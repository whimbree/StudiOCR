from collections import OrderedDict
from multiprocessing import Process, Queue, Pipe

from PySide2 import QtCore as Qc
from PySide2 import QtWidgets as Qw
from PySide2 import QtGui as Qg

from db import (db, OcrDocument, OcrPage, OcrBlock, create_tables)
from OcrEngine import OcrEngine


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


class OcrWorker(Process):
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
            ocr = OcrEngine(name)
            for idx, filepath in enumerate(filepaths):
                ocr.process_image(filepath)
                self.to_output.send(((idx / page_length)*100, None))
            doc_id = ocr.commit_data()
            self.to_output.send((100, doc_id))
