import webbrowser

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFont, QGuiApplication, QKeySequence
from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QDialog, QFileDialog, QHBoxLayout, QKeySequenceEdit,
                               QLabel, QLineEdit, QMainWindow, QPlainTextEdit, QRadioButton, QScrollArea,
                               QVBoxLayout, QWidget)

from .. import APP_NAME, VERSION, config, crashlog, translator, winapi
from ..offline import OFFLINE
from ..paths import resource
from . import theme
from .tasks import run_async


def _muted(text, size=13):
    l = QLabel(text)
    l.setWordWrap(True)
    l.setStyleSheet(f"color:{theme.MUTED.name()};font-size:{size}px;")
    return l


def _row(*widgets, stretch_end=True):
    w = QWidget()
    h = QHBoxLayout(w)
    h.setContentsMargins(0, 4, 0, 0)
    h.setSpacing(8)
    for x in widgets:
        h.addWidget(x)
    if stretch_end:
        h.addStretch(1)
    return w


class Card(theme.DoodleFrame):
    def __init__(self, title, tag=None):
        super().__init__(theme.BG, 20, 4)
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(18, 12, 22, 20)
        self.lay.setSpacing(6)
        head = QLabel(title)
        head.setFont(theme.head_font(20))
        if tag:
            t = QLabel(tag)
            t.setFont(theme.head_font(12, QFont.DemiBold))
            t.setStyleSheet(f"background:{theme.ACCENT_SOFT.name()};border:2px solid {theme.INK.name()};"
                            "border-radius:10px;padding:1px 8px;")
            self.lay.addWidget(self._head_row(head, t))
        else:
            self.lay.addWidget(head)

    @staticmethod
    def _head_row(head, tag):
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(0, 0, 0, 0)
        h.addWidget(head)
        h.addStretch(1)
        h.addWidget(tag)
        return w

    def add(self, w):
        self.lay.addWidget(w)
        return w


