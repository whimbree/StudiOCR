import os
import shutil

from PySide2 import QtCore as Qc
from PySide2 import QtWidgets as Qw
from PySide2 import QtGui as Qg

from StudiOCR.util import get_absolute_path
from StudiOCR.db import (db, OcrDocument, OcrPage, OcrBlock, create_tables)
from StudiOCR.PdfToImage import PDFToImage
from StudiOCR.PhotoViewer import PhotoViewer


class NewDocWindow(Qw.QDialog):
    """
    New Document Window Class: the window that appears when the user tries to insert a new document
    """

    close_event_signal = Qc.Signal(None)

    def __init__(self, new_doc_cb, parent=None):
        super().__init__(parent=parent)
        self.new_doc_cb = new_doc_cb

        self.setWindowTitle("Add New Document")

        self.desktop = Qw.QDesktopWidget()
        self.desktop_size = self.desktop.availableGeometry(
            self.desktop.primaryScreen()).size()
        self.resize(self.desktop_size.width() * 0.2,
                    self.desktop_size.height() * 0.6)

        self.display_preview_btn = Qw.QPushButton("Show document preview")
        self.display_preview_btn.setCheckable(True)
        self.display_preview_btn.setEnabled(False)
        self.display_preview_btn.toggled.connect(
            self.set_doc_preview_visibility)

        self.settings = NewDocOptions(self.new_doc_cb, parent=self)
        self.preview = NewDocPreview(parent=self)

        self.settings.close_on_submit_signal.connect(self.close_on_submit)
        self.settings.has_new_file_previews.connect(
            self.update_preview_image_list)

        self.submitted = False

        self.settings_layout = Qw.QVBoxLayout()
        self.settings_layout.addWidget(self.display_preview_btn)
        self.settings_layout.addWidget(self.settings)

        self.layout = Qw.QHBoxLayout()
        self.layout.addLayout(self.settings_layout)

        self.setLayout(self.layout)

    @Qc.Slot(list)
    def update_preview_image_list(self, pages):
        self.preview.update_preview_image_list(pages)
        if len(pages) > 0:
            self.display_preview_btn.setEnabled(True)
        else:
            # Hide the preview and disable the button
            self.display_preview_btn.setEnabled(False)
            self.display_preview_btn.setChecked(False)
            self.layout.removeWidget(self.preview)
            self.preview.hide()

    def set_doc_preview_visibility(self):
        if self.display_preview_btn.isChecked():
            self.display_preview_btn.setText("Hide document preview")
            self.resize(self.width() + self.desktop_size.width() * 0.2,
                        self.height())
            self.layout.addWidget(self.preview)
            self.preview.show()
        else:
            self.display_preview_btn.setText("Show document preview")
            self.resize(self.width() - self.preview.width(),
                        self.height())
            self.layout.removeWidget(self.preview)
            self.preview.hide()

    def close_on_submit(self):
        # If we are closing on submit, do not send close_event_signal to child
        # We need to preserve the temporary image files for processing
        self.submitted = True
        self.close()

    def closeEvent(self, e):
        if not self.submitted:
            self.close_event_signal.emit()


class DragList(Qw.QListWidget):
    """
    Subclass QListWidget to allow user to drag and drop files
    """

    file_dropped_signal = Qc.Signal(list)
    drag_complete_signal = Qc.Signal(None)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(Qw.QAbstractItemView.InternalMove)
        self.setSelectionMode(
            Qw.QAbstractItemView.ExtendedSelection)

    def width_hint(self):
        return self.sizeHintForColumn(0) + 24

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.accept()
        else:
            super().dragEnterEvent(e)

    def dropEvent(self, e):
        if e.mimeData().hasUrls():
            e.setDropAction(Qc.Qt.CopyAction)
            e.accept()
            filepaths = []
            for url in e.mimeData().urls():
                filepaths.append(str(url.toLocalFile()))

            self.file_dropped_signal.emit(filepaths)
        else:
            super().dropEvent(e)
        self.drag_complete_signal.emit()


