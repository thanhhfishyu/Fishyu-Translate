import numpy as np
import pytest
from PIL import Image, ImageDraw, ImageFont

from fishyu import ocr

from conftest import cjk_font


def render(lines_xy, size=(900, 420)):
    f = cjk_font(30)
    im = Image.new("RGB", size, (250, 250, 245))
    d = ImageDraw.Draw(im)
    for (x, y, t) in lines_xy:
        d.text((x, y), t, font=f, fill=(25, 25, 25))
    return np.array(im)


def test_zh_ja_tw():
    img = render([(20, 20, "细胞膜是包围细胞质的一层薄膜。")], (700, 90))
    r = ocr.recognize(img)
    assert r.text == "细胞膜是包围细胞质的一层薄膜。" and r.lang == "ZH"
    img = render([(20, 20, "先生、今日はどこへ行きますか？")], (700, 90))
    r = ocr.recognize(img)
    assert r.text == "先生、今日はどこへ行きますか？" and r.lang == "JA"


def test_paragraph_grouping_and_tap():
    img = render([(20, 20, "第一段第一行文字内容"), (20, 62, "第一段第二行文字"),
                  (20, 220, "第二段只有一行文字"), (480, 330, "右下角的按钮")])
    r = ocr.recognize(img)
    texts = [b.text for b in r.blocks]
    assert "第一段第一行文字内容第一段第二行文字" in texts
    b = ocr.block_at(r, 60, 75)
    assert b.text.startswith("第一段第一行")
    b = ocr.block_at(r, 100, 235)
    assert b.text == "第二段只有一行文字"


def test_tiny_crop_upscaled():
    img = render([(2, 2, "你好世界")], (140, 40))
    r = ocr.recognize(img)
    assert "你好" in r.text


def test_empty_image():
    r = ocr.recognize(np.full((100, 100, 3), 255, np.uint8))
    assert r.text == "" and r.blocks == []