class SettingsWindow(QMainWindow):
    hotkeys_changed = Signal()
    bubble_toggled = Signal(bool)
    test_translate = Signal(str)
    progress = Signal(str)

    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(theme.app_icon())
        self.resize(560, 820)
        self.setStyleSheet(f"QMainWindow{{background:{theme.PAGE.name()};}}" + theme.STYLE)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        page = QWidget()
        page.setObjectName("page")
        page.setStyleSheet(f"#page{{background:{theme.PAGE.name()};}}")
        self.col = QVBoxLayout(page)
        self.col.setContentsMargins(18, 14, 18, 30)
        self.col.setSpacing(16)
        scroll.setWidget(page)
        self.setCentralWidget(scroll)
        self._build()
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(600)
        self._save_timer.timeout.connect(self.save)

    def _changed(self):
        self._save_timer.start()

    def save(self):
        st = config.get()
        st.deepl_key = self.key_field.text().strip()
        st.domain_hint = self.domain.toPlainText().strip()
        st.glossary = self.glossary.toPlainText()
        config.save()

    def closeEvent(self, e):
        self.save()
        if self.controller.tray_available():
            e.ignore()
            self.hide()
            self.controller.notify_hidden_once()
        else:
            e.accept()
            self.controller.quit()

    def _build(self):
        st = config.get()
        self._build_error()
        self._build_coffee()
        self._build_hero()

        c = Card("Bong bóng & phím tắt")
        self.col.addWidget(c)
        cb = QCheckBox("Hiện bong bóng cá mập nổi trên màn hình")
        cb.setChecked(st.bubble_visible)
        cb.toggled.connect(self._toggle_bubble)
        c.add(cb)
        self.hotkey_edits = {}
        for key, label in (("hotkey_capture", "Khoanh vùng để dịch"), ("hotkey_live", "Dịch trực tiếp (game)"),
                           ("hotkey_clipboard", "Dịch chữ đã copy")):
            ed = QKeySequenceEdit(QKeySequence(getattr(st, key)))
            ed.setMaximumSequenceLength(1)
            ed.setFixedWidth(170)
            ed.editingFinished.connect(lambda k=key, e=ed: self._set_hotkey(k, e))
            self.hotkey_edits[key] = ed
            lbl = QLabel(label)
            lbl.setMinimumWidth(190)
            c.add(_row(lbl, ed))
        self.hotkey_warn = _muted("")
        self.hotkey_warn.setStyleSheet(f"color:{theme.ERROR.name()};font-size:13px;")
        self.hotkey_warn.hide()
        c.add(self.hotkey_warn)
        dc = QCheckBox("Bấm Ctrl+C hai lần liên tiếp để dịch chữ đang bôi đen")
        dc.setChecked(st.double_copy)
        dc.toggled.connect(lambda v: (setattr(config.get(), "double_copy", v), config.save()))
        c.add(dc)
        sw = QCheckBox("Khởi động cùng Windows (chạy ẩn ở khay hệ thống)")
        sw.setChecked(st.start_with_windows)
        sw.toggled.connect(self._toggle_startup)
        c.add(sw)

        c = Card("Dịch trực tiếp", "game")
        self.col.addWidget(c)
        c.add(_muted("Bấm phím tắt hoặc chọn \"Dịch trực tiếp\" trong menu bong bóng, rồi khoanh khung thoại. "
                     "Khung dịch luôn ghim trên cùng và tự dịch lại khi chữ đổi; bấm vào nó không làm game mất chuột/bàn phím. "
                     "Với game toàn màn hình, hãy chọn chế độ hiển thị \"Borderless\" hoặc \"Windowed\" trong game."))
        c.add(QLabel("Bộ dịch cho chế độ này"))
        self._radios(c, {"DEEPL": "DeepL (chuẩn hơn, tốn ký tự)", "OFFLINE": "Offline (miễn phí, tiết kiệm)"},
                     st.live_engine, lambda v: setattr(config.get(), "live_engine", v))
        src = QCheckBox("Hiện cả chữ gốc trong khung dịch")
        src.setChecked(st.live_show_source)
        src.toggled.connect(lambda v: (setattr(config.get(), "live_show_source", v), config.save()))
        c.add(src)

        c = Card("DeepL API key")
        self.col.addWidget(c)
        c.add(_muted("Gói Developer miễn phí của DeepL cho 1 triệu ký tự dùng một lần. Mỗi chữ Hán tính 1 ký tự. "
                     "Phần gợi ý lĩnh vực và ngữ cảnh không bị tính."))
        self.key_field = QLineEdit(st.deepl_key)
        self.key_field.setPlaceholderText("Dán DeepL API key vào đây")
        self.key_field.setEchoMode(QLineEdit.Password)
        self.key_field.textChanged.connect(self._changed)
        c.add(self.key_field)
        self.usage = _muted("")
        c.add(self.usage)
        check = theme.Chip("Kiểm tra key", filled=True)
        check.clicked.connect(self._check_key)
        getk = theme.Chip("Lấy key")
        getk.clicked.connect(lambda: webbrowser.open("https://www.deepl.com/pro-api"))
        show = theme.Chip("Hiện")
        show.clicked.connect(lambda: (self.key_field.setEchoMode(
            QLineEdit.Normal if self.key_field.echoMode() == QLineEdit.Password else QLineEdit.Password),
            show.setText("Ẩn" if self.key_field.echoMode() == QLineEdit.Normal else "Hiện")))
        c.add(_row(check, getk, show))

        c = Card("Bộ dịch khi khoanh vùng / chữ đã copy")
        self.col.addWidget(c)
        self._radios(c, config.ENGINES, st.engine, lambda v: setattr(config.get(), "engine", v))
        fb = QCheckBox("Tự chuyển sang offline khi DeepL lỗi hoặc hết ký tự")
        fb.setChecked(st.fallback_offline)
        fb.toggled.connect(lambda v: (setattr(config.get(), "fallback_offline", v), config.save()))
        c.add(fb)
        c.add(_muted("Gói dịch offline (khoảng 80 MB mỗi ngôn ngữ) được tải một lần khi dùng lần đầu."))
        self.off_status = _muted("")
        self.progress.connect(self.off_status.setText)
        c.add(self.off_status)
        dz = theme.Chip("Tải gói Trung - Việt")
        dz.clicked.connect(lambda: self._download("ZH"))
        dj = theme.Chip("Tải gói Nhật - Việt")
        dj.clicked.connect(lambda: self._download("JA"))
        c.add(_row(dz, dj))
        self._refresh_offline()

        c = Card("Ngôn ngữ nguồn")
        self.col.addWidget(c)
        self._radios(c, config.SOURCE_LANGS, st.source_lang, lambda v: setattr(config.get(), "source_lang", v),
                     horizontal=True)
        c.add(_muted("Chế độ Tự động nhận ra tiếng Nhật khi có chữ kana (ひらがな/カタカナ)."))

        c = Card("Lĩnh vực")
        self.col.addWidget(c)
        c.add(_muted("Gửi kèm cho DeepL làm ngữ cảnh để chọn từ chuẩn hơn. Nên viết bằng tiếng Anh."))
        self.domain = QPlainTextEdit(st.domain_hint)
        self.domain.setPlaceholderText("Ví dụ: Medical text. Use precise medical terminology.")
        self.domain.setFixedHeight(64)
        self.domain.textChanged.connect(self._changed)
        c.add(self.domain)
        presets = [theme.Chip("Không")]
        presets[0].clicked.connect(lambda: self.domain.setPlainText(""))
        for name, hint in config.DOMAIN_PRESETS:
            b = theme.Chip(name)
            b.clicked.connect(lambda _=False, h=hint: self.domain.setPlainText(h))
            presets.append(b)
        c.add(_row(*presets))

        c = Card("Bảng thuật ngữ")
        self.col.addWidget(c)
        c.add(_muted("Mỗi dòng: chữ gốc = cách dịch cố định. Dùng cho tên nhân vật, thuật ngữ chuyên ngành. "
                     "Dòng bắt đầu bằng # là ghi chú."))
        self.glossary = QPlainTextEdit(st.glossary)
        self.glossary.setPlaceholderText("林动 = Lâm Động\n心肌梗死 = nhồi máu cơ tim\n# ghi chú")
        self.glossary.setFixedHeight(120)
        self.glossary.textChanged.connect(self._changed)
        c.add(self.glossary)

        c = Card("Dịch thử")
        self.col.addWidget(c)
        test = QLineEdit("细胞膜是包围细胞质的一层薄膜。")
        c.add(test)
        go = theme.Chip("Dịch", filled=True, small=False)
        go.clicked.connect(lambda: (self.save(), self.test_translate.emit(test.text())))
        c.add(go)

        c = Card("Cách dùng")
        self.col.addWidget(c)
        hk = st.hotkey_capture
        steps = [
            f"Bấm {hk} (hoặc chuột trái vào bong bóng cá mập), kéo chuột khoanh vùng chữ. Bấm một lần vào đoạn chữ để dịch cả đoạn, hoặc chọn \"Cả màn hình\".",
            "Cửa sổ dịch mặc định được ghim luôn trên cùng: chuyển sang game hay app đọc truyện vẫn thấy. Bấm \"Đã ghim\" để bỏ ghim. Kéo thanh trên cùng để di chuyển, kéo góc dưới phải để đổi kích thước.",
            "Bôi đen chữ ở trang web hay app đọc truyện rồi bấm Ctrl+C hai lần, hoặc bấm phím tắt dịch chữ đã copy.",
            "Trong cửa sổ dịch, bôi đen một từ ở phần Bản gốc rồi bấm \"Tra từ\" để xem nghĩa theo ngữ cảnh, pinyin và âm Hán Việt.",
            "Game: bấm phím tắt dịch trực tiếp, khoanh khung thoại. Khung dịch tự cập nhật, có nút đổi DeepL/Offline, cỡ chữ, dừng.",
            "Chuột phải vào bong bóng hoặc biểu tượng ở khay hệ thống để mở menu. Đóng cửa sổ này thì app vẫn chạy ở khay hệ thống.",
        ]
        for i, s in enumerate(steps, 1):
            n = QLabel(str(i))
            n.setAlignment(Qt.AlignCenter)
            n.setFixedSize(24, 24)
            n.setFont(theme.head_font(13))
            n.setStyleSheet(f"background:{theme.ACCENT.name()};color:white;border:2px solid {theme.INK.name()};border-radius:12px;")
            t = QLabel(s)
            t.setWordWrap(True)
            w = QWidget()
            h = QHBoxLayout(w)
            h.setContentsMargins(0, 6, 0, 0)
            h.setSpacing(10)
            h.addWidget(n, 0, Qt.AlignTop)
            h.addWidget(t, 1)
            c.add(w)

        foot = _muted(f"{APP_NAME} {VERSION}. Từ điển CC-CEDICT (MDBG, CC BY-SA 4.0). Âm Hán Việt từ Unicode Unihan. "
                      "Nhận dạng chữ: RapidOCR (PaddleOCR). Dịch offline: Opus-MT (Helsinki-NLP).", 12)
        foot.setAlignment(Qt.AlignCenter)
        self.col.addWidget(foot)
        self.update_hotkey_warning([])

    def _build_error(self):
        log = crashlog.read()
        if not log:
            return
        c = Card("App vừa gặp lỗi")
        c.add(_muted("Bấm \"Chép lỗi\" rồi gửi cho người làm app để sửa nhanh hơn."))
        box = QLabel("\n".join(log.splitlines()[3:9]))
        box.setFont(QFont("Consolas", 9))
        box.setWordWrap(True)
        box.setStyleSheet(f"background:{theme.SURFACE.name()};border-radius:10px;padding:6px;")
        c.add(box)
        cp = theme.Chip("Chép lỗi", filled=True)
        cp.clicked.connect(lambda: QGuiApplication.clipboard().setText(log))
        hide = theme.Chip("Ẩn")
        hide.clicked.connect(lambda: (crashlog.clear(), c.hide()))
        c.add(_row(cp, hide))
        self.col.addWidget(c)

    def _build_coffee(self):
        bar = theme.DoodleFrame(theme.BG, 18, 3)
        h = QHBoxLayout(bar)
        h.setContentsMargins(12, 8, 18, 12)
        cup = QLabel()
        cup.setPixmap(theme.svg_pixmap("coffee.svg", 44))
        texts = QWidget()
        v = QVBoxLayout(texts)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        t = QLabel("Buy me a coffee")
        t.setFont(theme.head_font(18))
        v.addWidget(t)
        v.addWidget(_muted("Thấy app hữu ích thì ủng hộ mình một ly cà phê qua MoMo nhé", 13))
        btn = theme.Chip("Ủng hộ", filled=True)
        btn.clicked.connect(self._show_coffee)
        h.addWidget(cup)
        h.addWidget(texts, 1)
        h.addWidget(btn)
        self.col.addWidget(bar)

    def _show_coffee(self):
        from PySide6.QtGui import QPixmap
        d = QDialog(self)
        d.setWindowTitle("Buy me a coffee")
        d.setStyleSheet(f"QDialog{{background:{theme.PAGE.name()};}}" + theme.STYLE)
        v = QVBoxLayout(d)
        t = QLabel("Cảm ơn bạn đã ủng hộ!")
        t.setFont(theme.head_font(20))
        t.setAlignment(Qt.AlignCenter)
        v.addWidget(t)
        v.addWidget(_muted("Quét mã bằng MoMo hoặc app ngân hàng trên điện thoại."))
        img = QLabel()
        pm = QPixmap(str(resource("momo_qr.jpg")))
        img.setPixmap(pm.scaledToWidth(300, Qt.SmoothTransformation))
        img.setAlignment(Qt.AlignCenter)
        v.addWidget(img)

        def save_qr():
            fn, _ = QFileDialog.getSaveFileName(d, "Lưu mã QR", "fishyu_momo_qr.jpg", "Ảnh JPG (*.jpg)")
            if fn:
                pm.save(fn, "JPG", 95)

        sv = theme.Chip("Lưu mã QR")
        sv.clicked.connect(save_qr)
        cl = theme.Chip("Đóng", filled=True)
        cl.clicked.connect(d.accept)
        v.addWidget(_row(sv, cl))
        d.exec()

    def _build_hero(self):
        hero = theme.DoodleFrame(theme.ACCENT_SOFT, 24, 4)
        v = QVBoxLayout(hero)
        v.setContentsMargins(16, 16, 20, 18)
        v.setAlignment(Qt.AlignHCenter)
        m = QLabel()
        m.setPixmap(theme.svg_pixmap("mascot.svg", 150, 128))
        m.setAlignment(Qt.AlignCenter)
        v.addWidget(m)
        t = QLabel("Fishyu Translate")
        t.setFont(theme.head_font(30))
        t.setAlignment(Qt.AlignCenter)
        v.addWidget(t)
        s = QLabel("for Windows")
        s.setFont(theme.head_font(16, QFont.DemiBold))
        s.setAlignment(Qt.AlignCenter)
        s.setStyleSheet(f"color:{theme.ACCENT.name()};")
        v.addWidget(s)
        d = QLabel("Đọc truyện, tài liệu, chơi game tiếng Trung - Nhật bằng tiếng Việt")
        d.setAlignment(Qt.AlignCenter)
        d.setWordWrap(True)
        v.addWidget(d)
        self.col.addWidget(hero)

    def _radios(self, card, options: dict, selected, setter, horizontal=False):
        w = QWidget()
        lay = QHBoxLayout(w) if horizontal else QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        grp = QButtonGroup(w)
        for k, label in options.items():
            r = QRadioButton(label)
            r.setChecked(k == selected)
            r.toggled.connect(lambda on, key=k: on and (setter(key), config.save()))
            grp.addButton(r)
            lay.addWidget(r)
        if horizontal:
            lay.addStretch(1)
        card.add(w)

    def _toggle_bubble(self, v):
        config.get().bubble_visible = v
        config.save()
        self.bubble_toggled.emit(v)

    def _toggle_startup(self, v):
        config.get().start_with_windows = v
        config.save()
        winapi.set_startup(v)

    def _set_hotkey(self, key, edit):
        seq = edit.keySequence().toString(QKeySequence.PortableText)
        setattr(config.get(), key, seq)
        config.save()
        self.hotkeys_changed.emit()

    def update_hotkey_warning(self, failed):
        names = {"capture": "khoanh vùng", "live": "dịch trực tiếp", "clipboard": "chữ đã copy"}
        if failed:
            self.hotkey_warn.setText("Không đăng ký được phím tắt " + ", ".join(names.get(f, f) for f in failed) +
                                     " (đang bị app khác dùng hoặc không hợp lệ). Hãy chọn tổ hợp khác.")
            self.hotkey_warn.show()
        else:
            self.hotkey_warn.hide()

    def _check_key(self):
        self.save()
        self.usage.setText("Đang kiểm tra...")
        run_async(lambda: translator.deepl_usage(), lambda r, e: self.usage.setText(r if not e else f"Lỗi: {e}"))

    def _refresh_offline(self):
        zh = "đã có" if OFFLINE.installed("ZH") else "chưa tải"
        ja = "đã có" if OFFLINE.installed("JA") else "chưa tải"
        self.off_status.setText(f"Gói Trung - Việt: {zh}. Gói Nhật - Việt: {ja}.")

    def _download(self, lang):
        self.off_status.setText("Đang tải gói offline...")

        def prog(done, total):
            self.progress.emit(f"Đang tải gói offline... {done * 100 // max(1, total)}%")

        def finish(_, err):
            if err:
                self.off_status.setText(f"Lỗi: {err}")
            else:
                self._refresh_offline()

        run_async(lambda: OFFLINE.download(lang, prog), finish, "download")