class NewDocPreview(Qw.QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)

        self._image_previewer = Qw.QLabel()
        self.viewer = PhotoViewer(parent=self)

        self._curr_preview_page = 0
        # create button group for prev and next page buttons
        self.next_page_button = Qw.QPushButton("Next Page")
        self.next_page_button.setSizePolicy(
            Qw.QSizePolicy.MinimumExpanding, Qw.QSizePolicy.Fixed)
        self.next_page_button.clicked.connect(self.next_page)
        self.prev_page_button = Qw.QPushButton("Previous Page")
        self.prev_page_button.setSizePolicy(
            Qw.QSizePolicy.MinimumExpanding, Qw.QSizePolicy.Fixed)
        self.prev_page_button.clicked.connect(self.prev_page)
        self.page_number_label = Qw.QLabel(str(self._curr_preview_page + 1))

        self.page_number_box = Qw.QLineEdit(parent=self)
        self.page_number_box.setSizePolicy(
            Qw.QSizePolicy.Minimum, Qw.QSizePolicy.Fixed)
        self.page_number_box.editingFinished.connect(
            lambda: self.jump_to_page(int(self.page_number_box.text())-1))

        self._button_group = Qw.QHBoxLayout()
        self._button_group.addWidget(self.prev_page_button)
        self._button_group.addWidget(self.page_number_box)
        self._button_group.addWidget(self.next_page_button)

        self.preview_layout = Qw.QVBoxLayout()
        self.preview_layout.addWidget(self.viewer)
        self.preview_layout.addLayout(self._button_group)

        self.setLayout(self.preview_layout)

        self._pages = []
        self._pages_len = 0

    def update_preview_image_list(self, pages):
        self._pages = pages
        self._pages_len = len(self._pages)
        self.page_number_box.setInputMask(
            "0" * len(str(self._pages_len)))
        self.page_number_box.setFixedWidth(
            self.page_number_box.fontMetrics().boundingRect(str(self._pages_len)).width() + 20)
        self.jump_to_page(min(self._curr_preview_page, self._pages_len - 1))

    def jump_to_page(self, page_num: int):
        self.page_number_box.blockSignals(True)
        if page_num < self._pages_len and page_num >= 0:
            self._curr_preview_page = page_num
            self.page_number_box.setText(str(self._curr_preview_page+1))
            self.update_image()
        else:
            self.page_number_box.setText(str(self._curr_preview_page+1))
        self.page_number_box.blockSignals(False)

    def update_image(self):
        """
        Sets the image preview of the selected file
        """

        print("previewing image")
        if self._pages_len > 0:
            self._pixmap = Qg.QPixmap(
                self._pages[self._curr_preview_page])
            self.viewer.setPhoto(self._pixmap)
        else:
            self.viewer.hide()

    def next_page(self):
        if self._curr_preview_page + 1 < self._pages_len:
            self.jump_to_page(self._curr_preview_page + 1)

    def prev_page(self):
        if self._curr_preview_page - 1 >= 0:
            self.jump_to_page(self._curr_preview_page - 1)


