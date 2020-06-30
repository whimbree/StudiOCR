from PySide2 import QtCore as Qc
from PySide2 import QtWidgets as Qw
from PySide2 import QtGui as Qg

from db import (db, OcrDocument, OcrPage, OcrBlock, create_tables)


class NewDocWindow(Qw.QDialog):
    """
    New Document Window Class: the window that appears when the user tries to insert a new document
    """

    def __init__(self, new_doc_cb, parent=None, *args, **kwargs):
        super().__init__(parent=parent, *args, **kwargs)
        self.new_doc_cb = new_doc_cb

        self.setWindowTitle("Add New Document")

        desktop = Qw.QDesktopWidget()
        desktop_size = desktop.availableGeometry(
            desktop.primaryScreen()).size()
        self.resize(desktop_size.width() * 0.2, desktop_size.height() * 0.6)

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

        # Bug in qdarkstyle that makes dropdowns too large, so we need to add styles
        self.dropdown_style = """QComboBox::item:checked {
                height: 12px;
                border: 1px solid #32414B;
                margin-top: 0px;
                margin-bottom: 0px;
                padding: 4px;
                padding-left: 0px;
                }"""

        self.best_vs_fast = Qw.QLabel("Best Model or Fast Model:")
        self.best_vs_fast_options = Qw.QComboBox()

        self.best_vs_fast_options.setStyleSheet(self.dropdown_style)
        self.best_vs_fast_options.addItem("Fast")
        self.best_vs_fast_options.addItem("Best")
        # Default should be Best
        self.best_vs_fast_options.setCurrentIndex(1)

        self.processing_label = Qw.QLabel("Perform image preprocessing:")
        self.processing_options = Qw.QComboBox()
        self.processing_options.setStyleSheet(self.dropdown_style)
        self.processing_options.addItem("No")
        self.processing_options.addItem("Yes")
        # Default should be no
        self.processing_options.setCurrentIndex(0)

        self.psm_label = Qw.QLabel("PSM Number")
        self.psm_num = Qw.QComboBox()
        self.psm_num.setStyleSheet(self.dropdown_style)
        for i in range(3, 14):
            self.psm_num.addItem(str(i))
        # Default should be 3
        self.psm_num.setCurrentIndex(0)

        # self.oem_label = Qw.QLabel("OEM Number")
        # self.oem_num = Qw.QComboBox()
        # self.oem_num.setStyleSheet(self.dropdown_style)
        # for i in range(0, 4):
        #     self.oem_num.addItem(str(i))
        # # Default should be 3
        # self.oem_num.setCurrentIndex(3)

        self.info_button = Qw.QPushButton()
        self.info_button.setIcon(Qg.QIcon("../icons/info_icon.png"))
        self.info_button.clicked.connect(self.display_info)

        options_layout = Qw.QVBoxLayout()
        options_layout.addWidget(self.name_label)
        options_layout.addWidget(self.name_edit)
        options_layout.addWidget(self.best_vs_fast)
        options_layout.addWidget(self.best_vs_fast_options)
        options_layout.addWidget(self.processing_label)
        options_layout.addWidget(self.processing_options)
        options_layout.addWidget(self.psm_label)
        options_layout.addWidget(self.psm_num)
        # options_layout.addWidget(self.oem_label)
        # options_layout.addWidget(self.oem_num)
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
        file_dialog.setStyleSheet(self.dropdown_style)
        file_dialog.setFileMode(Qw.QFileDialog.ExistingFiles)
        file_dialog.setNameFilter(
            "Images (*.png *.jpg)")
        file_dialog.selectNameFilter("Images (*.png *.jpg)")

        if file_dialog.exec_():
            file_names = file_dialog.selectedFiles()
            # Insert the file(s) into listwidget unless it is a duplicate
            itemsTextList = [self.listwidget.item(
                i).text() for i in range(self.listwidget.count())]
            for file_name in file_names:
                if file_name not in itemsTextList:
                    self.listwidget.insertItem(
                        self.listwidget.count(), file_name)
                    itemsTextList.append(file_name)

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
            # looks like the only oem modes supported by both the fast and best model is
            # the new LTSM mode, so we can hardcode the oem option to 3
            oem_number = 3
            psm_number = self.psm_num.currentIndex()+3
            best = bool(self.best_vs_fast_options.currentIndex())
            preprocessing = bool(self.processing_options.currentIndex())
            self.new_doc_cb(name, file_names, oem_number,
                            psm_number, best, preprocessing)
            self.close_cb()
        db.close()

    def display_info(self):
        """
        When the information button is pressed, this window spawns with the information about the new
        document options
        """
        text_file = Qw.QTextBrowser()
        text = open("../information_doc_options.txt").read()
        text_file.setText(text)
        dialog = Qw.QDialog(parent=self)

        desktop = Qw.QDesktopWidget()
        desktop_size = desktop.availableGeometry(
            desktop.primaryScreen()).size()
        dialog.resize(desktop_size.width() * 0.2, desktop_size.height() * 0.4)

        temp_layout = Qw.QHBoxLayout()
        temp_layout.addWidget(text_file)
        dialog.setWindowTitle("Information")
        dialog.setLayout(temp_layout)
        dialog.show()
