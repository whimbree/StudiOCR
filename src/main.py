from PySide2.QtCore import *
from PySide2.QtWidgets import *
from PySide2.QtGui import *

from multiprocessing import Process, Queue, Pipe

import sys
import random
import cv2
import numpy as np

from ocr import *

from db import *
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
    app = QApplication(sys_argv)  # Create application

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


class StatusEmitter(QThread):
    """
    Waits for new processed OCR data, then tells application to update accordingly
    """

    # These need to be declared as part of the class, not as part of an instance
    document_process_status = Signal(int)
    data_available = Signal(str)

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

            self.to_output.send((100, ocr.commit_data()))


class MainWindow(QMainWindow):
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

        self.emitter.data_available.connect(lambda a:
                                            self.main_widget.documents.display_new_document(a))

        self.docs_in_queue = 0

    def new_doc(self, name, filenames):
        """Send filenames and doc name to ocr process"""
        self.docs_in_queue += 1
        self.process_queue.put((name, filenames))

    def update_status_bar(self, current_doc_process_status):
        self.statusBar().showMessage(
            f"{self.docs_in_queue} documents in queue. Current document {current_doc_process_status}% complete.")
        if current_doc_process_status == 100:
            self.docs_in_queue -= 1
            if self.docs_in_queue == 0:
                self.statusBar().showMessage("All documents processed.")


