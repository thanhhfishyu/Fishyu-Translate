from PySide6.QtCore import QPoint, QRect, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QImage, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QWidget

from . import theme
from .common import overlays


class RegionSelector(QWidget):
    region = Signal(object, QRect)
    tapped = Signal(object, QPoint)
    second = Signal(object)
    cancelled = Signal()

    is_selector = True

    def __init__(self, screen, image: QImage, hint: str, second_label: str):
        super().__init__(None, Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint)
        self.pinned = True
        self.screen_ = screen
        self.image = image
        self.pm = QPixmap.fromImage(image)
        self.hint = hint
        self.second_label = second_label
        self.status = None
        self.busy = False
        self._a = self._b = None
        self._drag = False
        self.cancel_btn = QRectF()
        self.second_btn = QRectF()
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        self.setCursor(Qt.CrossCursor)
        self.setMouseTracking(True)
        self.setGeometry(screen.geometry())
        overlays().register(self)

    def showEvent(self, e):
        super().showEvent(e)
        overlays().on_shown(self, noactivate=False)
        self.activateWindow()
        self.raise_()
        self.setFocus()

    def set_busy(self, msg):
        self.busy = True
        self.status = msg
        self.setCursor(Qt.WaitCursor)
        self.update()

    def sel_rect(self):
        if self._a is None or self._b is None or not self._drag:
            return None
        return QRect(self._a, self._b).normalized()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.drawPixmap(self.rect(), self.pm)
        dim = QColor(10, 20, 35, 120)
        sel = self.sel_rect()
        if sel:
            path = QPainterPath()
            path.addRect(QRectF(self.rect()))
            inner = QPainterPath()
            inner.addRect(QRectF(sel))
            p.fillPath(path.subtracted(inner), dim)
            pen = QPen(theme.ACCENT, 2.5, Qt.DashLine)
            p.setPen(pen)
            p.drawRect(sel)
            p.setFont(theme.body_font(12))
            p.setPen(Qt.white)
            p.drawText(sel.bottomRight() + QPoint(-70, 18), f"{sel.width()} x {sel.height()}")
        else:
            p.fillRect(self.rect(), dim)
        msg = self.status or self.hint
        f = theme.head_font(16, theme.QFont.DemiBold)
        p.setFont(f)
        tw = p.fontMetrics().horizontalAdvance(msg) + 36
        pill = QRectF(self.width() / 2 - tw / 2, 40, tw, 42)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(30, 42, 56, 235))
        p.drawRoundedRect(pill, 21, 21)
        p.setPen(Qt.white)
        p.drawText(pill, Qt.AlignCenter, msg)
        if not self.busy:
            bw, bh, gap = 150, 44, 16
            y = self.height() - 110
            cx = self.width() / 2
            self.cancel_btn = QRectF(cx - bw - gap / 2, y, bw, bh)
            self.second_btn = QRectF(cx + gap / 2, y, bw, bh)
            theme.paint_doodle(p, self.cancel_btn, theme.BG, 16, 3)
            theme.paint_doodle(p, self.second_btn, theme.ACCENT, 16, 3)
            p.setFont(theme.head_font(15))
            p.setPen(theme.FG)
            p.drawText(self.cancel_btn.adjusted(0, 0, -3, -3), Qt.AlignCenter, "Huỷ (Esc)")
            p.setPen(Qt.white)
            p.drawText(self.second_btn.adjusted(0, 0, -3, -3), Qt.AlignCenter, self.second_label)
        p.end()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.cancelled.emit()

    def mousePressEvent(self, e):
        if self.busy:
            return
        if e.button() == Qt.RightButton:
            self.cancelled.emit()
            return
        if e.button() == Qt.LeftButton:
            self._a = self._b = e.position().toPoint()
            self._drag = False

    def mouseMoveEvent(self, e):
        if self.busy or self._a is None:
            return
        self._b = e.position().toPoint()
        if (self._b - self._a).manhattanLength() > 8:
            self._drag = True
        if self._drag:
            self.update()

    def mouseReleaseEvent(self, e):
        if self.busy or e.button() != Qt.LeftButton or self._a is None:
            return
        pos = e.position()
        sel = self.sel_rect()
        self._a = None
        if sel is None:
            if self.cancel_btn.contains(pos):
                self.cancelled.emit()
            elif self.second_btn.contains(pos):
                self.second.emit(self)
            else:
                self.tapped.emit(self, pos.toPoint())
            return
        if sel.width() < 12 or sel.height() < 10:
            self._drag = False
            self.update()
            return
        self.region.emit(self, sel)

    def crop(self, local: QRect) -> QImage:
        k = self.image.width() / max(1, self.width())
        r = QRect(int(local.x() * k), int(local.y() * k), int(local.width() * k), int(local.height() * k))
        return self.image.copy(r.intersected(self.image.rect()))

    @property
    def scale(self):
        return self.image.width() / max(1, self.width())
