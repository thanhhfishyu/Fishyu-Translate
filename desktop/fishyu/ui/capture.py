import os
import time

from PySide6.QtCore import QRect
from PySide6.QtGui import QGuiApplication, QImage

from .. import sysapi


class QtBackend:
    name = "qt"

    def grab_screen(self, screen) -> QImage:
        return screen.grabWindow(0).toImage()

    def grab_rect(self, screen, r: QRect) -> QImage:
        geo = screen.geometry()
        return screen.grabWindow(0, r.x() - geo.x(), r.y() - geo.y(), r.width(), r.height()).toImage()


def _is_blank(img: QImage) -> bool:
    if img is None or img.isNull():
        return True
    from .common import qimage_to_np
    a = qimage_to_np(img)
    return a.size == 0 or int(a.max()) == 0


class PortalBackend:
    name = "portal"

    def __init__(self, min_interval=1.5):
        self.min_interval = min_interval
        self._shot = None
        self._shot_at = 0.0
        self.qt = QtBackend()
        self.last_error = None

    def _desktop_shot(self, max_age=0.0) -> QImage:
        now = time.monotonic()
        if self._shot is not None and now - self._shot_at <= max_age:
            return self._shot
        from .. import portal
        path = portal.screenshot()
        try:
            img = QImage(path)
        finally:
            try:
                os.unlink(path)
            except OSError:
                pass
        if img.isNull():
            raise RuntimeError("không đọc được ảnh chụp màn hình từ hệ thống")
        self._shot, self._shot_at = img, time.monotonic()
        return img

    def _crop(self, img: QImage, r: QRect) -> QImage:
        vg = QGuiApplication.primaryScreen().virtualGeometry()
        kx = img.width() / max(1, vg.width())
        ky = img.height() / max(1, vg.height())
        rr = QRect(int((r.x() - vg.x()) * kx), int((r.y() - vg.y()) * ky), int(r.width() * kx), int(r.height() * ky))
        return img.copy(rr.intersected(img.rect()))

    def grab_screen(self, screen) -> QImage:
        try:
            return self._crop(self._desktop_shot(), screen.geometry())
        except Exception as e:
            self.last_error = e
            img = self.qt.grab_screen(screen)
            if _is_blank(img):
                raise
            return img

    def grab_rect(self, screen, r: QRect) -> QImage:
        img = self.qt.grab_rect(screen, r)
        if not _is_blank(img):
            return img
        try:
            return self._crop(self._desktop_shot(max_age=self.min_interval), r)
        except Exception as e:
            self.last_error = e
            return None


_backend = None


def backend():
    global _backend
    if _backend is None:
        _backend = PortalBackend() if sysapi.is_wayland() else QtBackend()
    return _backend


def set_backend(b):
    global _backend
    _backend = b
