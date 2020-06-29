import wsl
from db import (db, OcrDocument, OcrPage, OcrBlock, create_tables)
from ocr import OcrProcess
import numpy as np
import random
import sys
import qdarkstyle
from collections import OrderedDict
from PySide2 import QtCore as Qc
from PySide2 import QtWidgets as Qw
from PySide2 import QtGui as Qg

from multiprocessing import Process, Queue, Pipe

# References
# https://doc.qt.io/qtforpython/


def main():
    # If the database has not been created, then create it
    create_tables()

    # Set DISPLAY env variable accordingly if running under WSL
    wsl.set_display_to_host()

    sys_argv = sys.argv
    sys_argv += ['--style', 'Fusion']
    app = Qw.QApplication(sys_argv)  # Create application

    # Create a pipe and queue for inter-process communication
    main_pipe, child_pipe = Pipe()
    queue = Queue()

    ocr_process = OcrProc(child_pipe, queue)
    status_emitter = StatusEmitter(main_pipe)

    window = MainWindow(queue, status_emitter)  # Create main window

    app.setStyleSheet(qdarkstyle.load_stylesheet(qt_api='pyside2'))

    window.show()  # Show main window

    ocr_process.start()  # Start child process

    app.exec_()  # Start application

    exit(0)


class StatusEmitter(Qc.QThread):
    """
    Waits for new processed OCR data, then tells application to update accordingly
    """

    # These need to be declared as part of the class, not as part of an instance
    document_process_status = Qc.Signal(int)
    data_available = Qc.Signal(int)

    def __init__(self, from_ocr_process: Pipe):
        super().__init__()

        self.data_from_process = from_ocr_process

    def run(self):
        while True:
            try:
                status, doc_id = self.data_from_process.recv()
            except EOFError:
                break
            else:
                if status is not None:
                    self.document_process_status.emit(status)
                if doc_id is not None:
                    self.data_available.emit(doc_id)


class OcrProc(Process):
    """
    Process to parse images using OCR and populate database
    """

    def __init__(self, to_output: Pipe, input_data: Queue, daemon=True):
        super().__init__()
        self.daemon = daemon
        self.to_output = to_output
        self.data_to_process = input_data

    def run(self):
        """
        Wait for any data to process and then process it and sent status updates
        """
        while True:
            (name, filepaths) = self.data_to_process.get()
            page_length = len(filepaths)
            ocr = OcrProcess(name)
            for idx, filepath in enumerate(filepaths):
                ocr.process_image(filepath)
                self.to_output.send(((idx / page_length)*100, None))
            doc_id = ocr.commit_data()
            self.to_output.send((100, doc_id))


