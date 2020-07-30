from collections import OrderedDict

from PySide2 import QtCore as Qc
from PySide2 import QtWidgets as Qw
from PySide2 import QtGui as Qg

import img2pdf

from StudiOCR.util import get_absolute_path
from StudiOCR.db import (db, OcrDocument, OcrPage, OcrBlock, create_tables)
from StudiOCR.PhotoViewer import PhotoViewer
from StudiOCR.EditDocWindow import EditDocWindow


class DocWindow(Qw.QDialog):
    """
    Document Window for when the user is searching in a specific document
    """

    def __init__(self, doc, parent=None, filter=''):
        """
        Constructor method
        :param doc: OCRDocument
        :param filter: Filter from main window
        """
        super().__init__(parent=parent)
        db.connect(reuse_if_open=True)
        self.setWindowTitle(doc.name)

        desktop = Qw.QDesktopWidget()
        desktop_size = desktop.availableGeometry(
            desktop.primaryScreen()).size()
        self.resize(desktop_size.width() * 0.3, desktop_size.height() * 0.6)

        self._doc = doc
        self._filter = filter
        self._curr_page = 0
        self._pages = self._doc.pages
        self._pages_len = len(self._pages)
        # Store key as page index, value as list of blocks
        self._filtered_page_indexes = OrderedDict()

        self._layout = Qw.QVBoxLayout()

        self._options = Qw.QHBoxLayout()

        self.search_bar = Qw.QLineEdit()
        self.search_bar.setPlaceholderText("Search through notes...")
        self.search_bar.textChanged.connect(self.update_filter)

        self.case_sens_button = Qw.QRadioButton(
            "Case Sensitive", parent=self)
        self.case_sens_button.toggled.connect(self.update_filter)

        self.filter_mode = Qw.QPushButton(
            "Show matching pages", default=False, autoDefault=False, parent=self)
        self.filter_mode.setCheckable(True)
        self.filter_mode.toggled.connect(self.set_filter_mode)

        self._options.addWidget(self.search_bar, alignment=Qc.Qt.AlignTop)
        self._options.addWidget(self.case_sens_button)
        self._options.addWidget(self.filter_mode, alignment=Qc.Qt.AlignTop)
        self._layout.addLayout(self._options, alignment=Qc.Qt.AlignTop)

        # create button group for prev and next page buttons
        self.next_page_button = Qw.QPushButton(
            "Next Page", default=False, autoDefault=False, parent=self)
        self.next_page_button.setSizePolicy(
            Qw.QSizePolicy.MinimumExpanding, Qw.QSizePolicy.Fixed)
        self.next_page_button.clicked.connect(self.next_page)
        self.prev_page_button = Qw.QPushButton(
            "Previous Page", default=False, autoDefault=False, parent=self)
        self.prev_page_button.setSizePolicy(
            Qw.QSizePolicy.MinimumExpanding, Qw.QSizePolicy.Fixed)
        self.prev_page_button.clicked.connect(self.prev_page)

        self.page_number_box = Qw.QLineEdit(parent=self)
        self.page_number_box.setSizePolicy(
            Qw.QSizePolicy.Minimum, Qw.QSizePolicy.Fixed)
        self.page_number_box.setInputMask("0" * len(str(self._pages_len)))
        self.page_number_box.setFixedWidth(
            self.page_number_box.fontMetrics().boundingRect(str(self._pages_len)).width() + 20)
        self.page_number_box.editingFinished.connect(
            lambda: self.jump_to_page(int(self.page_number_box.text())-1))

        # Added viewer
        self.viewer = PhotoViewer(parent=self)
        self._layout.addWidget(self.viewer)

        self.info_button = Qw.QPushButton(
            default=False, autoDefault=False, parent=self)
        self.info_button.setIcon(
            Qg.QIcon(get_absolute_path("icons/info_icon.png")))
        self.info_button.clicked.connect(self.display_info)

        self.export_button = Qw.QPushButton(
            "Export as PDF", default=False, autoDefault=False, parent=self)
        self.export_button.clicked.connect(self.export_pdf)

        self.add_pages_button = Qw.QPushButton(
            "Add pages", default=False, autoDefault=False, parent=self)
        self.add_pages_button.clicked.connect(
            lambda: self.add_pages(self._doc))

        self._button_group = Qw.QHBoxLayout()
        self._button_group.addWidget(self.add_pages_button)
        self._button_group.addWidget(self.prev_page_button)
        self._button_group.addWidget(self.page_number_box)
        self._button_group.addWidget(self.next_page_button)
        self._button_group.addWidget(self.export_button)
        self._button_group.addWidget(self.info_button)
        self._layout.addLayout(self._button_group)

        self.setLayout(self._layout)

        # if filter passed through from main window, set the search bar text and update window
        if self._filter:
            self.search_bar.setText(self._filter)
            self.update_filter()
        self.jump_to_page(0)

        db.close()

    def add_pages(self, doc):
        # TODO: Refactor. This is disgusting
        new_doc_cb = self.parentWidget().new_doc_cb
        self.edit_doc_window = EditDocWindow(
            new_doc_cb, doc=doc, parent=self)
        self.edit_doc_window.show()

    def export_pdf(self):

        # Bug in qdarkstyle that makes dropdowns too large, so we need to add styles
        dropdown_style = """QComboBox::item:checked {
                height: 12px;
                border: 1px solid #32414B;
                margin-top: 0px;
                margin-bottom: 0px;
                padding: 4px;
                padding-left: 0px;
                }"""

        file_dialog = Qw.QFileDialog()
        file_dialog.setStyleSheet(dropdown_style)
        file_dialog.setFileMode(Qw.QFileDialog.AnyFile)
        file_dialog.setAcceptMode(Qw.QFileDialog.AcceptSave)
        file_dialog.setNameFilters([
            "PDF File (*.pdf)"])
        file_dialog.selectNameFilter("PDF File (*.pdf)")
        file_dialog.setDefaultSuffix("pdf")

        if file_dialog.exec_():
            file = file_dialog.selectedFiles()[0]
            imgs = []
            for page in self._pages:
                imgs.append(page.image)

            with open(file, "wb") as f:
                f.write(img2pdf.convert(imgs))

    def display_info(self):
        """
        When the information button is pressed, this window spawns with the information about the new
        document options
        """
        text_file = Qw.QTextBrowser()
        text = open(get_absolute_path("information_doc_window.txt")).read()
        text_file.setText(text)
        dialog = Qw.QDialog(parent=self)

        desktop = Qw.QDesktopWidget()
        desktop_size = desktop.availableGeometry(
            desktop.primaryScreen()).size()
        dialog.resize(desktop_size.width() * 0.2, desktop_size.height() * 0.4)

        temp_layout = Qw.QHBoxLayout()
        temp_layout.addWidget(text_file)
        dialog.setWindowTitle("Doc Window Information")
        dialog.setLayout(temp_layout)
        dialog.show()

    def update_image(self):
        db.connect(reuse_if_open=True)
        # if there is no search criteria, display original image of current page
        if not self._filter or self._curr_page not in self._filtered_page_indexes.keys():
            img = Qg.QImage.fromData(self._pages[self._curr_page].image)
            self._pixmap = Qg.QPixmap.fromImage(img)
            self.viewer.setPhoto(self._pixmap)
        else:
            # for each block containing the search criteria, draw rectangles on the image
            block_list = self._filtered_page_indexes[self._curr_page]
            img = Qg.QImage.fromData(self._pages[self._curr_page].image)
            self._pixmap = Qg.QPixmap.fromImage(img)
            for block in block_list:
                # set color of rectangle based on confidence level of OCR
                if block.conf >= 80:
                    color = Qc.Qt.green
                elif (block.conf < 80 and block.conf >= 40):
                    color = Qc.Qt.blue
                else:
                    color = Qc.Qt.red
                painter = Qg.QPainter(self._pixmap)
                painter.setPen(Qg.QPen(color, 3, Qc.Qt.SolidLine))
                painter.drawRect(block.left, block.top,
                                 block.width, block.height)
                painter.end()

            self.viewer.setPhoto(self._pixmap)
        db.close()

    def set_filter_mode(self):
        if self.filter_mode.isChecked():
            self.filter_mode.setText("Show all pages")
            self.next_page_button.setText("Next Page containing search")
            self.prev_page_button.setText("Previous Page containing search")
            # if not already on page, then jump to the first page which matches search
            self.jump_first_matched_page()
        else:
            self.filter_mode.setText("Show matching pages")
            self.next_page_button.setText("Next Page")
            self.prev_page_button.setText("Previous Page")

    def jump_to_page(self, page_num: int):
        self.page_number_box.blockSignals(True)
        if page_num < self._pages_len and page_num >= 0:
            self._curr_page = page_num
            self.page_number_box.setText(str(self._curr_page+1))
            self.update_image()
        else:
            self.page_number_box.setText(str(self._curr_page+1))
        self.page_number_box.blockSignals(False)

    def next_page(self):
        """
        Increment the current page number if the next page button is pressed.
        If in filter mode, will go to next page containing the filter in the search bar
        """
        # if we are in the mode to only display pages that match filter, then iterate through  self._filtered_page_indexes
        if self.filter_mode.isChecked():
            # if nothing matches the filter, then do nothing
            if len(self._filtered_page_indexes) == 0:
                return
            # if not on last page, then find next page
            key_list = list(self._filtered_page_indexes.keys())
            if self._curr_page != key_list[len(key_list)-1]:
                # find the index of the tuple whose page we are currently on, and set it to that + 1
                for index, page_number in enumerate(key_list):
                    if page_number == self._curr_page:
                        break
                self.jump_to_page(key_list[index + 1])
        # otherwise, perform as normal
        else:
            # if not at end, then go forward a page
            if self._curr_page + 1 < self._pages_len:
                self.jump_to_page(self._curr_page + 1)

    def prev_page(self):
        """
        Decrement the current page number if the next page button is pressed.
        If in filter mode, will go to previous page containing filter in the search bar
        """
        # if we are in the mode to only display pages that match filter, then iterate through  self._filteredPageIndexes
        if self.filter_mode.isChecked():
            # if nothing matches the filter, then do nothing
            if len(self._filtered_page_indexes) == 0:
                return
            # if not on last page, then find next page
            key_list = list(self._filtered_page_indexes.keys())
            if self._curr_page != key_list[0]:
                # find the index of the tuple whose page we are currently on, and set it to that + 1
                for index, page_number in enumerate(key_list):
                    if page_number == self._curr_page:
                        break
                self.jump_to_page(key_list[index - 1])
        # otherwise, perform as normal
        else:
            # go not at beginning, then go back a page
            if self._curr_page > 0:
                self.jump_to_page(self._curr_page - 1)

    def update_filter(self):
        """
        Updates the filter criteria as the text in the search bar changes
        """
        self._filter = self.search_bar.text()
        self.exec_filter()
        self.update_image()
        # if in matching pages mode, jump to the first page that was matched if not already on matched page
        if self.filter_mode.isChecked():
            self.jump_first_matched_page()

    def jump_first_matched_page(self):
        """
        Jump to the first matched page if there are matches and not currently on a matched page,
        otherwise do nothing
        """
        if len(self._filtered_page_indexes) != 0 and self._curr_page not in self._filtered_page_indexes.keys():
            self.jump_to_page(list(self._filtered_page_indexes.keys())[0])

    def exec_filter(self):
        """
        Performs filtering operations, populating self._filtered_page_indexes
        """
        # clear self._filtered_page_indexes
        self._filtered_page_indexes = OrderedDict()
        # if there is search critera, then perform filtering
        if self._filter:
            db.connect(reuse_if_open=True)
            # search each block in the current page to see if it contains the search criteria (filter)
            if self.case_sens_button.isChecked():
                words = self._filter.split()
            else:
                words = self._filter.lower().split()
            for page_index, page in enumerate(self._pages):
                matched_blocks = []
                for block in page.blocks:
                    if self.case_sens_button.isChecked():
                        text = block.text
                    else:
                        text = block.text.lower()
                    # if the filter value is contained in the block text, add block to list
                    for word in words:
                        if word in text:
                            matched_blocks.append(block)
                if len(matched_blocks) != 0:
                    self._filtered_page_indexes[page_index] = matched_blocks
            db.close()
