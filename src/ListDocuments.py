from PySide2 import QtCore as Qc
from PySide2 import QtWidgets as Qw
from PySide2 import QtGui as Qg

from db import (db, OcrDocument, OcrPage, OcrBlock, create_tables)
from DocWindow import DocWindow
from NewDocWindow import NewDocWindow


class ListDocuments(Qw.QWidget):
    """
    Contains methods for interacting with list of documents: removal, addition, displaying
    """

    def __init__(self, new_doc_cb, *args, **kwargs):
        super().__init__(*args, **kwargs)

        db.connect(reuse_if_open=True)

        self._filter = ''

        self.new_doc_cb = new_doc_cb

        self.setSizePolicy(
            Qw.QSizePolicy.MinimumExpanding,
            Qw.QSizePolicy.MinimumExpanding
        )

        self._layout = Qw.QVBoxLayout()

        self.doc_grid = Qw.QGridLayout()
        self.scroll_area = Qw.QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.ui_box = Qw.QHBoxLayout()

        self._docButtons = []

        self.search_bar = Qw.QLineEdit()
        self.search_bar.setPlaceholderText("Search for document name...")
        self.search_bar.textChanged.connect(self.update_filter)

        self.doc_search = Qw.QRadioButton("DOC")
        self.doc_search.setChecked(True)
        self.ocr_search = Qw.QRadioButton("OCR")

        self.remove_mode = Qw.QPushButton("Enable remove mode")
        self.remove_mode.setCheckable(True)
        self.remove_mode.toggled.connect(self.set_remove_mode)

        self.ui_box.addWidget(self.doc_search)
        self.ui_box.addWidget(self.ocr_search)
        self.ui_box.addWidget(self.search_bar)
        self.ui_box.addWidget(self.remove_mode)
        # produces the document buttons that users can interact with
        for doc in OcrDocument.select():
            # assuming that each doc will surely have at least one page
            img = doc.pages[0].image
            name = doc.name

            doc_button = SingleDocumentButton(name, img, doc)
            doc_button.pressed.connect(
                lambda doc=doc: self.create_doc_window(doc))
            doc_button.setVisible(True)
            self._docButtons.append(doc_button)

        self.new_doc_button = SingleDocumentButton(
            'Add New Document', None, None)
        self.new_doc_button.pressed.connect(
            lambda: self.create_new_doc_window())

        self._active_docs = self._docButtons

        self.render_doc_grid()

        self._layout.addLayout(self.ui_box)
        self._layout.addWidget(self.scroll_area)

        self.setLayout(self._layout)
        db.close()

    def set_remove_mode(self):
        if self.remove_mode.isChecked():
            self.remove_mode.setText("Disable remove mode")
        else:
            self.remove_mode.setText("Enable remove mode")
        self.render_doc_grid()

    def render_doc_grid(self):
        # clear the doc_grid, not deleting widgets since they will be used later for repopulation
        while self.doc_grid.count():
            # must make the removed widget a child of the class, so that it does not get garbage collected
            self.doc_grid.takeAt(0).widget().setParent(self)
        # repopulate the doc_grid
        idx = 0
        # hide the new document button if remove mode is enabled
        if not self.remove_mode.isChecked():
            self.doc_grid.addWidget(
                self.new_doc_button, idx / 4, idx % 4, 1, 1)
            idx += 1
        self._active_docs.sort(key=lambda button: button.name.lower())
        for button in self._active_docs:
            self.doc_grid.addWidget(button, idx / 4, idx % 4, 1, 1)
            idx += 1
        temp_widget = Qw.QWidget()
        temp_widget.setLayout(self.doc_grid)
        self.scroll_area.setWidget(temp_widget)

    @Qc.Slot(int)
    def display_new_document(self, doc_id):
        db.connect(reuse_if_open=True)
        doc = OcrDocument.get(OcrDocument.id == doc_id)
        # assuming that each doc will surely have at least one page
        doc_button = SingleDocumentButton(doc.name, doc.pages[0].image, doc)
        doc_button.pressed.connect(
            lambda doc=doc: self.create_doc_window(doc))
        self._docButtons.append(doc_button)
        self.render_doc_grid()
        db.close()

    def create_doc_window(self, doc):
        db.connect(reuse_if_open=True)
        # If remove mode is checked, then prompt and remove the document
        if self.remove_mode.isChecked():
            confirm = Qw.QMessageBox()
            confirm.setWindowTitle(f"Remove Document: {doc.name}")
            confirm.setText(
                f"Are you sure you want to delete document: {doc.name}?")
            confirm.setIcon(Qw.QMessageBox.Question)
            confirm.setStandardButtons(Qw.QMessageBox.Yes)
            confirm.addButton(Qw.QMessageBox.No)
            confirm.setDefaultButton(Qw.QMessageBox.No)
            if confirm.exec_() == Qw.QMessageBox.Yes:
                button_to_remove = None
                for button in self._docButtons:
                    if button.doc == doc:
                        button_to_remove = button
                        break
                self.doc_grid.removeWidget(button_to_remove)
                self._docButtons.remove(button_to_remove)
                self.update_filter()
                db.connect(reuse_if_open=True)
                print(doc.delete_document())
                db.close()
        else:
            if self.ocr_search.isChecked():
                self.doc_window = DocWindow(doc, self._filter)
            else:
                self.doc_window = DocWindow(doc)
            self.doc_window.show()

    def create_new_doc_window(self):
        self.new_doc_window = NewDocWindow(self.new_doc_cb)
        self.new_doc_window.show()

    def update_filter(self):
        db.connect(reuse_if_open=True)
        self._filter = self.search_bar.text()

        self._active_docs = []
        if(self.doc_search.isChecked()):
            for button in self._docButtons:
                if(self._filter.lower() in button.name.lower()):
                    self._active_docs.append(button)
        elif(self.ocr_search.isChecked()):
            for button in self._docButtons:
                text_found = False
                for page in button.doc.pages:
                    for block in page.blocks:
                        if(self._filter.lower() in block.text.lower()):
                            if(not text_found):
                                self._active_docs.append(button)
                                text_found = True
                                break
        db.close()
        self.render_doc_grid()


class SingleDocumentButton(Qw.QToolButton):
    """
    Custom Button Class for Document Button which has a thumbnail of the first page
    """

    def __init__(self, name, image, doc, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._name = name
        self._doc = doc

        self.setFixedSize(160, 160)

        layout = Qw.QVBoxLayout()

        label = Qw.QLabel(name)
        if image is not None:
            thumbnail = DocumentThumbnail(image)
            layout.addWidget(thumbnail, alignment=Qc.Qt.AlignCenter)

        layout.addWidget(label, alignment=Qc.Qt.AlignCenter)

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


class DocumentThumbnail(Qw.QLabel):
    """
    Class for creating the pixmap from page.imageblobdata
    """

    def __init__(self, image, *args, **kwargs):
        super().__init__(*args, **kwargs)
        qimg = Qg.QImage.fromData(image)
        self.pixmap = Qg.QPixmap.fromImage(qimg)

        self.setPixmap(self.pixmap.scaled(
            self.size(), Qc.Qt.KeepAspectRatio, Qc.Qt.SmoothTransformation))

    def resizeEvent(self, e: Qg.QResizeEvent):
        self.setPixmap(self.pixmap.scaled(
            self.size(), Qc.Qt.KeepAspectRatio, Qc.Qt.SmoothTransformation))
        super().resizeEvent(e)
