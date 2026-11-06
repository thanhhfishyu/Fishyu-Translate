import numpy as np
import pytest

from fishyu import config, translator
from fishyu.replace import Gate, Piece, Sig, changed, pieces_from, render, zone_of


@pytest.fixture(scope="module")
def app():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def sig(fill=200, cells=()):
    v = np.full((20, 10), fill, dtype=np.int16)
    for i, val in cells:
        v.flat[i] = val
    return Sig(v, 30)


PAGE1 = sig(cells=[(i, 60) for i in range(20, 120, 3)])
PAGE2 = sig(cells=[(i, 70) for i in range(21, 140, 4)])
ZONE = np.zeros((20, 10), dtype=bool)
ZONE.flat[10:150] = True


def feed(g, s, t0, t1, step=0.16):
    out, t = [], t0
    while t <= t1 + 1e-9:
        out.append(g.frame(s, t))
        t += step
    return out


def until_peek(g, s, t0, t1):
    t = t0
    while t <= t1:
        if g.frame(s, t) == Gate.DO_PEEK:
            return True
        t += 0.16
    return False


def shown(g):
    feed(g, PAGE1, 0, 0.7)
    assert g.state == Gate.BUSY
    assert g.ocr_done("a", 0.7)
    g.processed(PAGE1, ZONE)
    assert g.state == Gate.SHOWN and g.needs_reference


def test_static_page_processed_once():
    g = Gate()
    assert Gate.PROCESS not in feed(g, PAGE1, 0, 0.3)
    assert feed(g, PAGE1, 0.46, 0.8).count(Gate.PROCESS) == 1


def test_click_without_change_keeps_overlay():
    g = Gate()
    shown(g)
    covered = sig(cells=[(i, 230) for i in range(10, 150)])
    g.reference(covered)
    g.touch(1.0)
    assert all(a == Gate.NONE for a in feed(g, covered, 1.0, 3.0))
    assert g.state == Gate.SHOWN


def test_page_change_hides_and_reprocesses():
    g = Gate()
    shown(g)
    g.reference(PAGE1)
    assert g.frame(PAGE2, 1.0) == Gate.HIDE
    assert feed(g, PAGE2, 1.16, 1.8).count(Gate.PROCESS) == 1


def test_opaque_overlay_peeks_after_click():
    g = Gate()
    g.peek_on_touch = True
    shown(g)
    covered = sig(cells=[(i, 250) for i in range(10, 150)])
    g.reference(covered)
    g.touch(1.0)
    assert until_peek(g, covered, 1.0, 1.8)
    assert g.frame(PAGE1, 1.95) == Gate.SHOW_CACHED
    g.reference(covered)
    g.touch(3.0)
    assert until_peek(g, covered, 3.0, 3.8)
    g.frame(PAGE2, 3.95)
    assert g.state == Gate.WAIT
    assert Gate.PROCESS in feed(g, PAGE2, 4.1, 4.8)


def test_animated_screen_needs_same_text_twice():
    g = Gate()
    t, flip, acts = 0.0, False, []
    while t < 1.2:
        flip = not flip
        s = sig(cells=[(i, 60) for i in range(20, 120, 3)] + ([(i, 20) for i in range(180, 186)] if flip else []))
        acts.append(g.frame(s, t))
        t += 0.16
    assert Gate.PROCESS in acts and g.animated
    assert not g.ocr_done("first", t)
    again = False
    while t < 2.4 and not again:
        flip = not flip
        s = sig(cells=[(i, 60) for i in range(20, 120, 3)] + ([(i, 20) for i in range(180, 186)] if flip else []))
        again = g.frame(s, t) == Gate.PROCESS
        t += 0.16
    assert again and g.ocr_done("first", t)


def test_zone_mask_and_changed():
    s = Sig(np.zeros((10, 10), dtype=np.int16), 10)
    m = zone_of([(25, 25, 39, 34)], s, grow=0)
    assert m.sum() == 2 * 2
    a = Sig(np.zeros((10, 10), dtype=np.int16), 10)
    b = Sig(np.zeros((10, 10), dtype=np.int16), 10)
    b.v[2, 2] = 50
    assert changed(a, b, 8, m) == pytest.approx(0.25)
    assert changed(a, b, 8) == pytest.approx(0.01)


def _ink(img, rect, color):
    x0, y0, x1, y1 = rect
    s = y1 - y0
    x = x0
    while x + s * 0.8 < x1:
        img[y0 + int(s * .1):y1 - int(s * .1), x + int(s * .1):x + int(s * .2)] = color
        img[y0 + int(s * .45):y0 + int(s * .55), x + int(s * .1):x + int(s * .85)] = color
        img[y0 + int(s * .1):y1 - int(s * .1), x + int(s * .6):x + int(s * .7)] = color
        x += s


def scene():
    img = np.zeros((1400, 1080, 3), dtype=np.uint8)
    img[:] = (250, 246, 236)
    lines1 = [(60, 80 + i * 70, 600 if i == 3 else 1020, 132 + i * 70) for i in range(4)]
    for l in lines1:
        _ink(img, l, (40, 34, 30))
    p1 = Piece((60, 80, 1020, 342), lines1, "细胞膜", "Màng tế bào là một lớp màng mỏng bao quanh tế bào chất, "
                                                     "giúp kiểm soát các chất đi vào và đi ra khỏi tế bào.")
    xs = np.linspace(0, 1, 1080)[None, :, None]
    img[450:900] = (np.array([40, 90, 160]) * (1 - xs) + np.array([200, 120, 60]) * xs).astype(np.uint8)
    l2 = (200, 640, 880, 700)
    _ink(img, l2, (255, 255, 255))
    p2 = Piece(l2, [l2], "我们走吧", "Chúng ta đi thôi!")
    img[1000:] = (30, 40, 60)
    lines3 = [(240, 1080, 840, 1130), (340, 1150, 740, 1200)]
    for l in lines3:
        _ink(img, l, (255, 230, 120))
    p3 = Piece((240, 1080, 840, 1200), lines3, "老师", "Thầy ơi, hôm nay thầy đi đâu vậy?")
    return img, [p1, p2, p3]


