from PySide2 import QtCore as Qc
from PySide2 import QtWidgets as Qw
from PySide2 import QtGui as Qg

from multiprocessing import Process, Queue, Pipe

import sys
import random
import numpy as np

from ocr import OcrProcess

from db import (db, OcrDocument, OcrPage, OcrBlock, create_tables)
import wsl

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
    def __init__(self, new_doc_cb, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.new_doc_cb = new_doc_cb

        self.welcome_label = Qw.QLabel('Welcome to StudiOCR')
        self.welcome_label.setAlignment(Qc.Qt.AlignCenter)

        self.documents = ListDocuments(self.new_doc_cb, *args, **kwargs)

        self.layout = Qw.QVBoxLayout()
        self.layout.addWidget(self.welcome_label, alignment=Qc.Qt.AlignTop)
        self.layout.addWidget(self.documents, alignment=Qc.Qt.AlignTop)
        self.setLayout(self.layout)


class ListDocuments(Qw.QWidget):
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

        self.ui_box.addWidget(self.doc_search)
        self.ui_box.addWidget(self.ocr_search)
        self.ui_box.addWidget(self.search_bar)

        # self._layout.addWidget(self.search_bar)

        for doc in OcrDocument.select():
            # assuming that each doc will surely have at least one page
            img = doc.pages[0].image
            name = doc.name

            doc_button = SingleDocumentButton(name, img, doc)
            doc_button.pressed.connect(
                lambda doc=doc: self.create_doc_window(doc))
            self._docButtons.append(doc_button)

        self.new_doc_button = SingleDocumentButton(
            'Add New Document', None, None)
        self.new_doc_button.pressed.connect(
            lambda: self.create_new_doc_window())

        self.render_doc_grid()

        self._layout.addLayout(self.ui_box)
        self._layout.addWidget(self.scroll_area)

        self.setLayout(self._layout)
        db.close()

    def render_doc_grid(self):
        # clear the doc_grid, not deleting widgets since they will be used later for repopulation
        while self.doc_grid.count():
            self.doc_grid.takeAt(0)
        # repopulate the doc_grid
        idx = 0
        self.doc_grid.addWidget(self.new_doc_button, idx / 4, idx % 4, 1, 1)
        idx += 1
        for button in self._docButtons:
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
        if(self.ocr_search.isChecked()):
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

        if(self.doc_search.isChecked()):
            for button in self._docButtons:
                if(self._filter.lower() in button.name.lower()):
                    button.show()
                else:
                    button.hide()
        elif(self.ocr_search.isChecked()):
            for button in self._docButtons:
                for page in button.doc.pages:
                    for block in page.blocks:
                        if(self._filter.lower() in block.text.lower()):
                            button.show()
                            break
                        else:
                            button.hide()
        db.close()


class NewDocWindow(Qw.QWidget):
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
        file_dialog = Qw.QFileDialog(self)
        file_dialog.setFileMode(Qw.QFileDialog.ExistingFiles)
        file_dialog.setNameFilter(
            "Images (*.png *.jpg);;PDF Files (*.pdf)")
        file_dialog.selectNameFilter("Images (*.png *.jpg)")

        if file_dialog.exec_():
            file_names = file_dialog.selectedFiles()

        for file_name in file_names:
            self.listwidget.insertItem(self.listwidget.count(), file_name)

    def remove_files(self):
        items = self.listwidget.selectedItems()
        for item in items:
            self.listwidget.takeItem(self.listwidget.row(item))

    def process_document(self):
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
    def __init__(self, doc, filter='', *args, **kwargs):
        """
        Constructor method
        :param doc: OCRDocument
        :param filter: Filter from main window
        """
        super().__init__(*args, **kwargs)
        db.connect(reuse_if_open=True)
        self.setWindowTitle(doc.name)

        self.setFixedWidth(500)
        self.setFixedHeight(800)

        self._doc = doc
        self._filter = filter
        self._currPage = 0
        self._pages = self._doc.pages
        self.update_page_blocks()
        self._listBlocks = []

        layout = Qw.QVBoxLayout()

        self.search_bar = Qw.QLineEdit()
        self.search_bar.setPlaceholderText("Search through notes...")
        self.search_bar.textChanged.connect(self.update_filter)
        layout.addWidget(self.search_bar, alignment=Qc.Qt.AlignTop)

        self.label = Qw.QLabel()
        # if filter passed through from main window, set the search bar text and update window
        if (self._filter):
            self.search_bar.setText(self._filter)
            self.im = Qg.QPixmap()
            self.update_filter()
        # display original image of first page
        else:
            img = Qg.QImage.fromData(self._pages[0].image)
            qp = Qg.QPixmap.fromImage(img)
            self.im = qp.scaled(2550 / 5, 3300 / 5,
                                Qc.Qt.KeepAspectRatio, Qc.Qt.SmoothTransformation)
            self.label.setPixmap(self.im)
        layout.addWidget(self.label)

        # create button group for prev and next page buttons
        self.next_page_button = Qw.QPushButton("Next Page")
        self.next_page_button.clicked.connect(self.next_page)
        self.prev_page_button = Qw.QPushButton("Previous Page")
        self.prev_page_button.clicked.connect(self.prev_page)
        button_group = Qw.QHBoxLayout()
        button_group.addWidget(self.prev_page_button)
        button_group.addWidget(self.next_page_button)

        layout.addLayout(button_group)
        self.setLayout(layout)
        db.close()

    def next_page(self):
        """
        Increment the current page number if the next page button is pressed.
        If current page is the last page, the page will not increment
        :return: NONE
        """
        # if on last page, make current page the first page
        if(self._currPage + 1 != len(self._pages)):
            self._currPage += 1
            self.update_page_blocks()
        self.update_image()

    def prev_page(self):
        """
        Decrement the current page number if the next page button is pressed.
        If current page is the first page, the page will not decrement
        :return: NONE
        """
        if(self._currPage != 0):
            self._currPage -= 1
            self.update_page_blocks()
        self.update_image()

    def update_page_blocks(self):
        self._page_blocks = self._pages[self._currPage].blocks

    def update_filter(self):
        """
        Updates the filter criteria as the text in the search bar changes
        :return: NONE
        """
        self._filter = self.search_bar.text()
        self.update_image()

    def update_image(self):
        """
        Function that updates the rectangles on the image based on self._currPage and self._filter
        :return: NONE
        """
        db.connect(reuse_if_open=True)
        # if there is no search criteria, display original image of current page
        if not self._filter:
            img = Qg.QImage.fromData(self._pages[self._currPage].image)
            qp = Qg.QPixmap.fromImage(img)
            self.im = qp.scaled(2550 / 5, 3300 / 5,
                                Qc.Qt.KeepAspectRatio, Qc.Qt.SmoothTransformation)
            self.label.setPixmap(self.im)
        else:
            # reset listBlocks
            self._listBlocks = []
            # search each block in the current page to see if it contains the search criteria (filter)
            for block in self._page_blocks:
                # if the filter value is contained in the block text, add block to list
                if(self._filter.lower() in block.text.lower()):
                    print(block.text, block.page_id)
                    self._listBlocks.append(block)

            # for each block containing the search criteria, draw rectangles on the image
            if self._listBlocks:
                img = Qg.QImage.fromData(self._pages[self._currPage].image)
                pixmap = Qg.QPixmap.fromImage(img)
                for block in self._listBlocks:
                    # set color of rectangle based on confidence level of OCR
                    if block.conf >= 80:
                        color = Qc.Qt.green
                    elif (block.conf < 80 and block.conf >= 40):
                        color = Qc.Qt.blue
                    else:
                        color = Qc.Qt.red
                    painter = Qg.QPainter(pixmap)
                    painter.setPen(Qg.QPen(color, 3, Qc.Qt.SolidLine))
                    painter.drawRect(block.left, block.top,
                                     block.width, block.height)
                    painter.end()

                self.im = pixmap.scaled(
                    2550 / 5, 3300 / 5, Qc.Qt.KeepAspectRatio, Qc.Qt.SmoothTransformation)
                self.label.setPixmap(self.im)
            # no blocks found, display original image
            else:
                img = Qg.QImage.fromData(self._pages[self._currPage].image)
                qp = Qg.QPixmap.fromImage(img)
                self.im = qp.scaled(
                    2550 / 5, 3300 / 5, Qc.Qt.KeepAspectRatio, Qc.Qt.SmoothTransformation)
                self.label.setPixmap(self.im)
        db.close()


class SingleDocumentButton(Qw.QToolButton):
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
