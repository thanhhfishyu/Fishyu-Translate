from dataclasses import dataclass

import numpy as np

from .textutil import han_count, has_kana


@dataclass
class Piece:
    box: tuple
    lines: list
    source: str
    text: str = ""


class Sig:
    __slots__ = ("v", "cell")

    def __init__(self, v: np.ndarray, cell: int):
        self.v = v.astype(np.int16)
        self.cell = cell


def signature(img: np.ndarray, cell: int) -> Sig:
    import cv2
    g = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    h, w = g.shape
    cols, rows = max(1, w // cell), max(1, h // cell)
    small = cv2.resize(g[: rows * cell, : cols * cell], (cols, rows), interpolation=cv2.INTER_AREA)
    return Sig(small, cell)


def changed(a: Sig, b: Sig, thr: int, mask=None) -> float:
    if a is None or b is None or a.v.shape != b.v.shape:
        return 1.0
    d = np.abs(a.v - b.v) > thr
    if mask is not None:
        n = int(mask.sum())
        return float(d[mask].sum()) / n if n else 0.0
    return float(d.mean())


def zone_of(rects, sig: Sig, grow=1):
    m = np.zeros(sig.v.shape, dtype=bool)
    rows, cols = m.shape
    c = sig.cell
    for x0, y0, x1, y1 in rects:
        cx0 = max(0, int(x0) // c - grow)
        cx1 = min(cols - 1, int(x1) // c + grow)
        cy0 = max(0, int(y0) // c - grow)
        cy1 = min(rows - 1, int(y1) // c + grow)
        m[cy0:cy1 + 1, cx0:cx1 + 1] = True
    return m


def is_cjk_text(s: str) -> bool:
    return han_count(s) > 0 or has_kana(s)


def pieces_from(res) -> list:
    out = []
    for b in res.blocks:
        src = b.text
        if not is_cjk_text(src):
            continue
        lines = [(int(l.x0), int(l.y0), int(round(l.x1)), int(round(l.y1))) for l in b.lines]
        x0, y0, x1, y1 = b.rect
        out.append(Piece((int(x0), int(y0), int(round(x1)), int(round(y1))), lines, src))
    out.sort(key=lambda p: (p.box[1], p.box[0]))
    return out


def text_key(pieces) -> str:
    return "\n".join(p.source for p in pieces)


class Gate:
    WAIT, BUSY, SHOWN, IDLE, PEEK = "WAIT", "BUSY", "SHOWN", "IDLE", "PEEK"
    NONE, HIDE, PROCESS, SHOW_CACHED, DO_PEEK = "none", "hide", "process", "show_cached", "peek"

    def __init__(self, stable=0.45, quiet=0.45, calm_level=0.12):
        self.stable_s = stable
        self.quiet_s = quiet
        self.calm_level = calm_level
        self.peek_on_touch = False
        self.state = self.WAIT
        self.animated = False
        self.has_render = False
        self._prev = None
        self._stable_since = 0.0
        self._calm_since = 0.0
        self._quiet_until = 0.0
        self._clean = None
        self._ref = None
        self._zone = None
        self._last_key = None
        self._verify_after = 0.0

    @property
    def needs_reference(self):
        return self.state == self.SHOWN and self._ref is None

    def touch(self, now):
        self._quiet_until = max(self._quiet_until, now + self.quiet_s)
        if self.state == self.SHOWN:
            if self.peek_on_touch:
                self._verify_after = now + self.quiet_s
        elif self.state in (self.BUSY, self.IDLE):
            self._to_wait(now)
        return self.NONE

    def frame(self, sig: Sig, now):
        p, self._prev = self._prev, sig
        d = 1.0 if p is None else changed(p, sig, 8)
        if d > 0.004:
            self._stable_since = now
        if d > self.calm_level:
            self._calm_since = now
        if self.state == self.WAIT:
            return self._on_wait(sig, now)
        if self.state == self.BUSY:
            return self.NONE
        if self.state == self.SHOWN:
            return self._on_shown(sig, now)
        if self.state == self.PEEK:
            return self._on_peek(sig, now)
        limit = 0.2 if self.animated else 0.004
        if self._clean is None or changed(self._clean, sig, 8) > limit:
            self._to_wait(now)
        return self.NONE

    def _on_wait(self, sig, now):
        if now < self._quiet_until:
            return self.NONE
        stable = now - self._stable_since >= self.stable_s
        calm = now - self._calm_since >= self.stable_s
        if not stable and not calm:
            return self.NONE
        self.animated = not stable
        if self.has_render and self._clean is not None and changed(self._clean, sig, 8) < 0.003:
            self.state = self.SHOWN
            self._ref = None
            return self.SHOW_CACHED
        self.state = self.BUSY
        return self.PROCESS

    def _on_shown(self, sig, now):
        r = self._ref
        if r is None:
            return self.NONE
        z = self._zone
        if self.animated:
            moved = (z is not None and changed(r, sig, 6, z) > 0.05) or changed(r, sig, 8) > 0.3
        else:
            moved = changed(r, sig, 10) > 0.002 or \
                (not self.peek_on_touch and z is not None and changed(r, sig, 3, z) > 0.03)
        if moved:
            self._to_wait(now)
            return self.HIDE
        settled = now - (self._calm_since if self.animated else self._stable_since) >= self.stable_s
        if self._verify_after and now >= self._verify_after and settled:
            self._verify_after = 0.0
            self.state = self.PEEK
            return self.DO_PEEK
        return self.NONE

    def _on_peek(self, sig, now):
        if self._clean is not None and changed(self._clean, sig, 8) < 0.003:
            self.state = self.SHOWN
            self._ref = None
            return self.SHOW_CACHED
        self._to_wait(now)
        return self.NONE

    def ocr_done(self, key, now) -> bool:
        if not self.animated:
            self._last_key = key
            return True
        if key == self._last_key:
            return True
        self._last_key = key
        self.state = self.WAIT
        self._stable_since = now
        self._calm_since = now - self.stable_s + 0.2
        return False

    def processed(self, sig, zone):
        self._clean = sig
        if zone is not None:
            self._zone = zone
            self.has_render = True
            self.state = self.SHOWN
            self._ref = None
        else:
            self.has_render = False
            self.state = self.IDLE

    def reference(self, sig):
        if self.state == self.SHOWN:
            self._ref = sig

    def abort(self, now):
        if self.state == self.BUSY:
            self._to_wait(now)

    def failed(self, now, retry=4.0):
        self._quiet_until = now + retry
        self._to_wait(now)

    def reset(self, now):
        self._clean = None
        self.has_render = False
        self._last_key = None
        self._prev = None
        self._to_wait(now)

    def _to_wait(self, now):
        self._verify_after = 0.0
        self.state = self.WAIT
        self._ref = None
        self._stable_since = now
        self._calm_since = now


def _median_color(a: np.ndarray):
    return np.median(a.reshape(-1, 3), axis=0)


def _ring(px, a, band):
    h, w = px.shape[:2]
    x0, y0, x1, y1 = a
    parts = [px[max(0, y0 - band):y0, max(0, x0 - band):min(w, x1 + band)],
             px[y1:min(h, y1 + band), max(0, x0 - band):min(w, x1 + band)],
             px[y0:y1, max(0, x0 - band):x0],
             px[y0:y1, x1:min(w, x1 + band)]]
    parts = [p.reshape(-1, 3) for p in parts if p.size]
    if not parts:
        return np.zeros((0, 3))
    s = np.concatenate(parts).astype(np.float32)
    if len(s) > 6000:
        s = s[:: len(s) // 6000 + 1]
    return s


def _smooth(a: np.ndarray, r: int):
    if len(a) < 3 or r < 1:
        return a
    k = np.ones(2 * r + 1, dtype=np.float32) / (2 * r + 1)
    pad = np.pad(a, ((r, r), (0, 0)), mode="edge")
    return np.stack([np.convolve(pad[:, c], k, mode="valid") for c in range(3)], axis=1)


def _edge(px, a, band, side):
    h, w = px.shape[:2]
    x0, y0, x1, y1 = a
    if side == "top" and y0 - 1 >= 0:
        e = px[max(0, y0 - band):y0, x0:x1].astype(np.float32).mean(axis=0)
    elif side == "bottom" and y1 < h:
        e = px[y1:min(h, y1 + band), x0:x1].astype(np.float32).mean(axis=0)
    elif side == "left" and x0 - 1 >= 0:
        e = px[y0:y1, max(0, x0 - band):x0].astype(np.float32).mean(axis=1)
    elif side == "right" and x1 < w:
        e = px[y0:y1, x1:min(w, x1 + band)].astype(np.float32).mean(axis=1)
    else:
        return None
    return _smooth(e, max(1, band))


def background(px, a, band):
    ring = _ring(px, a, band)
    if len(ring) == 0:
        med = np.array([255.0, 255.0, 255.0])
        return med, None, med
    med = np.median(ring, axis=0)
    close = np.abs(ring - med).mean(axis=1) <= 22
    if close.mean() >= 0.88:
        return med, None, med
    x0, y0, x1, y1 = a
    aw, ah = x1 - x0, y1 - y0
    t = _edge(px, a, band, "top")
    b = _edge(px, a, band, "bottom")
    t = t if t is not None else b
    if t is None:
        return med, None, med
    b = b if b is not None else t
    l = _edge(px, a, band, "left")
    r = _edge(px, a, band, "right")
    l = l if l is not None else r
    r = r if r is not None else l
    v = np.linspace(0, 1, ah, dtype=np.float32)[:, None, None]
    u = np.linspace(0, 1, aw, dtype=np.float32)[None, :, None]
    vert = (1 - v) * t[None, :, :] + v * b[None, :, :]
    if l is None:
        patch = vert
    else:
        horiz = (1 - u) * l[:, None, :] + u * r[:, None, :]
        p00, p10, p01, p11 = t[0], t[-1], b[0], b[-1]
        corner = (1 - u) * (1 - v) * p00 + u * (1 - v) * p10 + (1 - u) * v * p01 + u * v * p11
        patch = vert + horiz - corner
    return None, np.clip(patch, 0, 255).astype(np.uint8), med


def _luma(c):
    return 0.30 * c[0] + 0.59 * c[1] + 0.11 * c[2]


def _contrast(bg):
    return np.array([20, 24, 30]) if _luma(bg) > 140 else np.array([250, 250, 250])


def _centered(lines, line_h):
    if len(lines) < 2:
        return False
    lefts = [l[0] for l in lines]
    centers = [(l[0] + l[2]) / 2 for l in lines]
    sl = max(lefts) - min(lefts)
    sc = max(centers) - min(centers)
    return sl > line_h * 0.8 and sc < sl * 0.5


def _clip(a, w, h):
    x0, y0, x1, y1 = a
    x0, y0 = max(0, x0), max(0, y0)
    x1, y1 = min(w, x1), min(h, y1)
    return (x0, y0, x1, y1) if x1 > x0 and y1 > y0 else None


def render(img: np.ndarray, pieces, scale=1.0, family=""):
    from PySide6.QtCore import QRect, Qt
    from PySide6.QtGui import QColor, QFont, QFontMetrics, QImage, QPainter

    h, w = img.shape[:2]
    out = QImage(w, h, QImage.Format_ARGB32_Premultiplied)
    out.fill(Qt.transparent)
    painted = []
    p = QPainter(out)
    p.setRenderHint(QPainter.Antialiasing)
    p.setRenderHint(QPainter.TextAntialiasing)
    try:
        for pc in pieces:
            if not pc.text.strip():
                continue
            try:
                r = _draw_piece(p, img, w, h, pc, scale, family, QRect, Qt, QColor, QFont, QFontMetrics, QImage)
            except Exception:
                r = None
            if r:
                painted.append(r)
    finally:
        p.end()
    return out, painted


def _draw_piece(p, px, w, h, pc, scale, family, QRect, Qt, QColor, QFont, QFontMetrics, QImage):
    lines = [l for l in pc.lines if l[2] > l[0] and l[3] > l[1]] or [pc.box]
    vertical = sum(1 for l in lines if (l[3] - l[1]) > (l[2] - l[0]) * 1.6) * 2 > len(lines)
    line_h = max(6, int(np.median([min(l[2] - l[0], l[3] - l[1]) for l in lines])))
    pad = max(2, round(line_h * 0.14))
    band = max(3, round(line_h * 0.2))
    x0 = min([pc.box[0]] + [l[0] for l in lines]) - pad
    y0 = min([pc.box[1]] + [l[1] for l in lines]) - pad
    x1 = max([pc.box[2]] + [l[2] for l in lines]) + pad
    y1 = max([pc.box[3]] + [l[3] for l in lines]) + pad
    area = _clip((x0, y0, x1, y1), w, h)
    if not area:
        return None

    solid, patch, mean = background(px, area, band)

    def bg_at(sub_a):
        sx0, sy0, sx1, sy1 = sub_a
        if solid is not None:
            return np.broadcast_to(solid, (sy1 - sy0, sx1 - sx0, 3))
        return patch[sy0 - area[1]:sy1 - area[1], sx0 - area[0]:sx1 - area[0]].astype(np.float32)

    ink, seen = [], 0
    for ln in lines:
        la = _clip(ln, w, h)
        if not la:
            continue
        la = (max(la[0], area[0]), max(la[1], area[1]), min(la[2], area[2]), min(la[3], area[3]))
        if la[2] <= la[0] or la[3] <= la[1]:
            continue
        step = max(1, min(la[2] - la[0], la[3] - la[1]) // 18)
        sub = px[la[1]:la[3]:step, la[0]:la[2]:step].astype(np.float32)
        bg = bg_at(la)[::step, ::step]
        d = np.abs(sub - bg).mean(axis=2)
        seen += d.size
        sel = d > 60
        if sel.any():
            ink.append((sub[sel], d[sel]))
    ratio = 0.0
    if ink:
        cols = np.concatenate([a for a, _ in ink])
        ds = np.concatenate([b for _, b in ink])
        ratio = len(cols) / max(1, seen)
    if ratio < 0.02:
        color = _contrast(mean)
    else:
        order = np.argsort(-ds)[: max(1, len(ds) // 2)]
        color = np.median(cols[order], axis=0)
    if abs(_luma(color) - _luma(mean)) < 60:
        color = _contrast(mean)

    font = QFont(family) if family else QFont()
    font.setBold(ratio > 0.27)
    align = (Qt.AlignHCenter if _centered(lines, line_h) and not vertical else Qt.AlignLeft) | Qt.AlignTop
    flags = int(align) | int(Qt.TextWordWrap)
    ax0, ay0, ax1, ay1 = area
    min_w = line_h * 3 if vertical else line_h
    if ax1 - ax0 - pad * 2 < min_w:
        grow = (min_w - (ax1 - ax0 - pad * 2) + 1) // 2
        ax0, ax1 = max(0, ax0 - grow), min(w, ax1 + grow)
    inner_w = max(4, ax1 - ax0 - pad * 2)
    inner_h = max(4, ay1 - ay0 - pad * 2)
    text = pc.text.strip()

    def measure(size):
        font.setPixelSize(max(1, int(size)))
        return QFontMetrics(font).boundingRect(QRect(0, 0, inner_w, 100000), flags, text).height()

    max_fs = line_h * 0.84
    min_fs = min(max(11 * scale, line_h * 0.4), max_fs)
    if measure(max_fs) <= inner_h:
        fs = max_fs
    elif measure(min_fs) <= inner_h:
        lo, hi = min_fs, max_fs
        for _ in range(9):
            mid = (lo + hi) / 2
            if measure(mid) <= inner_h:
                lo = mid
            else:
                hi = mid
        fs = lo
    else:
        fs = min_fs
        need = measure(fs) + pad * 2
        ay1 = ay0 + need
        if ay1 > h:
            ay0, ay1 = max(0, h - need), h
    font.setPixelSize(max(1, int(fs)))
    text_h = QFontMetrics(font).boundingRect(QRect(0, 0, inner_w, 100000), flags, text).height()

    final = (ax0, ay0, ax1, ay1)
    if final != area:
        solid, patch, mean = background(px, final, band)
    fw, fh = ax1 - ax0, ay1 - ay0
    if solid is not None:
        p.fillRect(QRect(ax0, ay0, fw, fh), QColor(int(solid[0]), int(solid[1]), int(solid[2])))
    else:
        buf = np.ascontiguousarray(patch)
        qi = QImage(buf.data, fw, fh, fw * 3, QImage.Format_RGB888).copy()
        p.drawImage(ax0, ay0, qi)

    p.setFont(font)
    dy = max(0, (fh - pad * 2 - text_h) // 2)
    box = QRect(ax0 + pad, ay0 + pad + dy, inner_w, max(text_h, 1) + 2)
    if solid is None:
        halo = QColor(int(mean[0]), int(mean[1]), int(mean[2]))
        p.setPen(halo)
        r = max(1, round(fs * 0.08))
        for ox, oy in ((-r, 0), (r, 0), (0, -r), (0, r), (-r, -r), (r, r), (-r, r), (r, -r)):
            p.drawText(box.translated(ox, oy), flags, text)
    p.setPen(QColor(int(color[0]), int(color[1]), int(color[2])))
    p.drawText(box, flags, text)
    return final
