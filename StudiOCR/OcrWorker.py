from collections import OrderedDict
from multiprocessing import Process, Queue, Pipe

from PySide2 import QtCore as Qc
from PySide2 import QtWidgets as Qw
from PySide2 import QtGui as Qg

from StudiOCR.db import (db, OcrDocument, OcrPage, OcrBlock, create_tables)
from StudiOCR.OcrEngine import OcrEngine


class StatusEmitter(Qc.QThread):
    """
    Waits for new processed OCR data, then tells application to update accordingly
    """

    # These need to be declared as part of the class, not as part of an instance
    document_process_status = Qc.Signal(int)
    data_available = Qc.Signal(int)

    def __init__(self, from_ocr_process: Pipe, parent=None):
        super().__init__(parent=parent)

        self.running = False

        self.data_from_process = from_ocr_process

    def stop(self):
        self.running = False

    def run(self):
        self.running = True
        while self.running:
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
            value = self.data_to_process.get()
            # if sent None then terminate process
            if value is None:
                break
            (name, filepaths, (oem, psm, best, preprocessing)) = value
            page_length = len(filepaths)
            ocr = OcrEngine(name)
            for idx, filepath in enumerate(filepaths):
                ocr.process_image(image_filepath=filepath, oem=oem,
                                  psm=psm, best=best, preprocessing=preprocessing)
                self.to_output.send(((idx / page_length)*100, None))
            doc_id = ocr.commit_data()
            self.to_output.send((100, doc_id))
