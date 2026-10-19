import threading
from dataclasses import dataclass, field

import numpy as np

from .textutil import detect_lang, join_lines


@dataclass
class Line:
    text: str
    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def h(self):
        return self.y1 - self.y0


@dataclass
class Block:
    lines: list = field(default_factory=list)

    @property
    def rect(self):
        return (min(l.x0 for l in self.lines), min(l.y0 for l in self.lines),
                max(l.x1 for l in self.lines), max(l.y1 for l in self.lines))

    @property
    def text(self):
        return join_lines(l.text for l in self.lines)


@dataclass
class OcrResult:
    blocks: list
    lang: str

    @property
    def text(self):
        return "\n".join(b.text for b in self.blocks).strip()


_engine = None
_lock = threading.Lock()


def _get_engine():
    global _engine
    if _engine is None:
        from rapidocr import RapidOCR
        _engine = RapidOCR(params={"Global.log_level": "error"})
    return _engine


def warmup():
    try:
        recognize(np.full((48, 160, 3), 255, dtype=np.uint8))
    except Exception:
        pass


def merge_rows(pieces):
    rows = []
    for pc in sorted(pieces, key=lambda l: (l.y0 + l.y1) / 2):
        target = None
        for row in rows:
            top = min(p.y0 for p in row)
            bot = max(p.y1 for p in row)
            ov = min(bot, pc.y1) - max(top, pc.y0)
            if ov > 0.5 * min(pc.h, bot - top):
                gap_ok = any(min(abs(pc.x0 - p.x1), abs(p.x0 - pc.x1)) < 3 * max(pc.h, p.h) for p in row)
                if gap_ok:
                    target = row
                    break
        if target is None:
            rows.append([pc])
        else:
            target.append(pc)
    out = []
    for row in rows:
        row.sort(key=lambda p: p.x0)
        out.append(Line(join_lines(p.text for p in row), min(p.x0 for p in row), min(p.y0 for p in row),
                        max(p.x1 for p in row), max(p.y1 for p in row)))
    return out


def group_lines(lines):
    lines = sorted(merge_rows(lines), key=lambda l: (l.y0, l.x0))
    blocks = []
    for ln in lines:
        target = None
        for b in reversed(blocks):
            last = b.lines[-1]
            bx0, by0, bx1, by1 = b.rect
            gap = ln.y0 - last.y1
            ref = max(1.0, min(ln.h, last.h))
            overlap = min(bx1, ln.x1) - max(bx0, ln.x0)
            if -ref * 0.5 <= gap <= ref * 0.9 and overlap > 0.3 * min(ln.x1 - ln.x0, bx1 - bx0) \
                    and abs(ln.h - last.h) <= 0.45 * max(ln.h, last.h):
                target = b
                break
        if target is None:
            blocks.append(Block([ln]))
        else:
            target.lines.append(ln)
    return blocks


def recognize(img: np.ndarray, pref: str = "AUTO") -> OcrResult:
    if img is None or img.size == 0:
        return OcrResult([], "ZH")
    h, w = img.shape[:2]
    scale = 1.0
    if min(h, w) < 48:
        scale = 48.0 / min(h, w)
        import cv2
        img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_CUBIC)
    with _lock:
        out = _get_engine()(img)
    lines = []
    boxes = getattr(out, "boxes", None)
    txts = getattr(out, "txts", None) or ()
    if boxes is not None:
        for box, txt in zip(boxes, txts):
            xs = [p[0] / scale for p in box]
            ys = [p[1] / scale for p in box]
            if txt and txt.strip():
                lines.append(Line(txt.strip(), min(xs), min(ys), max(xs), max(ys)))
    blocks = group_lines(lines)
    full = " ".join(l.text for l in lines)
    return OcrResult(blocks, detect_lang(full, pref))


def block_at(res: OcrResult, x: float, y: float, pad: float = 14):
    best = None
    for b in res.blocks:
        x0, y0, x1, y1 = b.rect
        if x0 - pad <= x <= x1 + pad and y0 - pad <= y <= y1 + pad:
            return b
    for b in res.blocks:
        x0, y0, x1, y1 = b.rect
        cy = (y0 + y1) / 2
        cx = (x0 + x1) / 2
        d = abs(cy - y) + abs(cx - x) / 2
        if abs(cy - y) < 80 + (y1 - y0) / 2 and (best is None or d < best[0]):
            best = (d, b)
    return best[1] if best else None
