from PySide6.QtCore import QPoint, QRect, Qt, QTimer, Signal
from PySide6.QtGui import QGuiApplication, QPainter
from PySide6.QtWidgets import QMenu

from .. import config
from .common import OverlayWindow, screen_at
from .theme import svg_pixmap

SIZE = 58
MARGIN = 6


def place(right: bool, yfrac: float, avail: QRect) -> QPoint:
    yfrac = min(1.0, max(0.0, yfrac))
    x = avail.right() - SIZE - MARGIN + 1 if right else avail.left() + MARGIN
    top = avail.top() + MARGIN
    bottom = max(top, avail.bottom() - SIZE - MARGIN + 1)
    return QPoint(x, int(top + (bottom - top) * yfrac))


def to_relative(pos: QPoint, avail: QRect):
    right = pos.x() + SIZE / 2 >= avail.center().x()
    top = avail.top() + MARGIN
    bottom = max(top, avail.bottom() - SIZE - MARGIN + 1)
    frac = 0.0 if bottom == top else (pos.y() - top) / (bottom - top)
    return right, min(1.0, max(0.0, frac))


class Bubble(OverlayWindow):
    clicked = Signal()
    menu_requested = Signal(QPoint)

    def __init__(self):
        super().__init__(pinned=True)
        self.setFixedSize(SIZE, SIZE)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("Fishyu Translate\nChuột trái: khoanh vùng dịch\nChuột phải: menu")
        self._pm = svg_pixmap("bubble.svg", SIZE - 6)
        self._press = None
        self._start = None
        self._moved = False
        QGuiApplication.instance().screenAdded.connect(lambda *_: QTimer.singleShot(300, self.restore_position))
        QGuiApplication.instance().screenRemoved.connect(lambda *_: QTimer.singleShot(300, self.restore_position))
        QGuiApplication.primaryScreen().geometryChanged.connect(lambda *_: QTimer.singleShot(300, self.restore_position))

    def paintEvent(self, e):
        p = QPainter(self)
        p.setOpacity(0.96)
        p.drawPixmap(3, 3, self._pm)
        p.end()

    def restore_position(self):
        st = config.get()
        screens = QGuiApplication.screens()
        scr = None
        name = right = frac = None
        if isinstance(st.bubble_pos, list) and len(st.bubble_pos) == 3:
            name, right, frac = st.bubble_pos
            scr = next((s for s in screens if s.name() == name), None)
        if scr is None:
            scr = QGuiApplication.primaryScreen()
            right, frac = True, 0.35
        self.move(place(bool(right), float(frac), scr.availableGeometry()))

    def _save(self):
        scr = screen_at(self.geometry().center())
        right, frac = to_relative(self.pos(), scr.availableGeometry())
        config.get().bubble_pos = [scr.name(), right, frac]
        config.save()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._press = e.globalPosition().toPoint()
            self._start = self.pos()
            self._moved = False
        elif e.button() == Qt.RightButton:
            self.menu_requested.emit(e.globalPosition().toPoint())

    def mouseMoveEvent(self, e):
        if self._press is None:
            return
        d = e.globalPosition().toPoint() - self._press
        if not self._moved and d.manhattanLength() > 6:
            self._moved = True
        if self._moved:
            self.move(self._start + d)

    def mouseReleaseEvent(self, e):
        if e.button() != Qt.LeftButton or self._press is None:
            return
        self._press = None
        if self._moved:
            scr = screen_at(self.geometry().center())
            right, frac = to_relative(self.pos(), scr.availableGeometry())
            self.move(place(right, frac, scr.availableGeometry()))
            self._save()
        else:
            self.clicked.emit()


def build_menu(parent, items):
    m = QMenu(parent)
    m.setWindowFlag(Qt.WindowStaysOnTopHint, True)
    for it in items:
        if it is None:
            m.addSeparator()
        else:
            text, fn = it
            m.addAction(text, fn)
    return m