class MainUI(QWidget):
    def __init__(self, new_doc_cb, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.new_doc_cb = new_doc_cb

        self.welcome_label = QLabel('Welcome to StudiOCR')
        self.welcome_label.setAlignment(Qt.AlignCenter)

        self.documents = ListDocuments(self.new_doc_cb, *args, **kwargs)

        self.layout = QVBoxLayout()
        self.layout.addWidget(self.welcome_label, alignment=Qt.AlignTop)
        self.layout.addWidget(self.documents, alignment=Qt.AlignTop)
        self.setLayout(self.layout)


class ListDocuments(QWidget):
    def __init__(self, new_doc_cb, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.new_doc_cb = new_doc_cb

        self.setSizePolicy(
            QSizePolicy.MinimumExpanding,
            QSizePolicy.MinimumExpanding
        )

        self._layout = QVBoxLayout()

        doc_grid = QGridLayout()
        ui_box = QHBoxLayout()

        self._docButtons = []

        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search for document name...")
        self.search_bar.textChanged.connect(self.update_filter)

        self.doc_search = QRadioButton("DOC")
        self.doc_search.setChecked(True)
        self.ocr_search = QRadioButton("OCR")

        ui_box.addWidget(self.doc_search)
        ui_box.addWidget(self.ocr_search)
        ui_box.addWidget(self.search_bar)

        # self._layout.addWidget(self.search_bar)

        # If there are no documents, then the for loop won't create the index variable
        self.idx = 0
        for self.idx, doc in enumerate(OcrDocument.select()):
            img = None
            name = doc.name
            if len(doc.pages) > 0:
                img = doc.pages[0].image

            doc_button = SingleDocumentButton(name, img, doc)
            doc_button.pressed.connect(
                lambda doc=doc: self.create_doc_window(doc))
            doc_grid.addWidget(doc_button, self.idx / 4, self.idx % 4, 1, 1)
            self._docButtons.append(doc_button)

        new_doc_button = SingleDocumentButton('Add New Document', None, None)
        new_doc_button.pressed.connect(
            lambda: self.create_new_doc_window())
        doc_grid.addWidget(new_doc_button, (self.idx+1) /
                           4, (self.idx+1) % 4, 1, 1)

        self._layout.addLayout(ui_box)
        self._layout.addLayout(doc_grid)

        self.setLayout(self._layout)

    def display_new_document(self, doc_id):
        # For some reason the doc_id does not come through.
        # We will likely have to rerender all documents from DB.
        print(doc_id)
        # doc = OcrDocument.get(OcrDocument.id == doc_id)
        # # I'm assuming that each doc will surely have at least one page
        # doc_button = SingleDocumentButton(doc.name, doc.pages[0].image)
        # doc_button.pressed.connect(
        #     lambda doc=doc: self.create_doc_window(doc))
        # layout.addWidget(doc_button, self.idx / 4, self.idx % 4, 1, 1)

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


class NewDocWindow(QWidget):
    def __init__(self, new_doc_cb, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.new_doc_cb = new_doc_cb

        self.setWindowTitle("Add New Document")

        self.settings = NewDocOptions(self.close, self.new_doc_cb)

        layout = QHBoxLayout()
        layout.addWidget(self.settings)
        # TODO: Create some kind of preview for the selected image files
        # ^Done with a "Files Chosen" section down below
        self.setLayout(layout)


class NewDocOptions(QWidget):
    def __init__(self, close_cb, new_doc_cb, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.close_cb = close_cb
        self.new_doc_cb = new_doc_cb

        self.file_names = []

        self.choose_file_button = QPushButton("Choose images")
        self.choose_file_button.clicked.connect(self.choose_files)

        self.options = QGroupBox("Options")
        self.name_label = QLabel("Document Name:")
        self.name_edit = QLineEdit()
        self.best_vs_fast = QLabel("Best Model or Fast Model:")
        self.best_vs_fast_options = QComboBox()
        self.best_vs_fast_options.addItem("Best")
        self.best_vs_fast_options.addItem("Fast")
        self.psm_label = QLabel("PSM Number")
        self.psm_num = QSpinBox()
        self.psm_num.setRange(1, 10)
        self.info_button = QPushButton()
        self.info_button.setIcon(QIcon("../images/info_icon.png"))
        self.info_button.clicked.connect(self.display_info)
        options_layout = QVBoxLayout()
        options_layout.addWidget(self.name_label)
        options_layout.addWidget(self.name_edit)
        options_layout.addWidget(self.best_vs_fast)
        options_layout.addWidget(self.best_vs_fast_options)
        options_layout.addWidget(self.psm_label)
        options_layout.addWidget(self.psm_num)
        options_layout.addWidget(self.info_button, alignment=Qt.AlignRight)
        self.options.setLayout(options_layout)

        self.file_names_label = QLabel("Files Chosen: ")
        self.listwidget = QListWidget()

        self.submit = QPushButton("Process Document")
        self.submit.clicked.connect(self.process_document)

        layout = QVBoxLayout()
        layout.addWidget(self.choose_file_button)
        layout.addWidget(self.options)
        layout.addWidget(self.file_names_label)
        layout.addWidget(self.listwidget)
        layout.addWidget(self.submit, alignment=Qt.AlignBottom)
        self.setLayout(layout)

    def choose_files(self):
        file_dialog = QFileDialog(self)
        file_dialog.setFileMode(QFileDialog.ExistingFiles)
        file_dialog.setNameFilter(
            "Images (*.png *.xpm *.jpg);;PDF Files (*.pdf)")
        file_dialog.selectNameFilter("Images (*.png *.xpm *.jpg)")

        if file_dialog.exec_():
            self.file_names = file_dialog.selectedFiles()

        for i in range(len(self.file_names)):
            self.listwidget.insertItem(i, self.file_names[i])
        # self.listwidget.clicked.connect(self.clicked)

    def process_document(self):
        name = self.name_edit.text()
        query = OcrDocument.select().where(OcrDocument.name == name)
        if query.exists() or len(name) == 0:
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Warning)
            msg.setText("Document names must be unique and non empty.")
            if len(name) == 0:
                msg.setInformativeText(
                    'Please enter a non-empty document name.')
            else:
                msg.setInformativeText(
                    'There is already a document with that name.')
            msg.setWindowTitle("Error")
            msg.exec_()
        elif len(self.file_names) == 0:
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Warning)
            msg.setText("No files were selected as part of the document.")
            msg.setInformativeText(
                'Please select files to process.')
            msg.setWindowTitle("Error")
            msg.exec_()
        else:
            self.new_doc_cb(name, self.file_names)
            self.close_cb()

    def display_info(self):
        print("Info clicked")
        info = QMessageBox()
        print(self.size())
        info.setFixedSize(self.size())
        info.setWindowTitle("OCR Information")
        info.setIcon(QMessageBox.Information)
        info.setInformativeText("Best vs Fast:\nBest is more accurate, but takes longer to process\nPSM Values:\n"
                                "0 - Orientation and script detection only")
        info.exec_()


class DocWindow(QWidget):
    def __init__(self, doc, filter='', *args, **kwargs):
        """
        Constructor method
        :param doc: OCRDocument
        :param filter: Filter from main window
        """
        super().__init__(*args, **kwargs)
        self.setWindowTitle(doc.name)

        self.setFixedWidth(500)
        self.setFixedHeight(800)

        self._doc = doc
        self._filter = filter
        self._currPage = 0
        self._listBlocks = []

        layout = QVBoxLayout()

        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search through notes...")
        self.search_bar.textChanged.connect(self.update_filter)
        layout.addWidget(self.search_bar, alignment=Qt.AlignTop)

        self.label = QLabel()
        # if filter passed through from main window, set the search bar text and update window
        if (self._filter):
            self.search_bar.setText(self._filter)
            self.im = QPixmap()
            self.update_filter()
        # display original image of first page
        else:
            img = QImage.fromData(self._doc.pages[0].image)
            qp = QPixmap.fromImage(img)
            self.im = qp.scaled(2550 / 5, 3300 / 5,
                                Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.label.setPixmap(self.im)
        layout.addWidget(self.label)

        # create button group for prev and next page buttons
        self.next_page_button = QPushButton("Next Page")
        self.next_page_button.clicked.connect(self.next_page)
        self.prev_page_button = QPushButton("Previous Page")
        self.prev_page_button.clicked.connect(self.prev_page)
        button_group = QHBoxLayout()
        button_group.addWidget(self.prev_page_button)
        button_group.addWidget(self.next_page_button)

        layout.addLayout(button_group)
        self.setLayout(layout)

    def resize_keep_aspect_ratio(self, image, width=None, height=None, inter=cv2.INTER_AREA):
        new_dim = None
        h, w = image.shape[:2]

        if width is None and height is None:
            return image
        elif width is None:
            ratio = height / h
            new_dim = (int(w * ratio), height)
        else:
            ratio = width / w
            new_dim = (width, int(h * ratio))

        return cv2.resize(image, new_dim, interpolation=inter)

    def next_page(self):
        """
        Increment the current page number if the next page button is pressed.
        If current page is the last page, the page will not increment
        :return: NONE
        """
        # if on last page, make current page the first page
        if(self._currPage + 1 != len(self._doc.pages)):
            self._currPage += 1
        self.update_image()

    def prev_page(self):
        """
        Decrement the current page number if the next page button is pressed.
        If current page is the first page, the page will not decrement
        :return: NONE
        """
        if(self._currPage != 0):
            self._currPage -= 1
        self.update_image()

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
        # if there is no search criteria, display original image of current page
        if not self._filter:
            img = QImage.fromData(self._doc.pages[self._currPage].image)
            qp = QPixmap.fromImage(img)
            self.im = qp.scaled(2550 / 5, 3300 / 5,
                                Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.label.setPixmap(self.im)
        else:
            # reset listBlocks
            self._listBlocks = []
            # search each block in the current page to see if it contains the search criteria (filter)
            for block in self._doc.pages[self._currPage].blocks:
                # if the filter value is contained in the block text, add block to list
                if(self._filter.lower() in block.text.lower()):
                    print(block.text, block.page_id)
                    self._listBlocks.append(block)

            # for each block containing the search criteria, draw rectangles on the image
            if self._listBlocks:
                # Convert image from database into numpy array for cv2
                nparr = np.frombuffer((self._doc.pages)[
                    self._currPage].image, np.uint8)
                # Convert numpy array into cv2 object for processing
                img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                for block in self._listBlocks:
                    # set start and end point of rectangle
                    start_point = (block.left, block.top)
                    end_point = (block.left + block.width,
                                 block.top + block.height)
                    color = (0, 0, 0)
                    # set color of rectangle based on confidence level of OCR
                    if block.conf >= 80:
                        color = (0, 255, 0)
                    elif (block.conf < 80 and block.conf >= 40):
                        color = (255, 0, 0)
                    else:
                        color = (0, 0, 255)
                    img = cv2.rectangle(img, start_point, end_point, color, 2)

                # convert cv2 object to QImage
                qimg = QImage(
                    img, img.shape[1], img.shape[0], img.shape[1]*3, QImage.Format_RGB888)
                img_pixmap = QPixmap.fromImage(qimg)
                self.im = img_pixmap.scaled(
                    2550 / 5, 3300 / 5, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.label.setPixmap(self.im)
            # no blocks found, display original image
            else:
                img = QImage.fromData(self._doc.pages[self._currPage].image)
                qp = QPixmap.fromImage(img)
                self.im = qp.scaled(
                    2550 / 5, 3300 / 5, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.label.setPixmap(self.im)


class SingleDocumentButton(QToolButton):
    def __init__(self, name, image, doc, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._name = name
        self._doc = doc

        self.setFixedSize(160, 160)

        layout = QVBoxLayout()

        label = QLabel(name)
        if image is not None:
            thumbnail = DocumentThumbnail(image)
            layout.addWidget(thumbnail, alignment=Qt.AlignCenter)

        layout.addWidget(label, alignment=Qt.AlignCenter)

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


class DocumentThumbnail(QLabel):
    def __init__(self, image, *args, **kwargs):
        super().__init__(*args, **kwargs)
        qimg = QImage.fromData(image)
        self.pixmap = QPixmap.fromImage(qimg)

        self.setPixmap(self.pixmap.scaled(
            self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def resizeEvent(self, e: QResizeEvent):
        self.setPixmap(self.pixmap.scaled(
            self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
        super().resizeEvent(e)


if __name__ == "__main__":
    main()
