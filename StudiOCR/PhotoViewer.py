from PySide2 import QtCore as Qc
from PySide2 import QtWidgets as Qw
from PySide2 import QtGui as Qg

# PhotoViewer Code: https://stackoverflow.com/questions/35508711/how-to-enable-pan-and-zoom-in-a-qgraphicsview
class PhotoViewer(Qw.QGraphicsView):

    def __init__(self, parent):
        super(PhotoViewer, self).__init__(parent)
        self._zoom = 0
        self._zoom_in_factor = 1.15
        self._zoom_out_factor = 1/self._zoom_in_factor
        self._empty = True
        self._scene = Qw.QGraphicsScene(self)
        self._photo = Qw.QGraphicsPixmapItem()
        self._scene.addItem(self._photo)
        self.setScene(self._scene)
        self.setTransformationAnchor(Qw.QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(Qw.QGraphicsView.AnchorUnderMouse)
        self.setVerticalScrollBarPolicy(Qc.Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qc.Qt.ScrollBarAlwaysOff)
        self.setBackgroundBrush(Qg.QBrush(Qg.QColor(30, 30, 30)))
        self.setFrameShape(Qw.QFrame.NoFrame)

        self.pixmap = Qg.QPixmap()

    def hasPhoto(self):
        return not self._empty

    def fitInView(self, scale=True):
        rect = Qc.QRectF(self._photo.pixmap().rect())
        if not rect.isNull():
            self.setSceneRect(rect)
            if self.hasPhoto():
                unity = self.transform().mapRect(Qc.QRectF(0, 0, 1, 1))
                self.scale(1 / unity.width(), 1 / unity.height())
                viewrect = self.viewport().rect()
                scenerect = self.transform().mapRect(rect)
                factor = min(viewrect.width() / scenerect.width(),
                             viewrect.height() / scenerect.height())
                self.scale(factor, factor)
            self._zoom = 0

    def resizeEvent(self, e):
        old_zoom = self._zoom
        self.fitInView()
        self._zoom = old_zoom
        # Reapply the old zoom value
        for i in range(self._zoom):
            self.scale(self._zoom_in_factor, self._zoom_in_factor)

    def setPhoto(self, pixmap=None):
        self._zoom = 0
        if pixmap and not pixmap.isNull():
            self._empty = False
            self.setDragMode(Qw.QGraphicsView.ScrollHandDrag)
            self._photo.setPixmap(pixmap)
            self.pixmap = pixmap
        else:
            self._empty = True
            self.setDragMode(Qw.QGraphicsView.NoDrag)
            self._photo.setPixmap(Qg.QPixmap())
        self.fitInView()

    def wheelEvent(self, event):
        if self.hasPhoto():
            modifiers = Qw.QApplication.keyboardModifiers()
            if modifiers == Qc.Qt.ControlModifier:
                if event.angleDelta().y() > 0:
                    factor = self._zoom_in_factor
                    self._zoom += 1
                else:
                    factor = self._zoom_out_factor
                    self._zoom -= 1
                if self._zoom > 0:
                    self.scale(factor, factor)
                elif self._zoom == 0:
                    self.fitInView()
                else:
                    self._zoom = 0
    #reference for context menu: https://stackoverflow.com/questions/60210071/how-to-right-click-to-save-picture-or-file
    #reference for clipboard: https://stackoverflow.com/questions/17676373/python-matplotlib-pyqt-copy-image-to-clipboard
    def contextMenuEvent(self, event):
        cmenu = Qw.QMenu(self)
        copyClipboard = cmenu.addAction("Copy to Clipboard")
        action = cmenu.exec_(self.mapToGlobal(event.pos()))
        clipboard = Qw.QApplication.clipboard()
        if action == copyClipboard:
            #clipboard.clear(mode=clipboard.Clipboard )
            #clipboard.setPixmap((self._photo).pixmap())
            clipboard.setPixmap(self.pixmap)
        """
        saveAct = cmenu.addAction("Save as")
        action = cmenu.exec_(self.mapToGlobal(event.pos()))
        if action == saveAct:
            filename, _ = QFileDialog.getSaveFileName(self)
            pixmap = self.le.pixmap()
            if pixmap is not None and filename:
                pixmap.save(filename)
        """
