import sys
from multiprocessing import Queue, Pipe

from PySide2 import QtCore as Qc
from PySide2 import QtWidgets as Qw
from PySide2 import QtGui as Qg
import qdarkstyle

import wsl
from db import create_tables
from MainWindow import MainWindow
from OcrWorker import StatusEmitter, OcrWorker

# References
# https://doc.qt.io/qtforpython/


def main():
    # If the database has not been created, then create it
    create_tables()

    # Set DISPLAY env variable accordingly if running under WSL
    wsl.set_display_to_host()

    app = Qw.QApplication(sys.argv)  # Create application

    # Create a pipe and queue for inter-process communication
    main_pipe, child_pipe = Pipe()
    queue = Queue()

    ocr_process = OcrWorker(child_pipe, queue)
    status_emitter = StatusEmitter(main_pipe)

    window = MainWindow(queue, status_emitter)  # Create main window

    app.setStyleSheet(qdarkstyle.load_stylesheet(qt_api='pyside2'))

    window.show()  # Show main window

    ocr_process.start()  # Start child process

    app.exec_()  # Start application

    exit(0)


if __name__ == "__main__":
    main()
