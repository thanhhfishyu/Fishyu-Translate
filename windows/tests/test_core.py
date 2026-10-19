import os
from pathlib import Path

import numpy as np
import pytest

from fishyu import config, livegate, textutil, translator
from fishyu.dictionary import DICT


def run(g, frames):
    calls = 0
    for f in frames:
        d = g.offer(f)
        if d.kind == livegate.Decision.TRANSLATE:
            calls += 1
            g.remember(d.norm, "vi:" + f)
    return calls


def test_static_dialog_translated_once():
    assert run(livegate.LiveGate(), ["先生、今日はどこへ行きますか？"] * 30) == 1


def test_ocr_noise_not_retranslated():
    frames = ["先生、今日の任務は何ですか？", "先生、今日の任務は何ですか？", "先生、今日の任務は何ですか",
              "先生、今日の任務は向ですか？", "先生 今日の任務は何ですか？", "先生、今日の仕務は何ですか？",
              "・先生、今日の任務は何ですか？", "先生、今日の任務は何ですか？。"]
    assert run(livegate.LiveGate(), frames) == 1


def test_typewriter_waits_full_line():
    g = livegate.LiveGate()
    full = "这个世界上没有不劳而获的东西"
    last = ""
    for f in [full[:i] for i in range(2, len(full) + 1)] + [full] * 3:
        d = g.offer(f)
        if d.kind == livegate.Decision.TRANSLATE:
            last = f
            g.remember(d.norm, f)
    assert last == full


def test_repeats_reused():
    g = livegate.LiveGate()
    a, b = "我们走吧，时间不多了。", "等一下，我还没准备好！"
    calls = reuses = 0
    for f in [a, a, a, b, b, b, a, a, a]:
        d = g.offer(f)
        if d.kind == livegate.Decision.TRANSLATE:
            calls += 1
            g.remember(d.norm, "x")
        elif d.kind == livegate.Decision.REUSE:
            reuses += 1
    assert (calls, reuses) == (2, 1)


def test_vietnamese_ignored():
    assert run(livegate.LiveGate(), ["Cài đặt Tin nhắn Điện thoại Máy ảnh"] * 10) == 0


def test_detect_lang():
    assert textutil.detect_lang("先生、今日はどこへ行きますか？") == "JA"
    assert textutil.detect_lang("细胞膜是包围细胞质的一层薄膜") == "ZH"
    assert textutil.detect_lang("细胞膜", "JA") == "JA"


def test_join_lines():
    assert textutil.join_lines(["细胞 膜是", "包围细胞质"]) == "细胞膜是包围细胞质"
    assert textutil.join_lines(["Hello", "world"]) == "Hello world"


def test_dictionary():
    assert DICT.ready(60)
    assert DICT.error is None
    e = DICT.lookup("细胞")
    assert e and e[0].pinyin == "xì bāo" and "cell" in e[0].defs
    assert DICT.han_viet("医学") == "y học"
    assert DICT.segment("心肌梗死是疾病") [0] == "心肌梗死"


def test_glossary_xml():
    config.get().glossary = "林动 = Lâm Động\n# note\n林 = Lâm\nbad line"
    pairs = config.get().glossary_pairs()
    assert pairs[0] == ("林动", "Lâm Động")
    s = translator.apply_glossary_xml("林动看着林<b>", pairs)
    assert s == "<x>Lâm Động</x>看着<x>Lâm</x>&lt;b&gt;"


def test_split_sentences():
    assert translator.split_sentences("你好。我很好！真的吗？") == ["你好。", "我很好！", "真的吗？"]


def test_settings_roundtrip(tmp_path, monkeypatch):
    config.get().deepl_key = "abc:fx"
    config.save()
    config.reset_for_tests()
    assert config.get().deepl_key == "abc:fx"
    p = Path(os.environ["APPDATA"]) / "FishyuTranslate" / "settings.json"
    p.write_text('{"live_font": 999, "engine": "NOPE", "deepl_key": 5}', encoding="utf-8")
    config.reset_for_tests()
    s = config.get()
    assert s.live_font == 32 and s.engine == "DEEPL" and s.deepl_key == ""
    p.write_text("not json", encoding="utf-8")
    config.reset_for_tests()
    assert config.get().engine == "DEEPL"
