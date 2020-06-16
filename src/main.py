from PySide2.QtCore import Slot, Qt
import sys
import wsl
import random
from PySide2.QtWidgets import QApplication, QLabel, QPushButton, QVBoxLayout, QWidget

# References
# https://doc.qt.io/qtforpython/


def main():
    # Set DISPLAY env variable accordingly if running under WSL
    wsl.set_display_to_host()

    app = QApplication(sys.argv)  # Create application

    widget = HelloWidget()  # Create widget
    widget.show()  # Show widget

    app.exec_()  # Start application

    exit(0)


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