class NewDocOptions(Qw.QWidget):
    """
    Contains the methods for new document insertion: model selection and add/remove functionality
    """

    close_on_submit_signal = Qc.Signal(None)

    has_new_file_previews = Qc.Signal(list)

    def __init__(self, new_doc_cb, parent=None):
        super().__init__(parent)

        self.new_doc_cb = new_doc_cb

        self.parentWidget().close_event_signal.connect(self.cleanup_temp_files)

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
        self.info_button.setIcon(
            Qg.QIcon(get_absolute_path("icons/info_icon.png")))
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
        options_layout.addWidget(self.info_button, alignment=Qc.Qt.AlignRight)
        self.options.setLayout(options_layout)

        self.file_names_label = Qw.QLabel("Files Chosen: ")
        self.listwidget = DragList(self)
        self.listwidget.file_dropped_signal.connect(self.insert_files)
        self.listwidget.drag_complete_signal.connect(self.update_file_previews)

        self.submit = Qw.QPushButton("Process Document")
        self.submit.clicked.connect(self.process_document)

        layout = Qw.QVBoxLayout()
        layout.addWidget(self.choose_file_button)
        layout.addWidget(self.remove_file_button)
        layout.addWidget(self.file_names_label)
        layout.addWidget(self.listwidget)
        layout.addWidget(self.options)
        layout.addWidget(self.submit, alignment=Qc.Qt.AlignBottom)

        main_layout = Qw.QHBoxLayout()
        main_layout.addLayout(layout)
        self.setLayout(main_layout)

        # For the preview image feature, keep two data types
        # Dictionary that stores PDF filepath -> ([image filepaths], temp_dir)
        self.pdf_previews = {}

    def sensible_max_width(self):
        preview_enabled = self.parentWidget().display_preview_btn.isChecked()

        if preview_enabled:
            max_width = max((max(self.listwidget.width_hint(), self.name_edit.fontMetrics(
            ).boundingRect(self.name_edit.text()).width() + 20)), 100)
        else:
            # By default widgets have a max width of 16777215
            max_width = 16777215

        return max_width

    def resizeEvent(self, e):
        self.setMaximumWidth(self.sensible_max_width())
        super().resizeEvent(e)

    def cleanup_temp_files(self):
        for key in self.pdf_previews:
            shutil.rmtree(self.pdf_previews[key][1])
        self.pdf_previews = {}

    def choose_files(self):
        """
        Opens the file dialog and sets a filter for the type of files allowed
        """
        file_dialog = Qw.QFileDialog(self)
        file_dialog.setStyleSheet(self.dropdown_style)
        file_dialog.setFileMode(Qw.QFileDialog.ExistingFiles)
        file_dialog.setNameFilters([
            "Image or PDF (*.png *.jpg *.jpeg *.pdf)"])
        file_dialog.selectNameFilter("Image or PDF (*.png *.jpg *.jpeg *.pdf)")

        if file_dialog.exec_():
            filepaths = file_dialog.selectedFiles()
            self.insert_files(filepaths)

        self.update_file_previews()

    @Qc.Slot(list)
    def insert_files(self, filepaths):
        # Insert the file(s) into listwidget unless it is a duplicate
        items_list = [self.listwidget.item(
            i).text() for i in range(self.listwidget.count())]
        allowed_extensions = ['.jpg', '.jpeg', '.png', '.pdf']
        had_invalid_extension = False
        for filepath in filepaths:
            _, file_extension = os.path.splitext(filepath)
            # Should we alert the user if they are trying to add a duplicate file?
            if filepath not in items_list:
                if file_extension in allowed_extensions:
                    self.listwidget.insertItem(
                        self.listwidget.count(), filepath)
                    items_list.append(filepath)
                # If there was a file added with an invalid extension, keep track of that and warn the user
                else:
                    had_invalid_extension = True

        if had_invalid_extension:
            msg = Qw.QMessageBox()
            msg.setIcon(Qw.QMessageBox.Information)
            msg.setText("This program only supports JPEG, PNG, and PDF files.")
            msg.setWindowTitle("Invalid file type")
            msg.exec_()

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

                # If the item being deleted is a PDF, ensure that we remove the temp files
                if item.text() in self.pdf_previews:
                    shutil.rmtree(self.pdf_previews[item.text()][1])
                    del self.pdf_previews[item.text()]

                self.listwidget.takeItem(self.listwidget.row(item))

        self.update_file_previews()

    def update_file_previews(self):
        """
        Update the file previews on file change
        """

        to_process = []
        for index in range(self.listwidget.count()):
            filepath = self.listwidget.item(index).text()
            filename, file_extension = os.path.splitext(filepath)
            if file_extension == '.pdf' and filepath not in self.pdf_previews:
                # If the file is a PDF, save the path into a queue for processing in a separate process
                # We do not want to block the GUI Thread
                to_process.append(filepath)

        if len(to_process) > 0:
            self.pdf_image_process = PDFToImage(self)
            self.pdf_image_process.done_signal.connect(
                self.complete_update_file_previews)

            self.pdf_image_process.pdf_filenames = to_process
            self.pdf_image_process.run()
        else:
            self.complete_update_file_previews({})

    @Qc.Slot(object)
    def complete_update_file_previews(self, result):
        self.pdf_previews.update(result)

        preview_image_filenames = []
        for index in range(self.listwidget.count()):
            filepath = self.listwidget.item(index).text()
            _, file_extension = os.path.splitext(filepath)
            if file_extension == '.pdf' and filepath in self.pdf_previews:
                preview_image_filenames.extend(self.pdf_previews[filepath][0])
            else:
                preview_image_filenames.append(filepath)

        self.has_new_file_previews.emit(preview_image_filenames)

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
            self.close_on_submit_signal.emit()
        db.close()

    def display_info(self):
        """
        When the information button is pressed, this window spawns with the information about the new
        document options
        """
        text_file = Qw.QTextBrowser()
        text = open(get_absolute_path("information_doc_options.txt")).read()
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
