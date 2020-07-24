import tempfile
from multiprocessing import Pool

from PySide2 import QtCore as Qc
from PySide2 import QtWidgets as Qw
from PySide2 import QtGui as Qg

from pdf2image import convert_from_path, convert_from_bytes


class PDFToImage(Qc.QThread):
    """
    Process the list of PDF files using multiple processes.
    Emit a dictionary when done: PDF filepath -> ([image filepaths], temp_dir)
    """
    done_signal = Qc.Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.pdf_filenames = []
        self.output_data = {}

    @staticmethod
    def pdf_to_img(filepath):
        temp_dir = tempfile.mkdtemp()
        # NOTE: Must remove temp dir with shutil.rmtree(temp_dir) once done with PDF images files
        images_from_path = convert_from_path(
            filepath, fmt='jpeg', paths_only=True, output_folder=temp_dir)
        return (filepath, (images_from_path, temp_dir))

    def run(self):
        self.p = Pool()
        self.p.map_async(PDFToImage.pdf_to_img,
                         self.pdf_filenames, callback=self.emit_result)

    def emit_result(self, result):
        self.done_signal.emit(dict(result))
        self.p.close()
        self.p.join()
