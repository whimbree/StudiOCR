from collections import OrderedDict

from PySide2 import QtCore as Qc
from PySide2 import QtWidgets as Qw
from PySide2 import QtGui as Qg

from db import (db, OcrDocument, OcrPage, OcrBlock, create_tables)


class DocWindow(Qw.QDialog):
    """
    Document Window for when the user is searching in a specific document
    """

    def __init__(self, doc, parent=None, filter='', *args, **kwargs):
        """
        Constructor method
        :param doc: OCRDocument
        :param filter: Filter from main window
        """
        super().__init__(parent=parent, *args, **kwargs)
        db.connect(reuse_if_open=True)
        self.setWindowTitle(doc.name)

        desktop = Qw.QDesktopWidget()
        desktop_size = desktop.availableGeometry(
            desktop.primaryScreen()).size()
        self.resize(desktop_size.width() * 0.3, desktop_size.height() * 0.6)

        self._doc = doc
        self._filter = filter
        self._currPage = 0
        self._pages = self._doc.pages
        self._pages_len = len(self._pages)
        # Store key as page index, value as list of blocks
        self._filtered_page_indexes = OrderedDict()

        self._layout = Qw.QVBoxLayout()

        self._options = Qw.QHBoxLayout()

        self.search_bar = Qw.QLineEdit()
        self.search_bar.setPlaceholderText("Search through notes...")
        self.search_bar.textChanged.connect(self.update_filter)

        self.filter_mode = Qw.QPushButton("Show matching pages")
        self.filter_mode.setCheckable(True)
        self.filter_mode.toggled.connect(self.set_filter_mode)

        self._options.addWidget(self.search_bar, alignment=Qc.Qt.AlignTop)
        self._options.addWidget(self.filter_mode, alignment=Qc.Qt.AlignTop)
        self._layout.addLayout(self._options, alignment=Qc.Qt.AlignTop)

        self._pixmap = Qg.QPixmap()
        self._label_height_offset = 100
        self._label_width_offset = 40

        self.label = Qw.QLabel()
        # if filter passed through from main window, set the search bar text and update window
        if self._filter:
            self.search_bar.setText(self._filter)
            self.update_filter()
        # display original image of first page
        else:
            self.update_image()
        self._layout.addWidget(self.label, alignment=Qc.Qt.AlignCenter)

        # create button group for prev and next page buttons
        self.next_page_button = Qw.QPushButton("Next Page")
        self.next_page_button.setSizePolicy(
            Qw.QSizePolicy.MinimumExpanding, Qw.QSizePolicy.Fixed)
        self.next_page_button.clicked.connect(self.next_page)
        self.prev_page_button = Qw.QPushButton("Previous Page")
        self.prev_page_button.setSizePolicy(
            Qw.QSizePolicy.MinimumExpanding, Qw.QSizePolicy.Fixed)
        self.prev_page_button.clicked.connect(self.prev_page)
        self.page_number_label = Qw.QLabel(str(self._currPage+1))
        self._button_group = Qw.QHBoxLayout()
        self._button_group.addWidget(self.prev_page_button)
        self._button_group.addWidget(self.page_number_label)
        self._button_group.addWidget(self.next_page_button)

        self._layout.addLayout(self._button_group)
        self.setLayout(self._layout)
        db.close()

    def resizeEvent(self, e):
        pixmap_scaled = self._pixmap.scaled(
            self.width() - self._label_width_offset, self.height() - self._label_height_offset,
            Qc.Qt.KeepAspectRatio, Qc.Qt.SmoothTransformation)
        self.label.setPixmap(pixmap_scaled)
        self.label.setSizePolicy(
            Qw.QSizePolicy.Preferred, Qw.QSizePolicy.Preferred)
        super().resizeEvent(e)

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

    def next_page(self):
        """
        Increment the current page number if the next page button is pressed.
        If current page is the last page, the page will not increment
        :return: NONE
        """
        # if we are in the mode to only display pages that match filter, then iterate through  self._filteredPageIndexes
        if self.filter_mode.isChecked():
            # if nothing matches the filter, then do nothing
            if len(self._filtered_page_indexes) == 0:
                return
            # if not on last page, then find next page
            key_list = list(self._filtered_page_indexes.keys())
            if self._currPage != key_list[len(key_list)-1]:
                # find the index of the tuple whose page we are currently on, and set it to that + 1
                for index, page_number in enumerate(key_list):
                    if page_number == self._currPage:
                        break
                self._currPage = key_list[index + 1]
                self.page_number_label.setText(str(self._currPage+1))
                self.update_image()
        # otherwise, perform as normal
        else:
            # if not at end, then go forward a page
            if self._currPage + 1 != self._pages_len:
                self._currPage += 1
                self.page_number_label.setText(str(self._currPage+1))
            self.update_image()

    def prev_page(self):
        """
        Decrement the current page number if the next page button is pressed.
        If current page is the first page, the page will not decrement
        :return: NONE
        """
        # if we are in the mode to only display pages that match filter, then iterate through  self._filteredPageIndexes
        if self.filter_mode.isChecked():
            # if nothing matches the filter, then do nothing
            if len(self._filtered_page_indexes) == 0:
                return
            # if not on last page, then find next page
            key_list = list(self._filtered_page_indexes.keys())
            if self._currPage != key_list[0]:
                # find the index of the tuple whose page we are currently on, and set it to that + 1
                for index, page_number in enumerate(key_list):
                    if page_number == self._currPage:
                        break
                self._currPage = key_list[index - 1]
                self.page_number_label.setText(str(self._currPage+1))
                self.update_image()
        # otherwise, perform as normal
        else:
            # go not at beginning, then go back a page
            if self._currPage != 0:
                self._currPage -= 1
                self.page_number_label.setText(str(self._currPage+1))
            self.update_image()

    def update_filter(self):
        """
        Updates the filter criteria as the text in the search bar changes
        :return: NONE
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
        :return: NONE
        """
        if len(self._filtered_page_indexes) != 0 and self._currPage not in self._filtered_page_indexes.keys():
            self._currPage = list(self._filtered_page_indexes.keys())[0]
            self.page_number_label.setText(str(self._currPage+1))
            self.update_image()

    def exec_filter(self):
        """
        Performs filtering operations, populating self._filtered_page_indexes
        :return: NONE
        """
        # clear self._filtered_page_indexes
        self._filtered_page_indexes = OrderedDict()
        # if there is search critera, then perform filtering
        if self._filter:
            db.connect(reuse_if_open=True)
            # search each block in the current page to see if it contains the search criteria (filter)
            words = self._filter.lower().split()
            for page_index, page in enumerate(self._pages):
                matched_blocks = []
                for block in page.blocks:
                    text = block.text.lower()
                    # if the filter value is contained in the block text, add block to list
                    for word in words:
                        if word in text:
                            matched_blocks.append(block)
                if len(matched_blocks) != 0:
                    self._filtered_page_indexes[page_index] = matched_blocks
            db.close()

    def update_image(self):
        """
        Function that updates the rectangles on the image based on self._currPage and self._filtered_page_indexes
        :return: NONE
        """
        db.connect(reuse_if_open=True)
        # if there is no search criteria, display original image of current page
        if not self._filter or self._currPage not in self._filtered_page_indexes.keys():
            img = Qg.QImage.fromData(self._pages[self._currPage].image)
            self._pixmap = Qg.QPixmap.fromImage(img)
            pixmap_scaled = self._pixmap.scaled(self.width() - self._label_width_offset, self.height() - self._label_height_offset,
                                                Qc.Qt.KeepAspectRatio, Qc.Qt.SmoothTransformation)
            self.label.setPixmap(pixmap_scaled)
        else:
            # for each block containing the search criteria, draw rectangles on the image
            block_list = self._filtered_page_indexes[self._currPage]
            img = Qg.QImage.fromData(self._pages[self._currPage].image)
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

            pixmap_scaled = self._pixmap.scaled(self.width() - self._label_width_offset, self.height() - self._label_height_offset,
                                                Qc.Qt.KeepAspectRatio, Qc.Qt.SmoothTransformation)
            self.label.setPixmap(pixmap_scaled)
        db.close()