class MainWindow(Qw.QMainWindow):
    """
    Custom Main Window class with new document and status bar features
    """
    def __init__(self, child_process_queue: Queue, emitter: StatusEmitter, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.process_queue = child_process_queue
        self.emitter = emitter
        self.emitter.daemon = True
        self.emitter.start()

        self.setWindowTitle("StudiOCR")
        self.resize(900, 900)

        self.main_widget = MainUI(self.new_doc)

        # Set the central widget of the Window.
        self.setCentralWidget(self.main_widget)

        # Configure emitter
        self.emitter.document_process_status.connect(self.update_status_bar)

        self.emitter.data_available.connect(
            self.main_widget.documents.display_new_document)

        self.docs_in_queue = 0

    def new_doc(self, name, filenames):
        """Send filenames and doc name to ocr process"""
        self.docs_in_queue += 1
        self.process_queue.put((name, filenames))

    @Qc.Slot(int)
    def update_status_bar(self, current_doc_process_status):
        self.statusBar().showMessage(
            f"{self.docs_in_queue} documents in queue. Current document {current_doc_process_status}% complete.")
        if current_doc_process_status == 100:
            self.docs_in_queue -= 1
            if self.docs_in_queue == 0:
                self.statusBar().showMessage("All documents processed.")


class MainUI(Qw.QWidget):
    """
    UI for the Main Window
    """
    def __init__(self, new_doc_cb, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.new_doc_cb = new_doc_cb

        self.welcome_label = Qw.QLabel('Welcome to StudiOCR')
        self.welcome_label.setAlignment(Qc.Qt.AlignCenter)

        self.documents = ListDocuments(self.new_doc_cb, *args, **kwargs)

        self.layout = Qw.QVBoxLayout()
        self.layout.addWidget(self.welcome_label, alignment=Qc.Qt.AlignTop)
        self.layout.addWidget(self.documents)
        self.setLayout(self.layout)


class ListDocuments(Qw.QWidget):
    """
    Contains methods for interacting with list of documents: removal, addition, displaying
    """
    def __init__(self, new_doc_cb, *args, **kwargs):
        super().__init__(*args, **kwargs)

        db.connect(reuse_if_open=True)

        self._filter = ''

        self.new_doc_cb = new_doc_cb

        self.setSizePolicy(
            Qw.QSizePolicy.MinimumExpanding,
            Qw.QSizePolicy.MinimumExpanding
        )

        self._layout = Qw.QVBoxLayout()

        self.doc_grid = Qw.QGridLayout()
        self.scroll_area = Qw.QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.ui_box = Qw.QHBoxLayout()

        self._docButtons = []

        self.search_bar = Qw.QLineEdit()
        self.search_bar.setPlaceholderText("Search for document name...")
        self.search_bar.textChanged.connect(self.update_filter)

        self.doc_search = Qw.QRadioButton("DOC")
        self.doc_search.setChecked(True)
        self.ocr_search = Qw.QRadioButton("OCR")

        self.remove_mode = Qw.QPushButton("Enable remove mode")
        self.remove_mode.setCheckable(True)
        self.remove_mode.toggled.connect(self.set_remove_mode)

        self.ui_box.addWidget(self.doc_search)
        self.ui_box.addWidget(self.ocr_search)
        self.ui_box.addWidget(self.search_bar)
        self.ui_box.addWidget(self.remove_mode)
        # produces the document buttons that users can interact with
        for doc in OcrDocument.select():
            # assuming that each doc will surely have at least one page
            img = doc.pages[0].image
            name = doc.name

            doc_button = SingleDocumentButton(name, img, doc)
            doc_button.pressed.connect(
                lambda doc=doc: self.create_doc_window(doc))
            doc_button.setVisible(True)
            self._docButtons.append(doc_button)

        self.new_doc_button = SingleDocumentButton(
            'Add New Document', None, None)
        self.new_doc_button.pressed.connect(
            lambda: self.create_new_doc_window())

        self._active_docs = self._docButtons

        self.render_doc_grid()

        self._layout.addLayout(self.ui_box)
        self._layout.addWidget(self.scroll_area)

        self.setLayout(self._layout)
        db.close()

    def set_remove_mode(self):
        if self.remove_mode.isChecked():
            self.remove_mode.setText("Disable remove mode")
        else:
            self.remove_mode.setText("Enable remove mode")
        self.render_doc_grid()

    def render_doc_grid(self):
        # clear the doc_grid, not deleting widgets since they will be used later for repopulation
        while self.doc_grid.count():
            # must make the removed widget a child of the class, so that it does not get garbage collected
            self.doc_grid.takeAt(0).widget().setParent(self)
        # repopulate the doc_grid
        idx = 0
        # hide the new document button if remove mode is enabled
        if not self.remove_mode.isChecked():
            self.doc_grid.addWidget(
                self.new_doc_button, idx / 4, idx % 4, 1, 1)
            idx += 1
        self._active_docs.sort(key=lambda button: button.name.lower())
        for button in self._active_docs:
            self.doc_grid.addWidget(button, idx / 4, idx % 4, 1, 1)
            idx += 1
        temp_widget = Qw.QWidget()
        temp_widget.setLayout(self.doc_grid)
        self.scroll_area.setWidget(temp_widget)

    @Qc.Slot(int)
    def display_new_document(self, doc_id):
        db.connect(reuse_if_open=True)
        doc = OcrDocument.get(OcrDocument.id == doc_id)
        # assuming that each doc will surely have at least one page
        doc_button = SingleDocumentButton(doc.name, doc.pages[0].image, doc)
        doc_button.pressed.connect(
            lambda doc=doc: self.create_doc_window(doc))
        self._docButtons.append(doc_button)
        self.render_doc_grid()
        db.close()

    def create_doc_window(self, doc):
        db.connect(reuse_if_open=True)
        # If remove mode is checked, then prompt and remove the document
        if self.remove_mode.isChecked():
            confirm = Qw.QMessageBox()
            confirm.setWindowTitle(f"Remove Document: {doc.name}")
            confirm.setText(
                f"Are you sure you want to delete document: {doc.name}?")
            confirm.setIcon(Qw.QMessageBox.Question)
            confirm.setStandardButtons(Qw.QMessageBox.Yes)
            confirm.addButton(Qw.QMessageBox.No)
            confirm.setDefaultButton(Qw.QMessageBox.No)
            if confirm.exec_() == Qw.QMessageBox.Yes:
                button_to_remove = None
                for button in self._docButtons:
                    if button.doc == doc:
                        button_to_remove = button
                        break
                self.doc_grid.removeWidget(button_to_remove)
                self._docButtons.remove(button_to_remove)
                self.update_filter()
                db.connect(reuse_if_open=True)
                print(doc.delete_document())
                db.close()
        else:
            if self.ocr_search.isChecked():
                self.doc_window = DocWindow(doc, self._filter)
            else:
                self.doc_window = DocWindow(doc)
            self.doc_window.show()

    def create_new_doc_window(self):
        self.new_doc_window = NewDocWindow(self.new_doc_cb)
        self.new_doc_window.show()

    def update_filter(self):
        db.connect(reuse_if_open=True)
        self._filter = self.search_bar.text()

        self._active_docs = []
        if(self.doc_search.isChecked()):
            for button in self._docButtons:
                if(self._filter.lower() in button.name.lower()):
                    self._active_docs.append(button)
        elif(self.ocr_search.isChecked()):
            for button in self._docButtons:
                text_found = False
                for page in button.doc.pages:
                    for block in page.blocks:
                        if(self._filter.lower() in block.text.lower()):
                            if(not text_found):
                                self._active_docs.append(button)
                                text_found = True
                                break
        db.close()
        self.render_doc_grid()


class NewDocWindow(Qw.QWidget):
    """
    New Document Window Class: the window that appears when the user tries to insert a new document
    """
    def __init__(self, new_doc_cb, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.new_doc_cb = new_doc_cb

        self.setWindowTitle("Add New Document")

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
        itemsTextList = [self.listwidget.item(i).text() for i in range(self.listwidget.count())]
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


class DocWindow(Qw.QWidget):
    """
    Document Window for when the user is searching in a specific document
    """
    def __init__(self, doc, filter='', *args, **kwargs):
        """
        Constructor method
        :param doc: OCRDocument
        :param filter: Filter from main window
        """
        super().__init__(*args, **kwargs)
        db.connect(reuse_if_open=True)
        self.setWindowTitle(doc.name)

        self._doc = doc
        self._filter = filter
        self._currPage = 0
        self._pages = self._doc.pages
        self._pages_len = len(self._pages)
        # Store key as page index, value as list of blocks
        self._filtered_page_indexes = OrderedDict()

        self._layout = Qw.QVBoxLayout()

        self._options = Qw.QHBoxLayout()

        self.search_bar = Qw.QLineEdit()
        self.search_bar.setPlaceholderText("Search through notes...")
        self.search_bar.textChanged.connect(self.update_filter)

        self.filter_mode = Qw.QPushButton("Show matching pages")
        self.filter_mode.setCheckable(True)
        self.filter_mode.toggled.connect(self.set_filter_mode)

        self._options.addWidget(self.search_bar, alignment=Qc.Qt.AlignTop)
        self._options.addWidget(self.filter_mode, alignment=Qc.Qt.AlignTop)
        self._layout.addLayout(self._options, alignment=Qc.Qt.AlignTop)

        self._pixmap = Qg.QPixmap()
        self._label_height_offset = 100
        self._label_width_offset = 40

        self.label = Qw.QLabel()
        # if filter passed through from main window, set the search bar text and update window
        if self._filter:
            self.search_bar.setText(self._filter)
            self.update_filter()
        # display original image of first page
        else:
            self.update_image()
        self._layout.addWidget(self.label, alignment=Qc.Qt.AlignCenter)

        # create button group for prev and next page buttons
        self.next_page_button = Qw.QPushButton("Next Page")
        self.next_page_button.setSizePolicy(
            Qw.QSizePolicy.MinimumExpanding, Qw.QSizePolicy.Fixed)
        self.next_page_button.clicked.connect(self.next_page)
        self.prev_page_button = Qw.QPushButton("Previous Page")
        self.prev_page_button.setSizePolicy(
            Qw.QSizePolicy.MinimumExpanding, Qw.QSizePolicy.Fixed)
        self.prev_page_button.clicked.connect(self.prev_page)
        self.page_number_label = Qw.QLabel(str(self._currPage+1))
        self._button_group = Qw.QHBoxLayout()
        self._button_group.addWidget(self.prev_page_button)
        self._button_group.addWidget(self.page_number_label)
        self._button_group.addWidget(self.next_page_button)

        self._layout.addLayout(self._button_group)
        self.setLayout(self._layout)
        db.close()

    def resizeEvent(self, e):
        pixmap_scaled = self._pixmap.scaled(
            self.width() - self._label_width_offset, self.height() - self._label_height_offset,
            Qc.Qt.KeepAspectRatio, Qc.Qt.SmoothTransformation)
        self.label.setPixmap(pixmap_scaled)
        self.label.setSizePolicy(
            Qw.QSizePolicy.Preferred, Qw.QSizePolicy.Preferred)
        super().resizeEvent(e)

    def set_filter_mode(self):
        if self.filter_mode.isChecked():
            self.filter_mode.setText("Show all pages")
            self.next_page_button.setText("Next Page containing search")
            self.prev_page_button.setText("Previous Page containing search")
            # if not already on page, then jump to the first page which matches search
            self.jump_first_matched_page()
        else:
            self.filter_mode.setText("Show matching pages")
            self.next_page_button.setText("Next Page")
            self.prev_page_button.setText("Previous Page")

    def next_page(self):
        """
        Increment the current page number if the next page button is pressed.
        If current page is the last page, the page will not increment
        :return: NONE
        """
        # if we are in the mode to only display pages that match filter, then iterate through  self._filteredPageIndexes
        if self.filter_mode.isChecked():
            # if nothing matches the filter, then do nothing
            if len(self._filtered_page_indexes) == 0:
                return
            # if not on last page, then find next page
            key_list = list(self._filtered_page_indexes.keys())
            if self._currPage != key_list[len(key_list)-1]:
                # find the index of the tuple whose page we are currently on, and set it to that + 1
                for index, page_number in enumerate(key_list):
                    if page_number == self._currPage:
                        break
                self._currPage = key_list[index + 1]
                self.page_number_label.setText(str(self._currPage+1))
                self.update_image()
        # otherwise, perform as normal
        else:
            # if not at end, then go forward a page
            if self._currPage + 1 != self._pages_len:
                self._currPage += 1
                self.page_number_label.setText(str(self._currPage+1))
            self.update_image()

    def prev_page(self):
        """
        Decrement the current page number if the next page button is pressed.
        If current page is the first page, the page will not decrement
        :return: NONE
        """
        # if we are in the mode to only display pages that match filter, then iterate through  self._filteredPageIndexes
        if self.filter_mode.isChecked():
            # if nothing matches the filter, then do nothing
            if len(self._filtered_page_indexes) == 0:
                return
            # if not on last page, then find next page
            key_list = list(self._filtered_page_indexes.keys())
            if self._currPage != key_list[0]:
                # find the index of the tuple whose page we are currently on, and set it to that + 1
                for index, page_number in enumerate(key_list):
                    if page_number == self._currPage:
                        break
                self._currPage = key_list[index - 1]
                self.page_number_label.setText(str(self._currPage+1))
                self.update_image()
        # otherwise, perform as normal
        else:
            # go not at beginning, then go back a page
            if self._currPage != 0:
                self._currPage -= 1
                self.page_number_label.setText(str(self._currPage+1))
            self.update_image()

    def update_filter(self):
        """
        Updates the filter criteria as the text in the search bar changes
        :return: NONE
        """
        self._filter = self.search_bar.text()
        self.exec_filter()
        self.update_image()
        # if in matching pages mode, jump to the first page that was matched if not already on matched page
        if self.filter_mode.isChecked():
            self.jump_first_matched_page()

    def jump_first_matched_page(self):
        """
        Jump to the first matched page if there are matches and not currently on a matched page,
        otherwise do nothing
        :return: NONE
        """
        if len(self._filtered_page_indexes) != 0 and self._currPage not in self._filtered_page_indexes.keys():
            self._currPage = list(self._filtered_page_indexes.keys())[0]
            self.page_number_label.setText(str(self._currPage+1))
            self.update_image()

    def exec_filter(self):
        """
        Performs filtering operations, populating self._filtered_page_indexes
        :return: NONE
        """
        # clear self._filtered_page_indexes
        self._filtered_page_indexes = OrderedDict()
        # if there is search critera, then perform filtering
        if self._filter:
            db.connect(reuse_if_open=True)
            # search each block in the current page to see if it contains the search criteria (filter)
            for page_index, page in enumerate(self._pages):
                matched_blocks = []
                for block in page.blocks:
                    text = block.text.lower()
                    # if the filter value is contained in the block text, add block to list
                    for word in self._filter.lower().split():
                        if word in text:
                            matched_blocks.append(block)
                if len(matched_blocks) != 0:
                    self._filtered_page_indexes[page_index] = matched_blocks
            db.close()

    def update_image(self):
        """
        Function that updates the rectangles on the image based on self._currPage and self._filtered_page_indexes
        :return: NONE
        """
        db.connect(reuse_if_open=True)
        # if there is no search criteria, display original image of current page
        if not self._filter or self._currPage not in self._filtered_page_indexes.keys():
            img = Qg.QImage.fromData(self._pages[self._currPage].image)
            self._pixmap = Qg.QPixmap.fromImage(img)
            pixmap_scaled = self._pixmap.scaled(self.width() - self._label_width_offset, self.height() - self._label_height_offset,
                                                Qc.Qt.KeepAspectRatio, Qc.Qt.SmoothTransformation)
            self.label.setPixmap(pixmap_scaled)
        else:
            # for each block containing the search criteria, draw rectangles on the image
            block_list = self._filtered_page_indexes[self._currPage]
            img = Qg.QImage.fromData(self._pages[self._currPage].image)
            self._pixmap = Qg.QPixmap.fromImage(img)
            for block in block_list:
                # set color of rectangle based on confidence level of OCR
                if block.conf >= 80:
                    color = Qc.Qt.green
                elif (block.conf < 80 and block.conf >= 40):
                    color = Qc.Qt.blue
                else:
                    color = Qc.Qt.red
                painter = Qg.QPainter(self._pixmap)
                painter.setPen(Qg.QPen(color, 3, Qc.Qt.SolidLine))
                painter.drawRect(block.left, block.top,
                                 block.width, block.height)
                painter.end()

            pixmap_scaled = self._pixmap.scaled(self.width() - self._label_width_offset, self.height() - self._label_height_offset,
                                                Qc.Qt.KeepAspectRatio, Qc.Qt.SmoothTransformation)
            self.label.setPixmap(pixmap_scaled)
        db.close()


class SingleDocumentButton(Qw.QToolButton):
    """
    Custom Button Class for Document Button which has a thumbnail of the first page
    """
    def __init__(self, name, image, doc, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._name = name
        self._doc = doc

        self.setFixedSize(160, 160)

        layout = Qw.QVBoxLayout()

        label = Qw.QLabel(name)
        if image is not None:
            thumbnail = DocumentThumbnail(image)
            layout.addWidget(thumbnail, alignment=Qc.Qt.AlignCenter)

        layout.addWidget(label, alignment=Qc.Qt.AlignCenter)

        self.setLayout(layout)

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, name):
        self._name = name

    @property
    def doc(self):
        return self._doc

    @doc.setter
    def doc(self, doc):
        self._doc = doc


class DocumentThumbnail(Qw.QLabel):
    """
    Class for creating the pixmap from page.imageblobdata
    """
    def __init__(self, image, *args, **kwargs):
        super().__init__(*args, **kwargs)
        qimg = Qg.QImage.fromData(image)
        self.pixmap = Qg.QPixmap.fromImage(qimg)

        self.setPixmap(self.pixmap.scaled(
            self.size(), Qc.Qt.KeepAspectRatio, Qc.Qt.SmoothTransformation))

    def resizeEvent(self, e: Qg.QResizeEvent):
        self.setPixmap(self.pixmap.scaled(
            self.size(), Qc.Qt.KeepAspectRatio, Qc.Qt.SmoothTransformation))
        super().resizeEvent(e)


if __name__ == "__main__":
    main()
