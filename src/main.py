from PySide2.QtCore import Slot, Qt
from PySide2.QtWidgets import QApplication, QLabel, QPushButton, QVBoxLayout, QWidget, QFileDialog
from PySide2.QtGui import QPixmap

import sys
import random

from db import *
import wsl

# References
# https://doc.qt.io/qtforpython/


def main():
    # Set DISPLAY env variable accordingly if running under WSL
    wsl.set_display_to_host()

    app = QApplication(sys.argv)  # Create application

    widget = Main_UI()  # Create widget
    widget.show()  # Show widget

    app.exec_()  # Start application

    exit(0)


class Main_UI(QWidget):
    def __init__(self):
        QWidget.__init__(self)

        self.choose_file_button = QPushButton("Choose file")

        self.label = QLabel(self)
        pixmap = QPixmap('test_img/conv_props.jpg')
        self.label.setPixmap(pixmap.scaled(256, 256, Qt.KeepAspectRatio))
        self.label.show()

        self.layout = QVBoxLayout()
        self.resize(300, 300)
        self.move(300, 300)
        self.setWindowTitle("StudiOCR")

        self.layout.addWidget(self.choose_file_button, alignment=Qt.AlignRight)

        self.setLayout(self.layout)

        self.choose_file_button.clicked.connect(self.choose_file)

    def choose_file(self):
        print("Button pressed")
        file_name = QFileDialog.getOpenFileName()
        filepath = file_name[0]
        print(filepath)


class file_browser(QWidget):
    def __init__(self):
        QWidget.__init__(self)

        self.button = QPushButton("Choose file")

        # Create and setup layout object
        self.layout = QVBoxLayout()
        self.layout.addWidget(self.button)

        # Apply layout
        self.setLayout(self.layout)

        # Connecting the signal from button
        self.button.clicked.connect(self.button_action)

    def button_action(self):
        print("Button pressed")
        self.open_fs()

    def open_fs(self):
        file = QFileDialog.getOpenFileName()
        filepath = file[0]
        print(filepath)


class HelloWidget(QWidget):
    def __init__(self):
        QWidget.__init__(self)

        self.hello = ["Hello, world!", "Goodbye, world!"]

        self.button = QPushButton("Click me!")
        self.text = QLabel(self.hello[0])
        self.text.setAlignment(Qt.AlignCenter)

        # Create and setup layout object
        self.layout = QVBoxLayout()
        self.layout.addWidget(self.text)
        self.layout.addWidget(self.button)

        # Apply layout
        self.setLayout(self.layout)

        # Connecting the signal from button
        self.button.clicked.connect(self.button_action)

    def button_action(self):
        self.text.setText(random.choice(self.hello))


if __name__ == "__main__":
    main()
