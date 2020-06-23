from PySide2.QtCore import Slot, Qt, QSize
import sys
import os
import glob
import random
from PySide2.QtWidgets import QApplication, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QWidget, QFileDialog, QMainWindow, QLineEdit
from PySide2.QtWidgets import QGridLayout
from PySide2.QtGui import QPixmap
from PIL import Image

# References
# https://doc.qt.io/qtforpython/


def main():
    app = QApplication(sys.argv)  # Create application

    widget = Notes_Grid()  # Create widget

    widget.show()

    sys.exit(app.exec_())  # Start application

class Main_UI(QMainWindow):
    def __init__(self):
        QMainWindow.__init__(self)

        self.setMinimumSize(QSize(300, 200))
        self.setStyleSheet('background-color : white;')
        self.choose_file_button = QPushButton("Choose file", self)
        self.choose_file_button.setStyleSheet('background-color: orange; color: black;')
        self.choose_file_button.move(900, 360)

        self.search_bar = QLineEdit(self)
        self.search_bar.move(80, 20)
        self.search_bar.resize(200, 32)

        self.search_bar.textChanged.connect(self.update_filter)

        # layout = QGridLayout(self)
        #
        # labels = []
        # count = 0
        # for file in os.listdir('test_img'):
        #     if (file.endswith('.jpg')):
        #         count += 1
        #         label = QLabel()
        #         pmap = QPixmap(file)
        #         pmap = pmap.scaled(150, 150, Qt.KeepAspectRatio, Qt.FastTransformation)
        #         label.setPixmap(pmap)
        #         labels.append(label)
        #
        # x = 0
        # y = 0
        # for label in labels:
        #     layout.addWidget(label, x, y)
        #     y += 1
        #
        # widget = QWidget()
        # widget.setLayout(layout)
        # self.setCentralWidget(widget)

        self.setWindowTitle("StudiOCR")

        self.choose_file_button.clicked.connect(self.choose_file)

        self.showFullScreen()

    def choose_file(self):
        print("Button pressed")
        file_name = QFileDialog.getOpenFileName()
        filepath = file_name[0]
        print(filepath)

    def update_filter(self):
        print(self.search_bar.text())

class Notes_Grid(QWidget):
    def __init__(self):
        QWidget.__init__(self)

        # print(glob.glob('test_img/*.jpg'))
        #
        self.img1 = QPixmap('test_img/conv_props.jpg')
        self.img1 = self.img1.scaled(150, 150, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        # self.img2 = QPixmap('test_img/handwritten_notes.jpg')
        # self.img2 = self.img2.scaled(150, 150, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        #
        self.label1 = QLabel()
        self.label1.setPixmap(self.img1)
        #
        # self.label2 = QLabel()
        # self.label2.setPixmap(self.img2)
        #
        # self.grid = QGridLayout()
        # self.grid.addWidget(self.label1, 0, 0)
        # self.grid.addWidget(self.label2, 0, 1)
        #
        # self.setLayout(self.grid)

        self.vbox = QVBoxLayout(self)
        self.vbox.addWidget(self.label1)

        self.button = QPushButton('conv_props')
        self.vbox.addWidget(self.button)

        self.setLayout(self.vbox)

        self.setWindowTitle("Photo Grid")

    def show_image(self):


if __name__ == "__main__":
    main()
