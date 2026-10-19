import time
from collections import deque

import numpy as np
from PySide6.QtCore import QRect, QRectF, Qt, QTimer
from PySide6.QtGui import QFont, QPainter, QPen
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from .. import config, ocr, translator
from ..livegate import Decision, LiveGate
from . import theme
from .common import OverlayWindow, clamp_to_screens, grab_rect, overlays
from .tasks import run_async


class LiveFrame(OverlayWindow):
    click_through = True
    no_mask = True

    def __init__(self, region: QRect):
        super().__init__(pinned=True)
        pad = 5
        self.setGeometry(region.adjusted(-pad, -pad, pad, pad))

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QPen(theme.ACCENT, 2, Qt.DashLine))
        p.drawRoundedRect(QRectF(self.rect()).adjusted(1.5, 1.5, -1.5, -1.5), 5, 5)
        p.end()


class LiveBox(OverlayWindow):
    def __init__(self, session):
        super().__init__(pinned=True)
        self.session = session
        self._drag = None
        self.card = theme.DoodleFrame(theme.BG, 16, 3)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self.card)
        lay = QVBoxLayout(self.card)
        lay.setContentsMargins(12, 8, 15, 12)
        lay.setSpacing(4)
        self.header = QWidget()
        hl = QHBoxLayout(self.header)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(6)
        self.engine_chip = theme.Chip(self._engine_label())
        self.engine_chip.setToolTip("Đổi bộ dịch: DeepL (chuẩn) / Offline (miễn phí)")
        self.engine_chip.clicked.connect(session.toggle_engine)
        a_minus = theme.Chip("A-")
        a_minus.clicked.connect(lambda: session.font_step(-2))
        a_plus = theme.Chip("A+")
        a_plus.clicked.connect(lambda: session.font_step(2))
        self.pause_chip = theme.Chip("Dừng")
        self.pause_chip.clicked.connect(session.toggle_pause)
        src = theme.Chip("Chữ gốc")
        src.clicked.connect(session.toggle_source)
        close = theme.Chip("Đóng", filled=True)
        close.clicked.connect(session.stop)
        for w in (self.engine_chip, a_minus, a_plus, self.pause_chip, src):
            hl.addWidget(w)
        hl.addStretch(1)
        hl.addWidget(close)
        lay.addWidget(self.header)
        self.source = QLabel("")
        self.source.setWordWrap(True)
        self.source.setStyleSheet(f"color:{theme.MUTED.name()};")
        self.source.setVisible(config.get().live_show_source)
        self.translation = QLabel("Đang đọc chữ trong vùng...")
        self.translation.setWordWrap(True)
        self.status = QLabel("Đang theo dõi")
        self.status.setStyleSheet(f"color:{theme.MUTED.name()};font-size:11px;")
        lay.addWidget(self.source)
        lay.addWidget(self.translation)
        lay.addWidget(self.status)
        self.apply_font()
        self.header.installEventFilter(self)

    def _engine_label(self):
        return "DeepL" if config.get().live_engine == "DEEPL" else "Offline"

    def apply_font(self):
        px = config.get().live_font
        self.translation.setFont(theme.body_font(px + 2, QFont.Medium))
        self.source.setFont(theme.body_font(max(11, px - 3)))
        self.fit()

    def fit(self):
        w = self.width()
        h = self.layout().totalHeightForWidth(w)
        if h <= 0:
            h = self.sizeHint().height()
        self.resize(w, h)
        r = clamp_to_screens(self.geometry())
        if r.topLeft() != self.pos():
            self.move(r.topLeft())

    def eventFilter(self, obj, ev):
        t = ev.type()
        if obj is self.header:
            if t == ev.Type.MouseButtonPress and ev.button() == Qt.LeftButton:
                self._drag = ev.globalPosition().toPoint() - self.pos()
                return True
            if t == ev.Type.MouseMove and self._drag is not None:
                r = QRect(ev.globalPosition().toPoint() - self._drag, self.size())
                self.move(clamp_to_screens(r).topLeft())
                return True
            if t == ev.Type.MouseButtonRelease:
                self._drag = None
                return True
        return super().eventFilter(obj, ev)


def signature(img: np.ndarray) -> np.ndarray:
    import cv2
    g = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    h = max(4, min(32, int(48 * g.shape[0] / max(1, g.shape[1]))))
    return cv2.resize(g, (48, h), interpolation=cv2.INTER_AREA).astype(np.int16)


def sig_diff(a, b) -> float:
    if a is None or b is None or a.shape != b.shape:
        return 255.0
    return float(np.abs(a - b).mean())


