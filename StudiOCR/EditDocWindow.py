import os
import shutil

from PySide2 import QtCore as Qc
from PySide2 import QtWidgets as Qw
from PySide2 import QtGui as Qg

from StudiOCR.util import get_absolute_path
from StudiOCR.db import (db, OcrDocument, OcrPage, OcrBlock, create_tables)
from StudiOCR.PdfToImage import PDFToImage
from StudiOCR.PhotoViewer import PhotoViewer


class EditDocWindow(Qw.QDialog):
    """
    Edit Document Window Class: the window that appears when the user tries to insert a new document
    This window also appears when the user wants to add pages to an existing document
    """

    close_event_signal = Qc.Signal(None)

    def __init__(self, new_doc_cb, doc=None, parent=None):
        super().__init__(parent=parent)
        db.connect(reuse_if_open=True)

        self._doc = doc

        self.new_doc_cb = new_doc_cb

        if self._doc is None:
            self.setWindowTitle("Add New Document")
        else:
            self.setWindowTitle(f"Add pages to {self._doc.name}")

        self.desktop = Qw.QDesktopWidget()
        self.desktop_size = self.desktop.availableGeometry(
            self.desktop.primaryScreen()).size()
        self.resize(self.desktop_size.width() * 0.2,
                    self.desktop_size.height() * 0.6)

        self.settings = EditDocOptions(self.new_doc_cb, doc=doc, parent=self)
        self.preview = EditDocPreview(doc=self._doc, parent=self)
        self.preview.hide()

        self.settings.close_on_submit_signal.connect(self.close_on_submit)
        self.settings.has_new_file_previews.connect(
            self.preview.update_preview_image_list)
        self.settings.display_preview_toggle_signal.connect(
            self.set_preview_visibility)

        self.submitted = False

        self.settings_layout = Qw.QVBoxLayout()
        # self.settings_layout.addWidget(self.display_preview_button)
        self.settings_layout.addWidget(self.settings)

        self.layout = Qw.QHBoxLayout()
        self.layout.addLayout(self.settings_layout)

        self.setLayout(self.layout)

        db.close()

    @Qc.Slot(bool)
    def set_preview_visibility(self, visible: bool):
        if visible:
            self.resize(self.width() + self.desktop_size.width() * 0.2,
                        self.height())
            self.layout.addWidget(self.preview)
            self.preview.show()
        else:
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


class EditDocPreview(Qw.QWidget):

    def __init__(self, doc=None, parent=None):
        super().__init__(parent)
        db.connect(reuse_if_open=True)

        self._image_previewer = Qw.QLabel()
        self.viewer = PhotoViewer(parent=self)

        self._doc = doc
        self._doc_size = 0 if self._doc is None else len(self._doc.pages)

        self._curr_preview_page = 0
        # create button group for prev and next page buttons
        self.next_page_button = Qw.QPushButton(
            "Next Page", default=False, autoDefault=False, parent=self)
        self.next_page_button.setSizePolicy(
            Qw.QSizePolicy.MinimumExpanding, Qw.QSizePolicy.Fixed)
        self.next_page_button.clicked.connect(self.next_page)
        self.prev_page_button = Qw.QPushButton(
            "Previous Page", default=False, autoDefault=False, parent=self)
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

        db.close()

        if self._doc is not None:
            self.update_preview_image_list([])

    @Qc.Slot(list)
    def update_preview_image_list(self, pages):
        self._pages = pages
        self._pages_len = len(self._pages)
        self.page_number_box.setInputMask(
            "0" * len(str(self._pages_len + self._doc_size)))
        self.page_number_box.setFixedWidth(
            self.page_number_box.fontMetrics().boundingRect(str(self._pages_len + self._doc_size)).width() + 20)
        # If adding pages to an existing document, instead jump to the beginning of the added pages
        if self._doc is not None:
            page_to_jump_to = self._curr_preview_page if self._curr_preview_page > self._doc_size or self._pages_len == 0 else self._doc_size
            self.jump_to_page(min(page_to_jump_to,
                                  self._pages_len + self._doc_size - 1))
        else:
            # otherwise keep the same page, only changing if total pages is less than current page
            self.jump_to_page(min(self._curr_preview_page,
                                  self._pages_len - 1))

    def jump_to_page(self, page_num: int):
        self.page_number_box.blockSignals(True)
        if page_num < self._pages_len+self._doc_size and page_num >= 0:
            self._curr_preview_page = page_num
            self.page_number_box.setText(str(self._curr_preview_page+1))
            self.update_image()
        elif page_num >= self._pages_len+self._doc_size:
            self._curr_preview_page = self._pages_len+self._doc_size-1
            self.page_number_box.setText(str(self._curr_preview_page+1))
            self.update_image()
        else:
            self.page_number_box.setText(str(self._curr_preview_page+1))
        self.page_number_box.blockSignals(False)

    def update_image(self):
        """
        Sets the image preview of the selected file
        """

        if self._curr_preview_page < self._doc_size:
            db.connect(reuse_if_open=True)
            img = Qg.QImage.fromData(
                self._doc.pages[self._curr_preview_page].image)
            db.close()
            self._pixmap = Qg.QPixmap.fromImage(img)
            self.viewer.setPhoto(self._pixmap)
        elif self._pages_len > 0:
            self._pixmap = Qg.QPixmap(
                self._pages[self._curr_preview_page - self._doc_size])
            self.viewer.setPhoto(self._pixmap)
        else:
            self.viewer.hide()

    def next_page(self):
        if self._curr_preview_page + 1 < self._pages_len + self._doc_size:
            self.jump_to_page(self._curr_preview_page + 1)

    def prev_page(self):
        if self._curr_preview_page - 1 >= 0:
            self.jump_to_page(self._curr_preview_page - 1)


