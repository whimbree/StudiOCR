import tempfile
from multiprocessing import Pool

from PySide2 import QtCore as Qc
from PySide2 import QtWidgets as Qw
from PySide2 import QtGui as Qg

from pdf2image import convert_from_path, convert_from_bytes

from StudiOCR.util import get_threads


class PDFToImage(Qc.QThread):
    """
    Process the list of PDF files using multiple processes.
    Emit a dictionary when done: PDF filepath -> ([image filepaths], temp_dir)
    """
    done_signal = Qc.Signal(object)
    status_signal = Qc.Signal(int, int)  # done, total

    def __init__(self, parent=None):
        super().__init__(parent)
        self.pdf_filenames = []
        self.result = {}
        self._processed_so_far = 0

    @staticmethod
    def pdf_to_img(filepath):
        temp_dir = tempfile.mkdtemp()
        # NOTE: Must remove temp dir with shutil.rmtree(temp_dir) once done with PDF images files
        num_threads = get_threads()
        # Use 4 threads at max to prevent I/O bottleneck
        use_threads = num_threads if num_threads <= 4 else 4
        images_from_path = convert_from_path(
            filepath, fmt='jpeg', paths_only=True, output_folder=temp_dir, thread_count=use_threads, use_pdftocairo=True)
        return (filepath, (images_from_path, temp_dir))

    def run(self):
        self.p = Pool()
        for filename in self.pdf_filenames:
            self.p.apply_async(PDFToImage.pdf_to_img,
                               args=[filename], callback=self.emit_result)

    def emit_result(self, single_result):
        self.result[single_result[0]] = single_result[1]
        self._processed_so_far += 1
        len_to_process = len(self.pdf_filenames)
        self.status_signal.emit(self._processed_so_far, len_to_process)
        if len_to_process == self._processed_so_far:
            self.done_signal.emit(self.result)
            self.p.close()
            self.p.join()