class LiveSession:
    def __init__(self, region: QRect, on_stop=None):
        self.region = QRect(region)
        self.on_stop = on_stop
        self.gate = LiveGate()
        self.history = deque(maxlen=3)
        self.paused = False
        self.busy = False
        self.last_sig = None
        self.next_ocr_at = 0.0
        self.empty_streak = 0
        self.sent_chars = 0
        self.alive = True
        self.frame = LiveFrame(self.region)
        self.box = LiveBox(self)
        self.timer = QTimer()
        self.timer.setInterval(350)
        self.timer.timeout.connect(self.tick)

    def start(self):
        self.frame.show()
        self.box.resize(max(380, min(self.region.width(), 760)), 120)
        self.box.fit()
        self._place_box()
        self.box.show()
        self.timer.start()

    def _place_box(self):
        w, h = self.box.width(), max(self.box.height(), 110)
        r = self.region
        x = r.center().x() - w // 2
        y = r.top() - h - 12
        scr_top = clamp_to_screens(QRect(x, y, w, h))
        if y < scr_top.top() or scr_top.intersects(r):
            y = r.bottom() + 12
        self.box.move(clamp_to_screens(QRect(x, y, w, h)).topLeft())

    def stop(self):
        if not self.alive:
            return
        self.alive = False
        self.timer.stop()
        for w in (self.frame, self.box):
            try:
                w.hide()
                w.deleteLater()
            except RuntimeError:
                pass
        if self.on_stop:
            self.on_stop(self)

    def set_hidden(self, hidden: bool):
        for w in (self.frame, self.box):
            try:
                w.setVisible(not hidden)
            except RuntimeError:
                pass
        if not hidden:
            self.next_ocr_at = time.monotonic() + 0.4

    def toggle_engine(self):
        st = config.get()
        st.live_engine = "OFFLINE" if st.live_engine == "DEEPL" else "DEEPL"
        config.save()
        self.box.engine_chip.setText(self.box._engine_label())
        self.box.engine_chip.updateGeometry()
        self.gate.reset(clear_done=True)
        self.last_sig = None

    def font_step(self, d):
        st = config.get()
        st.live_font = max(10, min(32, st.live_font + d))
        config.save()
        self.box.apply_font()

    def toggle_pause(self):
        self.paused = not self.paused
        self.box.pause_chip.setText("Tiếp" if self.paused else "Dừng")
        self.box.status.setText("Đã dừng" if self.paused else "Đang theo dõi")
        if not self.paused:
            self.last_sig = None
            self.gate.reset()

    def toggle_source(self):
        st = config.get()
        st.live_show_source = not st.live_show_source
        config.save()
        self.box.source.setVisible(st.live_show_source)
        self.box.fit()

    def _mask(self, img, dpr):
        if overlays().exclude_ok:
            return img
        fill = img[0, 0].copy()
        for r in overlays().visible_rects():
            rr = r.intersected(self.region)
            if rr.isEmpty():
                continue
            x0 = int((rr.left() - self.region.left()) * dpr)
            y0 = int((rr.top() - self.region.top()) * dpr)
            x1 = int((rr.right() + 1 - self.region.left()) * dpr)
            y1 = int((rr.bottom() + 1 - self.region.top()) * dpr)
            img[max(0, y0):max(0, y1), max(0, x0):max(0, x1)] = fill
        return img

    def tick(self):
        if not self.alive or self.paused or self.busy or not self.box.isVisible():
            return
        try:
            img, dpr = grab_rect(self.region)
        except Exception:
            return
        if img is None:
            return
        img = self._mask(img, dpr)
        sig = signature(img)
        changed = sig_diff(sig, self.last_sig) >= 3
        now = time.monotonic()
        if not (changed or self.gate.has_pending) or now < self.next_ocr_at:
            return
        self.last_sig = sig
        self.next_ocr_at = now + 0.65
        self.busy = True
        pref = config.get().source_lang
        run_async(lambda: ocr.recognize(img, pref), self._on_ocr, "live-ocr")

    def _on_ocr(self, res, err):
        if not self.alive:
            return
        if err:
            self.busy = False
            return
        text = res.text.replace("\n", "").strip()
        d = self.gate.offer(text)
        if d.kind in (Decision.EMPTY, Decision.NOT_CJK):
            self.empty_streak += 1
            if self.empty_streak == 3 and not self.gate.has_shown:
                self.box.status.setText("Chưa thấy chữ Trung/Nhật trong vùng đã chọn")
            self.busy = False
            return
        self.empty_streak = 0
        if d.kind in (Decision.SAME, Decision.WAIT):
            self.busy = False
            return
        self.box.source.setText(text)
        if d.kind == Decision.REUSE:
            self.box.translation.setText(d.translation)
            self.box.fit()
            self.busy = False
            return
        self.box.status.setText("Đang dịch...")
        engine = config.get().live_engine
        ctx = "\n".join(self.history) or None
        lang = res.lang

        def done(r, e):
            self.busy = False
            if not self.alive:
                return
            if e:
                self.box.status.setText(f"Lỗi: {str(e)[:60]} - sẽ thử lại")
                self.gate.failed()
                self.next_ocr_at = time.monotonic() + 4
                return
            self.box.translation.setText(r.text)
            if r.engine == "DeepL":
                self.sent_chars += len(text)
            self.gate.remember(d.norm, r.text)
            self.history.append(text)
            if r.note:
                self.box.status.setText("Đang dịch offline (DeepL lỗi)")
            elif engine == "DEEPL":
                self.box.status.setText(f"Đang theo dõi - đã gửi DeepL khoảng {self.sent_chars} ký tự")
            else:
                self.box.status.setText("Đang theo dõi")
            self.box.fit()

        run_async(lambda: translator.translate(text, lang, ctx, engine), done, "live-translate")