def composite(img, layer):
    from fishyu.ui.common import qimage_to_np
    from PySide6.QtGui import QImage, QPainter
    base = QImage(img.data, img.shape[1], img.shape[0], img.shape[1] * 3, QImage.Format_RGB888).copy()
    p = QPainter(base)
    p.drawImage(0, 0, layer)
    p.end()
    return qimage_to_np(base)


def near(a, b, tol):
    return np.all(np.abs(np.asarray(a, dtype=int) - np.asarray(b, dtype=int)) <= tol, axis=-1)


def test_render_erases_and_matches_colors(app, tmp_path):
    img, pieces = scene()
    layer, rects = render(img, pieces, 1.0)
    assert len(rects) == 3
    full = composite(img, layer)
    layer.save(str(tmp_path / "layer.png"))
    from PySide6.QtGui import QImage
    QImage(full.data, full.shape[1], full.shape[0], full.shape[1] * 3, QImage.Format_RGB888).save(str(tmp_path / "full.png"))

    x0, y0, x1, y1 = rects[0]
    reg = full[y0:y1, x0:x1]
    assert near(reg, (250, 246, 236), 12).mean() > 0.6
    assert near(reg, (40, 34, 30), 40).mean() > 0.03

    x0, y0, x1, y1 = rects[1]
    cy = (y0 + y1) // 2
    assert near(full[cy, x0 + 4], img[cy, x0 - 3], 30)

    x0, y0, x1, y1 = rects[2]
    assert near(full[y0:y1, x0:x1], (255, 230, 120), 50).sum() > 20


def test_render_grows_for_long_text(app):
    img = np.full((400, 600, 3), 255, dtype=np.uint8)
    line = (20, 20, 200, 60)
    _ink(img, line, (0, 0, 0))
    p = Piece(line, [line], "好", "Một câu dịch rất dài so với chữ gốc chỉ có vài ký tự nên phải xuống dòng nhiều lần")
    _, rects = render(img, [p], 1.0)
    assert rects[0][3] - rects[0][1] > 60


def test_pieces_from_skips_latin_blocks():
    from fishyu.ocr import Block, Line, OcrResult
    res = OcrResult([Block([Line("Settings", 0, 0, 80, 20)]), Block([Line("设置菜单", 0, 40, 80, 60)])], "ZH")
    ps = pieces_from(res)
    assert [p.source for p in ps] == ["设置菜单"]
    assert ps[0].lines == [(0, 40, 80, 60)]


def test_translate_many_batches_and_caches(monkeypatch):
    st = config.get()
    st.deepl_key = "k:fx"
    calls = []

    def fake_many(texts, lang, context=None):
        calls.append((list(texts), context))
        return [f"vi:{t}" for t in texts]

    monkeypatch.setattr(translator, "deepl_many", fake_many)
    translator._pieces.clear()
    out = translator.translate_many(["一", "二", "一"], "ZH", "一\n二", "DEEPL")
    assert [r.text for r in out] == ["vi:一", "vi:二", "vi:一"]
    assert calls == [(["一", "二"], "一\n二")]
    out = translator.translate_many(["二", "三"], "ZH", "二\n三", "DEEPL")
    assert [r.text for r in out] == ["vi:二", "vi:三"]
    assert calls[-1][0] == ["三"]
    st.deepl_key = ""


def test_manual_session_paints_over_text(app, monkeypatch):
    import time
    from PIL import Image, ImageDraw
    from PySide6.QtGui import QGuiApplication, QImage
    from conftest import cjk_font
    from fishyu.ui import capture
    from fishyu.ui import replace as rep

    scr = QGuiApplication.primaryScreen()
    g = scr.geometry()
    im = Image.new("RGB", (g.width(), g.height()), (250, 250, 245))
    ImageDraw.Draw(im).text((120, 200), "细胞膜是包围细胞质的一层薄膜。", font=cjk_font(44), fill=(20, 20, 20))
    raw = im.tobytes()
    shot = QImage(raw, im.width, im.height, im.width * 3, QImage.Format_RGB888).copy()

    class Fake:
        def grab_screen(self, screen):
            return shot

    monkeypatch.setattr(capture, "_backend", Fake())
    monkeypatch.setattr(rep.translator, "translate_many",
                        lambda texts, lang, context=None, engine=None:
                        [translator.TranslateResult("Màng tế bào là lớp màng mỏng.", "DeepL") for _ in texts])
    s = rep.ReplaceSession(scr)
    s.manual = True
    s.start()
    end = time.monotonic() + 60
    while time.monotonic() < end and not (s.visible and s.last):
        app.processEvents()
        time.sleep(0.02)
    try:
        assert s.visible and s.last
        x0, y0, x1, y1 = s.last[1][0]
        assert x0 < 140 and y0 < 220 and x1 > 600
        assert s.overlay.isVisible()
    finally:
        s.stop()
