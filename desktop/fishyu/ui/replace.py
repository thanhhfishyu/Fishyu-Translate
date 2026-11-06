import time

from PySide6.QtCore import QObject, QPoint, QRect, Qt, QTimer, Signal
from PySide6.QtGui import QGuiApplication, QImage, QPainter, QRegion

from .. import config, ocr, sysapi, translator
from ..replace import Gate, changed, pieces_from, render, signature, text_key, zone_of
from . import capture, theme
from .common import OverlayWindow, overlays, qimage_to_np
from .tasks import run_async


class ReplaceOverlay(OverlayWindow):
    click_through = True

    def __init__(self, screen):
        super().__init__(pinned=True)
        self.screen_ = screen
        self.image = None
        self.rects = []
        self.setGeometry(screen.geometry())

    def set_layer(self, img: QImage, rects):
        self.image = img
        self.rects = list(rects)
        self.setGeometry(self.screen_.geometry())
        self._apply_mask()
        self.update()

    def shape_region(self):
        reg = QRegion()
        if self.image is None or not self.rects:
            return QRegion(0, 0, 1, 1)
        k = self.image.width() / max(1, self.width())
        for x0, y0, x1, y1 in self.rects:
            lx0, ly0 = int(x0 / k + 0.999), int(y0 / k + 0.999)
            reg = reg.united(QRect(lx0, ly0, max(1, int(x1 / k) - lx0), max(1, int(y1 / k) - ly0)))
        return reg

    def _apply_mask(self):
        if sysapi.needs_shape_mask():
            try:
                self.setMask(self.shape_region())
            except Exception:
                pass

    def paintEvent(self, e):
        if self.image is None:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        p.drawImage(self.rect(), self.image)
        p.end()


class InputWatcher(QObject):
    pressed = Signal()

    def __init__(self):
        super().__init__()
        self._d = None
        self._notifier = None
        self._buttons = 0
        self._keys = None
        self._last = 0.0
        self.mode = None
        self.timer = QTimer(self)
        self.timer.setInterval(40)
        self.timer.timeout.connect(self._poll)

    def start(self):
        if not (sysapi.IS_LINUX and sysapi.session_type() == "x11"):
            return False
        try:
            from Xlib import display
            self._d = display.Display()
        except Exception:
            self._d = None
            return False
        try:
            from PySide6.QtCore import QSocketNotifier
            from Xlib.ext import xinput
            self._d.xinput_query_version()
            self._d.screen().root.xinput_select_events(
                [(xinput.AllDevices, xinput.RawButtonPressMask | xinput.RawKeyPressMask)])
            self._d.flush()
            self._notifier = QSocketNotifier(self._d.fileno(), QSocketNotifier.Read, self)
            self._notifier.activated.connect(self._drain)
            self.mode = "xi2"
            QTimer.singleShot(0, self._drain)
        except Exception:
            self._notifier = None
            self.mode = "poll"
            self.timer.start()
        return True

    def stop(self):
        self.timer.stop()
        if self._notifier is not None:
            self._notifier.setEnabled(False)
            self._notifier = None
        if self._d is not None:
            try:
                self._d.close()
            except Exception:
                pass
            self._d = None

    def _fire(self):
        now = time.monotonic()
        if now - self._last > 0.05:
            self._last = now
            self.pressed.emit()

    def _drain(self, *_):
        d = self._d
        if d is None:
            return
        from Xlib.ext import ge, xinput
        try:
            while d.pending_events():
                ev = d.next_event()
                if ev.type == ge.GenericEventCode and getattr(ev, "evtype", 0) in (xinput.RawButtonPress, xinput.RawKeyPress):
                    self._fire()
        except Exception:
            pass

    def _poll(self):
        try:
            q = self._d.screen().root.query_pointer()
            keys = bytes(self._d.query_keymap())
        except Exception:
            return
        buttons = q.mask & 0x1F00
        fire = bool(buttons & ~self._buttons)
        if self._keys is not None and keys != self._keys and any(keys):
            fire = True
        self._buttons, self._keys = buttons, keys
        if fire:
            self._fire()


