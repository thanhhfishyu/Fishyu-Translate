import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("APPDATA", tempfile.mkdtemp(prefix="fishyu-test-"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def cjk_font(size):
    from PIL import ImageFont
    for path, idx in (("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", 2),
                      ("C:/Windows/Fonts/msyh.ttc", 0), ("C:/Windows/Fonts/msyh.ttf", 0),
                      ("C:/Windows/Fonts/YuGothM.ttc", 0)):
        if os.path.exists(path):
            return ImageFont.truetype(path, size, index=idx)
    raise RuntimeError("no CJK font")
