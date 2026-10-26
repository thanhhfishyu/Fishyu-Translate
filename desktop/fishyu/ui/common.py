import time
import weakref

import numpy as np
from PySide6.QtCore import QObject, QPoint, QRect, Qt, QTimer
from PySide6.QtGui import QGuiApplication, QImage
from PySide6.QtWidgets import QApplication, QWidget

from .. import sysapi


class _Overlays(QObject):
    def __init__(self):
        super().__init__()
        self._items = weakref.WeakSet()
        self.exclude_ok = None
        self._timer = QTimer(self)
        self._timer.setInterval(1500)
        self._timer.timeout.connect(self._keep_on_top)
        self._timer.start()

    def register(self, w: QWidget):
        self._items.add(w)

    def _keep_on_top(self):
        items = []
        for w in list(self._items):
            try:
                if w.isVisible() and getattr(w, "pinned", True):
                    items.append(w)
            except RuntimeError:
                pass
        selectors = [w for w in items if getattr(w, "is_selector", False)]
        for w in (selectors or items):
            try:
                sysapi.set_topmost(w, True)
            except RuntimeError:
                pass

    def on_shown(self, w: QWidget, noactivate: bool, click_through: bool = False):
        ok = sysapi.exclude_from_capture(w)
        if self.exclude_ok is None and sysapi.IS_WIN:
            self.exclude_ok = ok
        if noactivate:
            sysapi.set_noactivate(w, True)
        if click_through:
            sysapi.set_click_through(w, True)
        if getattr(w, "pinned", True):
            sysapi.set_topmost(w, True)

    def visible_rects(self):
        out = []
        for w in list(self._items):
            try:
                if w.isVisible() and not getattr(w, "no_mask", False) and not getattr(w, "is_selector", False):
                    out.append(QRect(w.mapToGlobal(QPoint(0, 0)), w.size()))
            except RuntimeError:
                pass
        return out

    def hide_all_for_capture(self):
        hidden = []
        if self.exclude_ok:
            return hidden
        mode = sysapi.hide_mode()
        for w in list(self._items):
            try:
                if w.isVisible() and not getattr(w, "is_selector", False) and not getattr(w, "no_mask", False):
                    if mode == "opacity":
                        w.setWindowOpacity(0.0)
                    else:
                        w.hide()
                    hidden.append(w)
            except RuntimeError:
                pass
        if hidden:
            QApplication.processEvents()
            time.sleep(0.12 if mode == "hide" else 0.06)
            QApplication.processEvents()
        return hidden

    @staticmethod
    def restore(hidden):
        mode = sysapi.hide_mode()
        for w in hidden:
            try:
                if mode == "opacity":
                    w.setWindowOpacity(1.0)
                else:
                    w.show()
            except RuntimeError:
                pass


OVERLAYS = None


def overlays() -> _Overlays:
    global OVERLAYS
    if OVERLAYS is None:
        OVERLAYS = _Overlays()
    return OVERLAYS


def overlay_flags(pinned=True, noactivate=True, click_through=False):
    f = Qt.FramelessWindowHint | Qt.Tool | Qt.NoDropShadowWindowHint
    if pinned:
        f |= Qt.WindowStaysOnTopHint
    if noactivate:
        f |= Qt.WindowDoesNotAcceptFocus
    if click_through:
        f |= Qt.WindowTransparentForInput
    return f


class OverlayWindow(QWidget):
    noactivate = True
    click_through = False
    mask_shape = "round"
    mask_radius = 18

    def __init__(self, pinned=True):
        super().__init__(None, overlay_flags(pinned, self.noactivate, self.click_through))
        self.pinned = pinned
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        overlays().register(self)

    def showEvent(self, e):
        super().showEvent(e)
        self._apply_mask()
        overlays().on_shown(self, self.noactivate, self.click_through)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._apply_mask()

    def shape_region(self):
        from PySide6.QtGui import QPainterPath, QPolygonF, QRegion
        if self.mask_shape == "ellipse":
            return QRegion(self.rect(), QRegion.Ellipse)
        path = QPainterPath()
        path.addRoundedRect(self.rect().adjusted(0, 0, 0, 0), self.mask_radius, self.mask_radius)
        return QRegion(path.toFillPolygon().toPolygon())

    def _apply_mask(self):
        if self.mask_shape == "ring" or sysapi.needs_shape_mask():
            try:
                self.setMask(self.shape_region())
            except Exception:
                pass

    def set_pinned(self, on: bool):
        self.pinned = on
        handle = self.windowHandle()
        if handle is not None:
            handle.setFlag(Qt.WindowStaysOnTopHint, on)
        else:
            self.setWindowFlag(Qt.WindowStaysOnTopHint, on)
        if on:
            sysapi.set_topmost(self, True)
        elif sysapi.IS_WIN:
            from .. import winapi
            winapi.set_topmost(self, False)


def qimage_to_np(img: QImage) -> np.ndarray:
    img = img.convertToFormat(QImage.Format_RGB888)
    w, h, bpl = img.width(), img.height(), img.bytesPerLine()
    buf = np.frombuffer(img.constBits(), dtype=np.uint8, count=bpl * h).reshape(h, bpl)
    return buf[:, : w * 3].reshape(h, w, 3).copy()


def screen_at(pt: QPoint):
    return QGuiApplication.screenAt(pt) or QGuiApplication.primaryScreen()


def grab_screen(screen) -> QImage:
    from . import capture
    hidden = overlays().hide_all_for_capture()
    try:
        return capture.backend().grab_screen(screen)
    finally:
        overlays().restore(hidden)


def grab_rect(rect: QRect, hide_overlays=False):
    from . import capture
    scr = screen_at(rect.center())
    r = rect.intersected(scr.geometry())
    if r.isEmpty():
        return None, 1.0
    hidden = overlays().hide_all_for_capture() if hide_overlays else []
    try:
        img = capture.backend().grab_rect(scr, r)
    finally:
        overlays().restore(hidden)
    if img is None or img.isNull():
        return None, 1.0
    dpr = img.width() / max(1, r.width())
    return qimage_to_np(img), dpr


def clamp_to_screens(rect: QRect) -> QRect:
    scr = screen_at(rect.center())
    geo = scr.availableGeometry()
    w = min(rect.width(), geo.width())
    h = min(rect.height(), geo.height())
    x = max(geo.left(), min(rect.left(), geo.right() - w + 1))
    y = max(geo.top(), min(rect.top(), geo.bottom() - h + 1))
    return QRect(x, y, w, h)