class EditDocOptions(Qw.QWidget):
    """
    Contains the methods for new document insertion: model selection and add/remove functionality
    """

    close_on_submit_signal = Qc.Signal(None)
    has_new_file_previews = Qc.Signal(list)
    display_preview_toggle_signal = Qc.Signal(bool)

    def __init__(self, new_doc_cb, doc=None, parent=None):
        super().__init__(parent)
        db.connect(reuse_if_open=True)

        self.new_doc_cb = new_doc_cb

        self._doc = doc
        self._doc_size = 0 if self._doc is None else len(self._doc.pages)

        self.parentWidget().close_event_signal.connect(self.cleanup_temp_files)

        self.display_preview_button = Qw.QPushButton(
            "Show document preview", default=False, autoDefault=False, parent=self)
        self.display_preview_button.setCheckable(True)
        if self._doc is None:
            self.display_preview_button.setEnabled(False)
        self.display_preview_button.toggled.connect(
            self.on_display_preview_button_toggled)

        self.choose_file_button = Qw.QPushButton(
            "Add files", default=False, autoDefault=False, parent=self)
        self.choose_file_button.clicked.connect(self.choose_files)

        self.remove_file_button = Qw.QPushButton(
            "Remove files", default=False, autoDefault=False, parent=self)
        self.remove_file_button.clicked.connect(self.remove_files)

        self.options = Qw.QGroupBox("Options")

        self.name_label = Qw.QLabel("Document Name:")
        self.name_edit = Qw.QLineEdit(parent=self)
        if self._doc is not None:
            self.name_edit.setText(self._doc.name)
            # renaming is not permitted
            self.name_edit.setReadOnly(True)

        # Bug in qdarkstyle that makes dropdowns too large, so we need to add styles
        self.dropdown_style = """QComboBox::item:checked {
                height: 12px;
                border: 1px solid #32414B;
                margin-top: 0px;
                margin-bottom: 0px;
                padding: 4px;
                padding-left: 0px;
                }"""

        self.preset_label = Qw.QLabel("Preset:")
        self.preset_options = Qw.QComboBox()
        self.preset_options.setStyleSheet(self.dropdown_style)
        self.preset_options.addItem("Screenshot")
        self.preset_options.addItem("Printed Text (PDF)")
        self.preset_options.addItem("Written Paragraph")
        self.preset_options.addItem("Written Page")
        self.preset_options.addItem("Custom")
        self.preset_options.setCurrentIndex(4)
        self.preset_options.currentIndexChanged.connect(self.preset_changed)

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
        #default should be no
        self.processing_options.setCurrentIndex(0)
        self.processing_options.currentIndexChanged.connect(self.custom_preset)

        self.psm_label = Qw.QLabel("PSM Number")
        self.psm_num = Qw.QComboBox()
        self.psm_num.setStyleSheet(self.dropdown_style)
        for i in range(3, 14):
            self.psm_num.addItem(str(i))
        # Default should be 3
        self.psm_num.setCurrentIndex(0)
        self.psm_num.currentIndexChanged.connect(self.custom_preset)

        self.info_button = Qw.QPushButton(
            default=False, autoDefault=False, parent=self)
        self.info_button.setIcon(
            Qg.QIcon(get_absolute_path("icons/info_icon.png")))
        self.info_button.clicked.connect(self.display_info)

        self.status_bar = Qw.QStatusBar()
        self.status_bar.showMessage("Ready")

        options_layout = Qw.QVBoxLayout()
        options_layout.addWidget(self.name_label)
        options_layout.addWidget(self.name_edit)
        options_layout.addWidget(self.preset_label)
        options_layout.addWidget(self.preset_options)
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

        self.submit = Qw.QPushButton(
            "Process Document", default=False, autoDefault=False, parent=self)
        self.submit.clicked.connect(self.process_document)

        layout = Qw.QVBoxLayout()
        layout.addWidget(self.display_preview_button)
        layout.addWidget(self.choose_file_button)
        layout.addWidget(self.remove_file_button)
        layout.addWidget(self.file_names_label)
        layout.addWidget(self.listwidget)
        layout.addWidget(self.options)
        layout.addWidget(self.submit)
        layout.addWidget(self.status_bar)

        main_layout = Qw.QHBoxLayout()
        main_layout.addLayout(layout)
        self.setLayout(main_layout)

        # For the preview image feature, keep two data types
        # Dictionary that stores PDF filepath -> ([image filepaths], temp_dir)
        self.pdf_previews = {}
        # List of filenames, with PDFs already converted to images
        self._pages = []

        db.close()

    def custom_preset(self):
        #set preset to custom
        self.preset_options.setCurrentIndex(4)

    def preset_changed(self, i):
        self.processing_options.blockSignals(True)
        self.psm_num.blockSignals(True)
        #screenshot
        if self.preset_options.currentIndex() == 0:
            self.processing_options.setCurrentIndex(0)
            self.psm_num.setCurrentIndex(0)
        #printed text
        elif self.preset_options.currentIndex() == 1:
            self.processing_options.setCurrentIndex(0)
            self.psm_num.setCurrentIndex(0)
        #written paragraph
        elif self.preset_options.currentIndex() == 2:
            self.processing_options.setCurrentIndex(1)
            self.psm_num.setCurrentIndex(3)
        #written page
        elif self.preset_options.currentIndex() == 3:
            self.processing_options.setCurrentIndex(1)
            self.psm_num.setCurrentIndex(0)
        self.processing_options.blockSignals(False)
        self.psm_num.blockSignals(False)

    @Qc.Slot(None)
    def on_display_preview_button_toggled(self):
        if self.display_preview_button.isChecked():
            self.display_preview_button.setText("Hide document preview")
            self.setMaximumWidth(self.sensible_max_width())
            self.display_preview_toggle_signal.emit(True)
        else:
            self.display_preview_button.setText("Show document preview")
            self.setMaximumWidth(self.sensible_max_width())
            self.display_preview_toggle_signal.emit(False)

    def sensible_max_width(self):
        preview_enabled = self.display_preview_button.isChecked()

        if preview_enabled:
            max_width = max((max(self.listwidget.width_hint(), self.name_edit.fontMetrics(
            ).boundingRect(self.name_edit.text()).width() + 20)), 200)
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

    @Qc.Slot(int, int)
    def update_pdf_process_status(self, processed: int, total: int):
        if processed != total:
            self.status_bar.showMessage(
                f"Processing PDFs, {processed} out of {total}")
        else:
            self.status_bar.showMessage("Ready")

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
            # disable the buttons until all the PDFs are done processing
            self.submit.setEnabled(False)
            self.choose_file_button.setEnabled(False)
            self.remove_file_button.setEnabled(False)
            self.pdf_image_process = PDFToImage(self)
            self.pdf_image_process.done_signal.connect(
                self.complete_update_file_previews)
            self.pdf_image_process.status_signal.connect(
                self.update_pdf_process_status)

            self.pdf_image_process.pdf_filenames = to_process
            self.pdf_image_process.run()
            self.update_pdf_process_status(0, len(to_process))
        else:
            self.complete_update_file_previews({})

    @Qc.Slot(object)
    def complete_update_file_previews(self, result):
        self.pdf_previews.update(result)

        # re-enable the buttons
        self.submit.setEnabled(True)
        self.choose_file_button.setEnabled(True)
        self.remove_file_button.setEnabled(True)

        self._pages = []
        for index in range(self.listwidget.count()):
            filepath = self.listwidget.item(index).text()
            _, file_extension = os.path.splitext(filepath)
            if file_extension == '.pdf' and filepath in self.pdf_previews:
                self._pages.extend(self.pdf_previews[filepath][0])
            else:
                self._pages.append(filepath)

        # hide the preview if there is no files to display
        # also disable the button
        if len(self._pages) > 0:
            self.display_preview_button.setEnabled(True)
        elif self._doc is None:
            # Hide the preview and disable the button
            self.display_preview_button.setEnabled(False)
            self.display_preview_button.setChecked(False)

        self.has_new_file_previews.emit(self._pages)

    def process_document(self):
        """
        Adds a new document to the database with the file names from listwidget
        """
        db.connect(reuse_if_open=True)
        name = self.name_edit.text()
        query = OcrDocument.select().where(OcrDocument.name == name)
        if (query.exists() or len(name) == 0) and self._doc is None:
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
        elif len(self._pages) == 0:
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
            self.new_doc_cb(name, self.pdf_previews, self._pages, oem_number,
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
