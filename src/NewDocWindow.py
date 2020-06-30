from PySide2 import QtCore as Qc
from PySide2 import QtWidgets as Qw
from PySide2 import QtGui as Qg

from db import (db, OcrDocument, OcrPage, OcrBlock, create_tables)


class NewDocWindow(Qw.QWidget):
    """
    New Document Window Class: the window that appears when the user tries to insert a new document
    """

    def __init__(self, new_doc_cb, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.new_doc_cb = new_doc_cb

        self.setWindowTitle("Add New Document")

        desktop = Qw.QDesktopWidget()
        desktop_size = desktop.availableGeometry(
            desktop.primaryScreen()).size()
        self.resize(desktop_size.width() * 0.2, desktop_size.height() * 0.4)

        self.settings = NewDocOptions(self.close, self.new_doc_cb)

        layout = Qw.QHBoxLayout()
        layout.addWidget(self.settings)
        # TODO: Create some kind of preview for the selected image files
        # ^Done with a "Files Chosen" section down below
        self.setLayout(layout)


class NewDocOptions(Qw.QWidget):
    """
    Contains the methods for new document insertion: model selection and add/remove/display functionality
    """

    def __init__(self, close_cb, new_doc_cb, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.close_cb = close_cb
        self.new_doc_cb = new_doc_cb

        self.choose_file_button = Qw.QPushButton("Add files")
        self.choose_file_button.clicked.connect(self.choose_files)

        self.remove_file_button = Qw.QPushButton("Remove files")
        self.remove_file_button.clicked.connect(self.remove_files)

        self.options = Qw.QGroupBox("Options")
        self.name_label = Qw.QLabel("Document Name:")
        self.name_edit = Qw.QLineEdit()
        self.best_vs_fast = Qw.QLabel("Best Model or Fast Model:")
        self.best_vs_fast_options = Qw.QComboBox()
        self.best_vs_fast_options.addItem("Best")
        self.best_vs_fast_options.addItem("Fast")
        self.psm_label = Qw.QLabel("PSM Number")
        self.psm_num = Qw.QSpinBox()
        self.psm_num.setRange(1, 10)
        self.info_button = Qw.QPushButton()
        self.info_button.setIcon(Qg.QIcon("../images/info_icon.png"))
        self.info_button.clicked.connect(self.display_info)
        options_layout = Qw.QVBoxLayout()
        options_layout.addWidget(self.name_label)
        options_layout.addWidget(self.name_edit)
        options_layout.addWidget(self.best_vs_fast)
        options_layout.addWidget(self.best_vs_fast_options)
        options_layout.addWidget(self.psm_label)
        options_layout.addWidget(self.psm_num)
        options_layout.addWidget(self.info_button, alignment=Qc.Qt.AlignRight)
        self.options.setLayout(options_layout)

        self.file_names_label = Qw.QLabel("Files Chosen: ")
        self.listwidget = Qw.QListWidget()
        self.listwidget.setDragEnabled(True)
        self.listwidget.setAcceptDrops(True)
        self.listwidget.setDropIndicatorShown(True)
        self.listwidget.setDragDropMode(Qw.QAbstractItemView.InternalMove)
        self.listwidget.setSelectionMode(
            Qw.QAbstractItemView.ExtendedSelection)

        self.submit = Qw.QPushButton("Process Document")
        self.submit.clicked.connect(self.process_document)

        layout = Qw.QVBoxLayout()
        layout.addWidget(self.choose_file_button)
        layout.addWidget(self.remove_file_button)
        layout.addWidget(self.file_names_label)
        layout.addWidget(self.listwidget)
        layout.addWidget(self.options)
        layout.addWidget(self.submit, alignment=Qc.Qt.AlignBottom)
        self.setLayout(layout)

    def choose_files(self):
        """
        Opens the file dialog and sets a filter for the type of files allowed
        """
        file_dialog = Qw.QFileDialog(self)
        file_dialog.setFileMode(Qw.QFileDialog.ExistingFiles)
        file_dialog.setNameFilter(
            "Images (*.png *.jpg);;PDF Files (*.pdf)")
        file_dialog.selectNameFilter("Images (*.png *.jpg)")

        if file_dialog.exec_():
            file_names = file_dialog.selectedFiles()
        # Insert the file(s) into listwidget unless it is a duplicate
        itemsTextList = [self.listwidget.item(
            i).text() for i in range(self.listwidget.count())]
        for file_name in file_names:
            if file_name not in itemsTextList:
                self.listwidget.insertItem(self.listwidget.count(), file_name)
                itemsTextList.append(file_name)
            else:
                print("Do not insert duplicates.")

    def remove_files(self):
        """
        Removes the selected files in listwidget upon button press
        """
        items = self.listwidget.selectedItems()
        if len(items) == 0:
            msg = Qw.QMessageBox()
            msg.setIcon(Qw.QMessageBox.Information)
            msg.setText("No files were selected for removal.")
            msg.setInformativeText(
                'Select one or more files in the files chosen list and try again.')
            msg.setWindowTitle("Info")
            msg.exec_()
        else:
            for item in items:
                self.listwidget.takeItem(self.listwidget.row(item))

    def process_document(self):
        """
        Adds a new document to the database with the file names from listwidget
        """
        db.connect(reuse_if_open=True)
        name = self.name_edit.text()
        query = OcrDocument.select().where(OcrDocument.name == name)
        file_names = []
        for index in range(self.listwidget.count()):
            file_names.append(self.listwidget.item(index).text())
        if query.exists() or len(name) == 0:
            msg = Qw.QMessageBox()
            msg.setIcon(Qw.QMessageBox.Warning)
            msg.setText("Document names must be unique and non empty.")
            if len(name) == 0:
                msg.setInformativeText(
                    'Please enter a non-empty document name.')
            else:
                msg.setInformativeText(
                    'There is already a document with that name.')
            msg.setWindowTitle("Error")
            msg.exec_()
        elif len(file_names) == 0:
            msg = Qw.QMessageBox()
            msg.setIcon(Qw.QMessageBox.Warning)
            msg.setText("No files were selected as part of the document.")
            msg.setInformativeText(
                'Please select files to process.')
            msg.setWindowTitle("Error")
            msg.exec_()
        else:
            self.new_doc_cb(name, file_names)
            self.close_cb()
        db.close()

    def display_info(self):
        print("Info clicked")
        info = Qw.QMessageBox()
        print(self.size())
        info.setFixedSize(self.size())
        info.setWindowTitle("OCR Information")
        info.setIcon(Qw.QMessageBox.Information)
        info.setInformativeText("Best vs Fast:\nBest is more accurate, but takes longer to process\nPSM Values:\n"
                                "0 - Orientation and script detection only")
        info.exec_()
