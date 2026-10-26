import os
import shutil
from pathlib import Path

import pytest

from fishyu import config, translator
from fishyu.offline import OFFLINE

SRC = os.environ.get("FISHYU_TEST_MODELS")


@pytest.fixture(autouse=True)
def models():
    if not SRC:
        pytest.skip("no local models")
    for l in ("zh", "ja"):
        d = OFFLINE.path("JA" if l == "ja" else "ZH")
        if not OFFLINE.installed("JA" if l == "ja" else "ZH"):
            shutil.copytree(Path(SRC) / f"opus-{l}-vi", d, dirs_exist_ok=True)


def test_offline_zh_ja():
    r = translator.translate("我们走吧，时间不多了。", "ZH", engine="OFFLINE")
    assert r.engine == "Offline" and "thời gian" in r.text.lower()
    r = translator.translate("先生、今日はどこへ行きますか？", "JA", engine="OFFLINE")
    assert "hôm nay" in r.text.lower()


def test_offline_multiline_and_glossary():
    config.get().glossary = "林动 = Lâm Động"
    r = translator.translate("林动握紧了拳头。\n他笑了。", "ZH", engine="OFFLINE")
    print(r.text)
    assert "\n" in r.text
    assert "Lâm Động" in r.text


def test_deepl_without_key_falls_back():
    config.get().deepl_key = ""
    r = translator.translate("你好", "ZH", engine="DEEPL")
    assert r.engine == "Offline" and r.note
