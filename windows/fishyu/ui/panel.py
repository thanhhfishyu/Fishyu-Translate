from PySide6.QtCore import QRect, Qt, QTimer
from PySide6.QtGui import QCursor, QFont, QGuiApplication
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QPlainTextEdit, QScrollArea, QSizeGrip,
                               QVBoxLayout, QWidget)

from .. import config, translator
from ..dictionary import DICT
from ..textutil import detect_lang, han_count, has_kana
from . import theme
from .common import OverlayWindow, clamp_to_screens
from .tasks import run_async

LANG_LABEL = {"ZH": "Tiếng Trung", "JA": "Tiếng Nhật"}


class ResultPanel(OverlayWindow):
    noactivate = False

    def __init__(self, on_close=None):
        st = config.get()
        super().__init__(pinned=st.panel_pinned)
        self.on_close = on_close
        self.lang = "ZH"
        self.context = None
        self._gen = 0
        self._drag = None
        self.setMinimumSize(360, 220)
        self.resize(520, 380)

        self.card = theme.DoodleFrame(theme.BG, 18, 4)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self.card)
        lay = QVBoxLayout(self.card)
        lay.setContentsMargins(14, 10, 18, 16)
        lay.setSpacing(6)

        self.header = QWidget()
        hl = QHBoxLayout(self.header)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(6)
        self.lang_chip = theme.Chip("Tiếng Trung")
        self.lang_chip.clicked.connect(self.cycle_lang)
        self.engine_lbl = QLabel("")
        self.engine_lbl.setStyleSheet(f"color:{theme.MUTED.name()};font-size:12px;")
        self.pin_chip = theme.Chip("Đã ghim" if self.pinned else "Ghim", filled=self.pinned)
        self.pin_chip.setToolTip("Ghim: luôn nằm trên cùng, kể cả khi bấm sang game")
        self.pin_chip.clicked.connect(self.toggle_pin)
        smaller = theme.Chip("A-")
        smaller.clicked.connect(lambda: self.font_step(-1))
        bigger = theme.Chip("A+")
        bigger.clicked.connect(lambda: self.font_step(1))
        copy = theme.Chip("Chép")
        copy.clicked.connect(self.copy_translation)
        close = theme.Chip("Đóng", filled=True)
        close.clicked.connect(self.close_panel)
        hl.addWidget(self.lang_chip)
        hl.addWidget(self.engine_lbl)
        hl.addStretch(1)
        for w in (smaller, bigger, self.pin_chip, copy, close):
            hl.addWidget(w)
        lay.addWidget(self.header)

        body = QWidget()
        bl = QVBoxLayout(body)
        bl.setContentsMargins(0, 4, 4, 0)
        bl.setSpacing(6)
        self.translation = QLabel("")
        self.translation.setWordWrap(True)
        self.translation.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.note = QLabel("")
        self.note.setWordWrap(True)
        self.note.setStyleSheet(f"color:{theme.MUTED.name()};font-size:12px;")
        self.note.hide()
        bl.addWidget(self.translation)
        bl.addWidget(self.note)
        sep = QFrame()
        sep.setFixedHeight(2)
        sep.setStyleSheet(f"background:{theme.LINE.name()};")
        bl.addWidget(sep)
        row = QHBoxLayout()
        src_title = QLabel("Bản gốc - bôi đen để tra từ, sửa nếu nhận diện sai")
        src_title.setStyleSheet(f"color:{theme.MUTED.name()};font-size:12px;")
        self.lookup_chip = theme.Chip("Tra từ")
        self.lookup_chip.setEnabled(False)
        self.lookup_chip.clicked.connect(self.lookup_selection)
        again = theme.Chip("Dịch lại")
        again.clicked.connect(lambda: self.translate_now(self.source.toPlainText()))
        row.addWidget(src_title, 1)
        row.addWidget(self.lookup_chip)
        row.addWidget(again)
        bl.addLayout(row)
        self.source = QPlainTextEdit()
        self.source.setFixedHeight(84)
        self.source.selectionChanged.connect(self._sel_changed)
        bl.addWidget(self.source)
        self.dict_box = QLabel("")
        self.dict_box.setWordWrap(True)
        self.dict_box.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.dict_box.setStyleSheet(
            f"background:{theme.SURFACE.name()};border:2px solid {theme.ACCENT_SOFT.name()};border-radius:12px;padding:8px;")
        self.dict_box.hide()
        bl.addWidget(self.dict_box)
        bl.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(body)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.viewport().setStyleSheet("background:transparent;")
        body.setStyleSheet("background:transparent;")
        lay.addWidget(scroll, 1)
        grip_row = QHBoxLayout()
        grip_row.addStretch(1)
        grip_row.addWidget(QSizeGrip(self.card))
        lay.addLayout(grip_row)
        self.apply_font()
        self.header.installEventFilter(self)

    def apply_font(self):
        self.translation.setFont(theme.body_font(config.get().panel_font + 3, QFont.Medium))
        self.source.setFont(theme.body_font(config.get().panel_font))

    def font_step(self, d):
        st = config.get()
        st.panel_font = max(11, min(28, st.panel_font + d))
        config.save()
        self.apply_font()

    def toggle_pin(self):
        on = not self.pinned
        config.get().panel_pinned = on
        config.save()
        self.set_pinned(on)
        self.pin_chip.set_filled(on)
        self.pin_chip.setText("Đã ghim" if on else "Ghim")

    def eventFilter(self, obj, ev):
        t = ev.type()
        if obj is self.header:
            if t == ev.Type.MouseButtonPress and ev.button() == Qt.LeftButton:
                self._drag = ev.globalPosition().toPoint() - self.pos()
                return True
            if t == ev.Type.MouseMove and self._drag is not None:
                self.move(ev.globalPosition().toPoint() - self._drag)
                return True
            if t == ev.Type.MouseButtonRelease:
                self._drag = None
                return True
        return super().eventFilter(obj, ev)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.close_panel()
        else:
            super().keyPressEvent(e)

    def close_panel(self):
        self._gen += 1
        self.hide()
        if self.on_close:
            self.on_close(self)
        self.deleteLater()

    def place_near(self, anchor: QRect = None):
        if anchor is None or anchor.isEmpty():
            scr = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
            g = scr.availableGeometry()
            r = QRect(g.center().x() - self.width() // 2, g.bottom() - self.height() - 40, self.width(), self.height())
        else:
            scr = QGuiApplication.screenAt(anchor.center()) or QGuiApplication.primaryScreen()
            g = scr.availableGeometry()
            x = anchor.center().x() - self.width() // 2
            if anchor.bottom() + 12 + self.height() <= g.bottom():
                y = anchor.bottom() + 12
            elif anchor.top() - 12 - self.height() >= g.top():
                y = anchor.top() - 12 - self.height()
            else:
                y = g.bottom() - self.height() - 20
            r = QRect(x, y, self.width(), self.height())
        self.setGeometry(clamp_to_screens(r))

    def show_loading(self, msg):
        self.translation.setStyleSheet(f"color:{theme.MUTED.name()};")
        self.translation.setText(msg)
        self.note.hide()

    def show_error(self, msg):
        self.translation.setStyleSheet(f"color:{theme.ERROR.name()};")
        self.translation.setText(msg)

    def start(self, text, lang=None, context=None):
        self.context = context
        pref = config.get().source_lang
        self.lang = pref if pref in ("ZH", "JA") else (lang if lang in ("ZH", "JA") else detect_lang(text))
        self.lang_chip.setText(LANG_LABEL[self.lang])
        self.source.setPlainText(text)
        self.translate_now(text)

    def cycle_lang(self):
        self.lang = "JA" if self.lang == "ZH" else "ZH"
        self.lang_chip.setText(LANG_LABEL[self.lang])
        self.translate_now(self.source.toPlainText())

    def translate_now(self, text):
        self._gen += 1
        gen = self._gen
        self.dict_box.hide()
        text = text.strip()
        if not text:
            self.show_error("Không nhận diện được chữ nào. Thử khoanh vùng rộng hơn.")
            return
        self.show_loading("Đang dịch...")
        lang, ctx = self.lang, self.context

        def done(res, err):
            if gen != self._gen:
                return
            if err:
                self.show_error(f"Lỗi: {err}")
                return
            self.translation.setStyleSheet(f"color:{theme.FG.name()};")
            self.translation.setText(res.text)
            self.engine_lbl.setText(res.engine)
            self.note.setText(res.note or "")
            self.note.setVisible(bool(res.note))
            compact = text.strip()
            if lang == "ZH" and len(compact) <= 8 and han_count(compact) == len(compact):
                self._lookup(compact, False)

        run_async(lambda: translator.translate(text, lang, ctx), done, "translate")

    def copy_translation(self):
        QGuiApplication.clipboard().setText(self.translation.text())
        self.engine_lbl.setText("Đã chép")
        QTimer.singleShot(1500, lambda: self.engine_lbl.setText(""))

    def _sel_changed(self):
        self.lookup_chip.setEnabled(self.source.textCursor().hasSelection())

    def lookup_selection(self):
        w = self.source.textCursor().selectedText().strip()
        if w:
            self._lookup(w, True)

    def _lookup(self, word, from_selection):
        lang = self.lang
        full = self.source.toPlainText()
        self.dict_box.setText(f"<b style='font-size:18px'>{word}</b><br><span style='color:{theme.MUTED.name()}'>Đang tra...</span>")
        self.dict_box.show()

        def work():
            parts = []
            if from_selection:
                try:
                    r = translator.translate(word, lang, full)
                    parts.append(f"<span style='color:{theme.ACCENT.name()}'>Theo ngữ cảnh: {r.text}</span>")
                except Exception as e:
                    parts.append(f"Không dịch được: {e}")
            if lang == "JA" and has_kana(word):
                return parts
            if DICT.ready(30):
                hv = DICT.han_viet(word)
                if hv:
                    parts.append(f"Hán Việt: {hv}")
                entries = DICT.lookup(word)
                if entries:
                    parts += [self._fmt(e) for e in entries[:4]]
                elif han_count(word) > 1:
                    for w in list(dict.fromkeys(DICT.segment(word)))[:8]:
                        es = DICT.lookup(w)
                        if es:
                            parts.append(f"<b>{w}</b> - {DICT.han_viet(w)}")
                            parts += [self._fmt(e) for e in es[:2]]
            return parts

        def done(parts, err):
            if err or not parts:
                if not from_selection:
                    self.dict_box.hide()
                else:
                    self.dict_box.setText(f"<b>{word}</b><br>Không tìm thấy trong từ điển")
                return
            self.dict_box.setText(f"<b style='font-size:18px'>{word}</b><br>" + "<br>".join(parts))

        run_async(work, done, "lookup")

    @staticmethod
    def _fmt(e):
        head = f"{e.pinyin} ({e.trad})" if e.trad != e.simp else e.pinyin
        return f"<span style='color:{theme.ACCENT.name()}'>{head}</span><br><span style='color:{theme.MUTED.name()}'>{e.defs}</span>"
