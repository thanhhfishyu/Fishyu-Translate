import time

import numpy as np
import pytest
from PIL import Image, ImageDraw, ImageFont
from PySide6.QtCore import QRect, QPoint
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication

from fishyu import config, translator
from fishyu.ui import theme

from conftest import cjk_font
calls = []


def fake_translate(text, lang, context=None, engine=None):
    calls.append((text, lang, context, engine))
    return translator.TranslateResult(f"[vi] {text}", "DeepL")


@pytest.fixture(scope="module")
def app():
    a = QApplication.instance() or QApplication([])
    theme.load_fonts()
    theme.apply_app_font(a)
    a.setStyleSheet(theme.STYLE)
    yield a


@pytest.fixture(autouse=True)
def fake(monkeypatch):
    calls.clear()
    monkeypatch.setattr(translator, "translate", fake_translate)


def pump(app, secs=0.5, until=None):
    end = time.monotonic() + secs
    while time.monotonic() < end:
        app.processEvents()
        if until and until():
            return True
        time.sleep(0.02)
    return bool(until and until())


def render(text, size=(900, 300), pos=(40, 60)):
    f = cjk_font(34)
    im = Image.new("RGB", size, (245, 245, 240))
    ImageDraw.Draw(im).text(pos, text, font=f, fill=(20, 20, 20))
    return np.array(im)


def np_to_qimage(a):
    h, w, _ = a.shape
    return QImage(a.tobytes(), w, h, w * 3, QImage.Format_RGB888).copy()


def test_controller_and_settings(app, tmp_path):
    from fishyu.ui.app import Controller
    ctl = Controller(app)
    assert ctl.settings.isVisible()
    assert ctl.bubble.isVisible()
    g = ctl.bubble.geometry()
    scr = app.primaryScreen().availableGeometry()
    assert scr.contains(g)
    ctl.settings.grab().save(str(tmp_path / "settings.png"))
    ctl.quit_called = False
    pytest.ctl = ctl


def test_panel_translate(app):
    ctl = pytest.ctl
    p = ctl.open_panel("细胞膜是包围细胞质的一层薄膜。")
    assert pump(app, 5, lambda: p.translation.text().startswith("[vi]"))
    assert calls[0][1] == "ZH"
    assert len(ctl.panels) == 1
    p2 = ctl.open_panel("先生、今日はどこへ行きますか？")
    assert pump(app, 5, lambda: p2.translation.text().startswith("[vi]"))
    assert calls[-1][1] == "JA"
    assert len(ctl.panels) == 1
    p2.toggle_pin()
    assert p2.pinned is False and config.get().panel_pinned is False
    p2.toggle_pin()
    assert p2.pinned is True
    p2.close_panel()
    assert ctl.panels == []


def test_region_and_tap_flow(app):
    from fishyu.ui.selector import RegionSelector
    ctl = pytest.ctl
    arr = render("第一段第一行文字内容\n第一段第二行文字", (900, 300))
    img = np_to_qimage(arr)
    scr = app.primaryScreen()
    sel = RegionSelector(scr, img, "hint", "Cả màn hình")
    ctl.selectors = [sel]
    k = sel.scale
    ctl._on_region(sel, QRect(int(30 / k), int(50 / k), int(500 / k), int(120 / k)), False)
    assert ctl.selectors == []
    p = ctl.panels[0]
    assert pump(app, 20, lambda: p.translation.text().startswith("[vi]"))
    assert "第一段" in calls[-1][0]
    first = ctl.panels[0]
    sel = RegionSelector(scr, img, "hint", "Cả màn hình")
    ctl.selectors = [sel]
    ctl._op += 1
    ctl._on_tap(sel, QPoint(int(100 / k), int(80 / k)), False)
    assert pump(app, 20, lambda: ctl.panels and ctl.panels[0] is not first
                and ctl.panels[0].translation.text().startswith("[vi]"))
    assert calls[-1][0].startswith("第一段第一行文字内容")


def test_live_session(app, monkeypatch):
    from fishyu.ui import live as live_mod
    frames = {"img": render("先生、今日はどこへ行きますか？", (700, 120), (20, 30))}
    monkeypatch.setattr(live_mod, "grab_rect", lambda r: (frames["img"].copy(), 1.0))
    ctl = pytest.ctl
    ctl.start_live(QRect(100, 100, 700, 120))
    s = ctl.live
    assert s and s.box.isVisible()
    assert ctl.panels == []
    assert pump(app, 30, lambda: s.box.translation.text().startswith("[vi] 先生"))
    n = len(calls)
    pump(app, 3)
    assert len(calls) == n, "static text must not be re-translated"
    frames["img"] = render("シャーレの仕事が終わったら行こう。", (700, 120), (20, 30))
    assert pump(app, 40, lambda: "シャーレ" in s.box.translation.text())
    assert len(calls) == n + 1
    frames["img"] = render("Cài đặt Tin nhắn", (700, 120), (20, 30))
    pump(app, 4)
    assert len(calls) == n + 1
    s.toggle_engine()
    assert config.get().live_engine == "OFFLINE"
    s.toggle_engine()
    ctl.start_capture  # attribute exists
    s.set_hidden(True)
    assert not s.box.isVisible()
    s.set_hidden(False)
    assert s.box.isVisible()
    ctl.stop_live()
    assert ctl.live is None


def test_stale_result_ignored(app):
    from fishyu.ui.selector import RegionSelector
    ctl = pytest.ctl
    img = np_to_qimage(render("迟到的结果不应该弹出"))
    sel = RegionSelector(app.primaryScreen(), img, "hint", "x")
    ctl.selectors = [sel]
    ctl._on_tap(sel, QPoint(50, 50), False)
    ctl.start_live(QRect(100, 100, 300, 80))
    pump(app, 8)
    assert ctl.panels == []
    ctl.stop_live()


def test_double_copy(app):
    ctl = pytest.ctl
    cb = app.clipboard()
    config.get().double_copy = True
    cb.setText("我们走吧")
    pump(app, 0.1)
    cb.setText("我们走吧")
    assert pump(app, 5, lambda: ctl.panels and ctl.panels[0].translation.text().startswith("[vi]"))
    ctl.close_panels()


def test_hotkey_parse():
    from fishyu.hotkeys import parse
    assert parse("Ctrl+Alt+Q") == (0x3, ord("Q"))
    assert parse("Ctrl+Shift+F12") == (0x6, 0x7B)
    assert parse("Q") is None
    assert parse("") is None
    assert parse("Ctrl+Alt+Nope") is None
