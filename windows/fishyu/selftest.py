import json
import sys
import time
import traceback


def _arg(name, default=None):
    if name in sys.argv:
        i = sys.argv.index(name)
        if i + 1 < len(sys.argv):
            return sys.argv[i + 1]
    return default


def run() -> int:
    out_path = _arg("--out", "selftest.json")
    want_offline = "--offline" in sys.argv
    results = {}
    ok = True

    def check(name, fn, required=True):
        nonlocal ok
        t = time.monotonic()
        try:
            v = fn()
            results[name] = {"ok": True, "info": v, "sec": round(time.monotonic() - t, 2)}
        except Exception as e:
            results[name] = {"ok": False, "required": required, "error": f"{type(e).__name__}: {e}",
                             "trace": traceback.format_exc()[-1500:]}
            if required:
                ok = False

    from PySide6.QtCore import QRect, Qt
    from PySide6.QtGui import QColor, QFont, QGuiApplication, QImage, QPainter
    from PySide6.QtWidgets import QApplication, QLabel

    app = QApplication(sys.argv)
    from . import VERSION, ocr, translator, winapi
    from .dictionary import DICT
    from .paths import resource
    from .ui import theme

    theme.load_fonts()
    theme.apply_app_font(app)
    app.setStyleSheet(theme.STYLE)

    def pump(sec, until=None):
        end = time.monotonic() + sec
        while time.monotonic() < end:
            app.processEvents()
            if until and until():
                return True
            time.sleep(0.02)
        return bool(until and until())

    def resources():
        missing = [n for n in ("cedict.dat", "hanviet.dat", "bubble.svg", "mascot.svg", "coffee.svg",
                               "app_icon.ico", "momo_qr.jpg", "baloo_bold.ttf") if not resource(n).exists()]
        assert not missing, f"thiếu {missing}"
        return "ok"

    def dictionary():
        assert DICT.ready(60) and DICT.error is None, DICT.error
        e = DICT.lookup("细胞")
        assert e and e[0].pinyin == "xì bāo"
        assert DICT.han_viet("医学") == "y học"
        return len(DICT.words)

    def render(text, family):
        img = QImage(900, 120, QImage.Format_RGB888)
        img.fill(QColor(250, 250, 245))
        p = QPainter(img)
        f = QFont(family)
        f.setPixelSize(40)
        p.setFont(f)
        p.setPen(QColor(20, 20, 20))
        p.drawText(20, 75, text)
        p.end()
        return img

    def ocr_test():
        from .ui.common import qimage_to_np
        r1 = ocr.recognize(qimage_to_np(render("细胞膜是包围细胞质的一层薄膜。", "Microsoft YaHei")))
        assert "细胞膜" in r1.text and r1.lang == "ZH", r1.text
        r2 = ocr.recognize(qimage_to_np(render("先生、今日はどこへ行きますか？", "Yu Gothic")))
        assert "今日" in r2.text and r2.lang == "JA", r2.text
        return [r1.text, r2.text]

    def windows_flags():
        from .ui.bubble import Bubble
        from .ui.live import LiveSession
        from .ui.panel import ResultPanel
        b = Bubble()
        b.restore_position()
        b.show()
        p = ResultPanel()
        p.resize(500, 300)
        p.show()
        s = LiveSession(QRect(200, 200, 400, 100))
        s.frame.show()
        s.box.resize(400, 120)
        s.box.show()
        pump(1.0)
        info = {}
        for name, w, need_noact in (("bubble", b, True), ("panel", p, False), ("livebox", s.box, True),
                                    ("liveframe", s.frame, True)):
            ex = winapi.exstyle(w)
            info[name] = {"topmost": bool(ex & winapi.WS_EX_TOPMOST), "noactivate": bool(ex & winapi.WS_EX_NOACTIVATE),
                          "affinity": winapi.display_affinity(w)}
            assert info[name]["topmost"], f"{name} không nằm trên cùng"
            if need_noact:
                assert info[name]["noactivate"], f"{name} sẽ lấy mất focus của game"
        assert winapi.exstyle(s.frame) & winapi.WS_EX_TRANSPARENT, "khung viền phải cho chuột xuyên qua"
        p.toggle_pin()
        pump(0.3)
        assert not (winapi.exstyle(p) & winapi.WS_EX_TOPMOST), "bỏ ghim không có tác dụng"
        p.toggle_pin()
        pump(0.3)
        assert winapi.exstyle(p) & winapi.WS_EX_TOPMOST, "ghim lại không có tác dụng"
        b.hide(); p.hide(); s.stop()
        return info

    def hotkeys():
        from .hotkeys import HotkeyManager
        hk = HotkeyManager()
        hk.start({"t": "Ctrl+Alt+Shift+F12"})
        failed = list(hk.failed)
        hk.stop()
        assert not failed, "không đăng ký được phím tắt"
        return "ok"

    def capture():
        from .ui.common import grab_screen
        scr = QGuiApplication.primaryScreen()
        img = grab_screen(scr)
        assert not img.isNull() and img.width() > 0
        return [img.width(), img.height(), scr.devicePixelRatio()]

    def live_e2e():
        from .ui import live as live_mod
        from .ui.common import grab_rect
        calls = []

        def fake(text, lang, context=None, engine=None):
            calls.append(text)
            return translator.TranslateResult("[vi] " + text, "DeepL")

        orig = live_mod.translator.translate
        live_mod.translator.translate = fake
        try:
            return _live_body(fake, calls)
        finally:
            live_mod.translator.translate = orig

    def _live_body(fake, calls):
        from .ui import live as live_mod
        from .ui.common import grab_rect
        lbl = QLabel("你好，我们今天去学校吧。")
        lbl.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        f = QFont("Microsoft YaHei")
        f.setPixelSize(36)
        lbl.setFont(f)
        lbl.setStyleSheet("background:#fafaf5;color:#141414;padding:16px;")
        lbl.setGeometry(150, 150, 620, 90)
        lbl.show()
        pump(1.5)
        img, _ = grab_rect(QRect(150, 150, 620, 90))
        if img is None or float(img.std()) < 2:
            return "bỏ qua: máy build không có màn hình để chụp"
        s = live_mod.LiveSession(QRect(150, 150, 620, 90))
        s.start()
        assert pump(90, lambda: "学校" in s.box.translation.text()), f"không dịch được: {s.box.translation.text()} / {s.box.status.text()}"
        n = len(calls)
        pump(4)
        assert len(calls) == n, "chữ không đổi mà vẫn dịch lại"
        lbl.setText("等一下，我还没准备好！")
        assert pump(90, lambda: "准备" in s.box.translation.text()), "không cập nhật khi chữ đổi"
        s.stop()
        lbl.close()
        return calls

    def offline():
        from .offline import OFFLINE
        r = translator.translate("我们走吧，时间不多了。", "ZH", engine="OFFLINE")
        assert r.engine == "Offline" and r.text.strip(), r
        r2 = translator.translate("先生、今日はどこへ行きますか？", "JA", engine="OFFLINE")
        assert r2.text.strip()
        return [r.text, r2.text, str(OFFLINE.path("ZH"))]

    check("version", lambda: VERSION)
    check("resources", resources)
    check("dictionary", dictionary)
    check("ocr", ocr_test)
    if winapi.IS_WIN:
        check("windows_flags", windows_flags)
        check("hotkeys", hotkeys)
    check("capture", capture)
    check("live", live_e2e)
    if want_offline:
        check("offline", offline)
    results["ok"] = ok
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(results, fh, ensure_ascii=False, indent=1)
    return 0 if ok else 1