class ReplaceSession(QObject):
    status = Signal(str)

    def __init__(self, screen=None, on_stop=None):
        super().__init__()
        self.screen = screen or QGuiApplication.primaryScreen()
        self.on_stop = on_stop
        self.alive = True
        self.paused = False
        self.busy = False
        self.op = 0
        self.manual = sysapi.is_wayland()
        self.gate = Gate()
        self.overlay = ReplaceOverlay(self.screen)
        self.last = None
        self.visible = False
        self.hide_at = 0.0
        self.show_at = 0.0
        self.processed_count = 0
        self.last_note = None
        self.input = InputWatcher()
        self.input.pressed.connect(self.touched)
        self.timer = QTimer(self)
        self.timer.setInterval(220)
        self.timer.timeout.connect(self.tick)

    @property
    def clean_capture(self):
        return bool(overlays().exclude_ok)

    @property
    def cell(self):
        return max(16, int(self.screen.geometry().width() * self.screen.devicePixelRatio()) // 40)

    def start(self):
        self.overlay.show()
        self.overlay.hide()
        self.gate.peek_on_touch = not self.clean_capture
        if not self.clean_capture:
            self.input.start()
        if self.manual:
            self.refresh()
        else:
            self.timer.start()

    def stop(self):
        if not self.alive:
            return
        self.alive = False
        self.op += 1
        self.timer.stop()
        self.input.stop()
        try:
            self.overlay.hide()
            self.overlay.deleteLater()
        except RuntimeError:
            pass
        if self.on_stop:
            self.on_stop(self)

    def set_paused(self, p: bool):
        if self.paused == p:
            return
        self.paused = p
        self.op += 1
        self.busy = False
        if p:
            self._hide()
        elif self.manual:
            if self.last is not None:
                self._show(self.last)
        else:
            self.gate.reset(time.monotonic())

    def refresh(self):
        self.op += 1
        self.busy = False
        self._hide()
        self.gate.reset(time.monotonic())
        if self.manual:
            QTimer.singleShot(250, self._manual_shot)

    def touched(self):
        before = self.gate.state
        self.gate.touch(time.monotonic())
        if before == Gate.BUSY and self.gate.state != before:
            self.op += 1
            self.busy = False

    def _show(self, layer):
        img, rects = layer
        self.overlay.set_layer(img, rects)
        if not self.overlay.isVisible():
            self.overlay.show()
        self.visible = True
        self.show_at = time.monotonic()

    def _hide(self):
        try:
            if self.overlay.isVisible():
                self.overlay.hide()
        except RuntimeError:
            return
        if self.visible:
            self.visible = False
            self.hide_at = time.monotonic()

    def _grab(self):
        img = capture.backend().grab_screen(self.screen)
        if img is None or img.isNull():
            return None
        return qimage_to_np(img)

    def tick(self):
        if not self.alive or self.paused or self.busy:
            return
        now = time.monotonic()
        if not self.visible and now - self.hide_at < 0.15:
            return
        try:
            arr = self._grab()
        except Exception:
            return
        if arr is None:
            return
        sig = signature(arr, self.cell)
        if self.visible and self.gate.needs_reference:
            if now - self.show_at >= 0.15:
                self.gate.reference(sig)
            return
        act = self.gate.frame(sig, now)
        if act in (Gate.HIDE, Gate.DO_PEEK):
            self._hide()
        elif act == Gate.SHOW_CACHED:
            if self.last is not None:
                self._show(self.last)
            else:
                self.gate.reset(now)
        elif act == Gate.PROCESS:
            self._process(arr, sig)

    def _manual_shot(self):
        if not self.alive or self.paused:
            return
        try:
            arr = self._grab()
        except Exception as e:
            self.status.emit(f"Không chụp được màn hình: {e}")
            return
        if arr is None:
            return
        sig = signature(arr, self.cell)
        self.gate.reset(time.monotonic())
        self.gate.state = Gate.BUSY
        self._process(arr, sig)

    def _process(self, arr, sig):
        self.busy = True
        self.op += 1
        op = self.op
        pref = config.get().source_lang

        def after_ocr(res, err):
            if op != self.op or not self.alive:
                return
            if err:
                self.busy = False
                self.gate.failed(time.monotonic())
                return
            pieces = pieces_from(res)
            if not self.manual and not self.gate.ocr_done(text_key(pieces), time.monotonic()):
                self.busy = False
                return
            if not pieces:
                self.busy = False
                self.gate.processed(sig, None)
                self._hide()
                self.processed_count += 1
                return
            st = config.get()
            page = "\n".join(p.source for p in pieces)
            engine = st.replace_engine
            lang = res.lang
            scale = self.screen.devicePixelRatio()
            family = theme.BODY_FAMILY

            def work():
                results = translator.translate_many([p.source for p in pieces], lang, page, engine)
                for p, r in zip(pieces, results):
                    p.text = r.text
                img, rects = render(arr, pieces, scale, family)
                return img, rects, results

            run_async(work, lambda r, e: self._rendered(op, sig, r, e), "replace-render")

        run_async(lambda: ocr.recognize(arr, pref), after_ocr, "replace-ocr")

    def _rendered(self, op, sig, r, err):
        if op != self.op or not self.alive:
            return
        self.busy = False
        now = time.monotonic()
        if err:
            self.gate.failed(now)
            self.status.emit(f"Lỗi dịch: {str(err)[:80]}")
            return
        img, rects, results = r
        if not self.manual and (self.clean_capture or not self.visible):
            try:
                again = self._grab()
            except Exception:
                again = None
            if again is not None and changed(sig, signature(again, self.cell), 8) > 0.01:
                self.gate.abort(now)
                return
        self.processed_count += 1
        if not rects:
            self.gate.processed(sig, None)
            self._hide()
            return
        self.last = (img, rects)
        self.gate.processed(sig, zone_of(rects, sig))
        self._show(self.last)
        note = next((x.note for x in results if x.note), None)
        if note and note != self.last_note:
            self.last_note = note
            self.status.emit(note)

    def overlay_rect_global(self, rect):
        k = self.screen.devicePixelRatio()
        g = self.screen.geometry()
        x0, y0, x1, y1 = rect
        return QRect(g.x() + int(x0 / k), g.y() + int(y0 / k), int((x1 - x0) / k), int((y1 - y0) / k))
