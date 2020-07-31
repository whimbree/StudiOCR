from multiprocessing import Queue

from PySide2 import QtCore as Qc
from PySide2 import QtWidgets as Qw
from PySide2 import QtGui as Qg

from StudiOCR.db import (db, OcrDocument, OcrPage, OcrBlock, create_tables)
from StudiOCR.OcrWorker import StatusEmitter
from StudiOCR.ListDocuments import ListDocuments


class MainWindow(Qw.QMainWindow):
    """
    Custom Main Window class with new document and status bar features
    """

    def __init__(self, child_process_queue: Queue, emitter: StatusEmitter, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.process_queue = child_process_queue
        self.emitter = emitter

        self.setWindowTitle("StudiOCR")

        desktop = Qw.QDesktopWidget()
        self.resize(desktop.availableGeometry(
            desktop.primaryScreen()).size() * 0.5)

        self.main_widget = MainUI(self.new_doc)

        # Set the central widget of the Window.
        self.setCentralWidget(self.main_widget)

        # Configure emitter
        self.emitter.document_process_status.connect(
            self.set_document_process_status)

        self.emitter.data_available.connect(
            self.main_widget.documents.display_new_document)

        self.docs_in_queue = 0
        self.current_doc_process_status = 0

    def new_doc(self, name, doc_id, temp_folders, filenames, oem, psm, best, preprocessing):
        """Send filenames and doc name to ocr process"""
        self.process_queue.put(
            (name, doc_id, temp_folders, filenames, (oem, psm, best, preprocessing)))
        self.docs_in_queue += 1
        self.update_status_bar()

    @ Qc.Slot(int)
    def set_document_process_status(self, current_doc_process_status):
        self.current_doc_process_status = current_doc_process_status
        self.update_status_bar()

    def update_status_bar(self):
        self.statusBar().showMessage(
            f"{self.docs_in_queue} documents in queue. Current document {self.current_doc_process_status}% complete.")
        if self.current_doc_process_status == 100:
            self.docs_in_queue -= 1
            self.current_doc_process_status = 0
            if self.docs_in_queue == 0:
                self.statusBar().showMessage("All documents processed.")
            else:
                self.update_status_bar()


class MainUI(Qw.QWidget):
    """
    UI for the Main Window
    """

    def __init__(self, new_doc_cb, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.new_doc_cb = new_doc_cb

        self.welcome_label = Qw.QLabel('Welcome to StudiOCR')
        self.welcome_label.setAlignment(Qc.Qt.AlignCenter)

        self.documents = ListDocuments(self.new_doc_cb, self)

        self.layout = Qw.QVBoxLayout()
        self.layout.addWidget(self.welcome_label, alignment=Qc.Qt.AlignTop)
        self.layout.addWidget(self.documents)
        self.setLayout(self.layout)
