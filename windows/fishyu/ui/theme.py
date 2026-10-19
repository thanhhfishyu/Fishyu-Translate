from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QFontDatabase, QIcon, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QFrame, QPushButton, QSizePolicy

from ..paths import resource

PAGE = QColor("#EEF5FD")
BG = QColor("#FFFFFF")
SURFACE = QColor("#EAF2FC")
FG = QColor("#1E2A38")
MUTED = QColor("#5E6B7C")
INK = QColor("#2B3442")
ACCENT = QColor("#3F7FD0")
ACCENT_SOFT = QColor("#A9C6EE")
LINE = QColor("#D3E2F4")
ERROR = QColor("#C0392B")

HEAD_FAMILY = "Segoe UI"
BODY_FAMILY = "Segoe UI"


def load_fonts():
    global HEAD_FAMILY
    for f in ("baloo_bold.ttf", "baloo_medium.ttf"):
        fid = QFontDatabase.addApplicationFont(str(resource(f)))
        if fid >= 0 and f == "baloo_bold.ttf":
            fams = QFontDatabase.applicationFontFamilies(fid)
            if fams:
                HEAD_FAMILY = fams[0]


def apply_app_font(app):
    app.setFont(body_font(14))


def head_font(px: int, weight=QFont.Bold) -> QFont:
    f = QFont(HEAD_FAMILY)
    f.setPixelSize(px)
    f.setWeight(weight)
    return f


def body_font(px: int, weight=QFont.Normal) -> QFont:
    f = QFont(BODY_FAMILY)
    f.setPixelSize(px)
    f.setWeight(weight)
    return f


def svg_pixmap(name: str, w: int, h: int = None, dpr: float = 2.0) -> QPixmap:
    h = h or w
    r = QSvgRenderer(str(resource(name)))
    pm = QPixmap(int(w * dpr), int(h * dpr))
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    r.render(p)
    p.end()
    pm.setDevicePixelRatio(dpr)
    return pm


def app_icon() -> QIcon:
    ic = QIcon(str(resource("app_icon.ico")))
    if ic.isNull():
        ic = QIcon(str(resource("app_icon.png")))
    return ic


def paint_doodle(p: QPainter, rect: QRectF, fill: QColor, radius=16.0, shadow=4.0, border=2.0, pressed=False):
    p.setRenderHint(QPainter.Antialiasing)
    r = QRectF(rect.x() + border / 2, rect.y() + border / 2,
               rect.width() - shadow - border, rect.height() - shadow - border)
    if not pressed:
        path = QPainterPath()
        path.addRoundedRect(r.translated(shadow, shadow), radius, radius)
        p.fillPath(path, INK)
    else:
        r = r.translated(shadow, shadow)
    path = QPainterPath()
    path.addRoundedRect(r, radius, radius)
    p.fillPath(path, fill)
    p.setPen(QPen(INK, border))
    p.drawPath(path)


class DoodleFrame(QFrame):
    def __init__(self, fill=BG, radius=18.0, shadow=4.0, parent=None):
        super().__init__(parent)
        self.fill = QColor(fill)
        self.radius = radius
        self.shadow = shadow
        self.setAttribute(Qt.WA_TranslucentBackground, True)

    def paintEvent(self, e):
        p = QPainter(self)
        paint_doodle(p, QRectF(self.rect()), self.fill, self.radius, self.shadow)
        p.end()


class Chip(QPushButton):
    def __init__(self, text, filled=False, small=True, parent=None):
        super().__init__(text, parent)
        self.filled = filled
        self.shadow = 2.0 if small else 4.0
        self.setCursor(Qt.PointingHandCursor)
        self.setFont(head_font(13 if small else 16, QFont.DemiBold if small else QFont.Bold))
        self.setSizePolicy(QSizePolicy.Maximum if small else QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setFlat(True)
        self._pad = (12, 5) if small else (18, 9)
        self.setStyleSheet("QPushButton{border:none;background:transparent;}")

    def set_filled(self, f):
        self.filled = f
        self.update()

    def sizeHint(self):
        fm = self.fontMetrics()
        w = fm.horizontalAdvance(self.text()) + self._pad[0] * 2 + int(self.shadow) + 4
        h = fm.height() + self._pad[1] * 2 + int(self.shadow) + 2
        return QSize(w, h)

    def paintEvent(self, e):
        p = QPainter(self)
        fill = ACCENT if self.filled else BG
        if not self.isEnabled():
            fill = SURFACE
        paint_doodle(p, QRectF(self.rect()), fill, 13.0 if self.shadow < 3 else 16.0, self.shadow, 2.0,
                     pressed=self.isDown())
        p.setPen(QColor("#FFFFFF") if self.filled and self.isEnabled() else (FG if self.isEnabled() else MUTED))
        p.setFont(self.font())
        off = self.shadow if self.isDown() else 0
        r = self.rect().adjusted(int(off), int(off), -int(self.shadow - off), -int(self.shadow - off))
        p.drawText(r, Qt.AlignCenter, self.text())
        p.end()


STYLE = f"""
QWidget {{ color: {FG.name()}; }}
QLineEdit, QPlainTextEdit, QTextEdit, QKeySequenceEdit QLineEdit {{
  background: {SURFACE.name()}; border: 2px solid {ACCENT_SOFT.name()}; border-radius: 12px;
  padding: 7px 10px; selection-background-color: {ACCENT.name()}; selection-color: white;
}}
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus {{ border-color: {ACCENT.name()}; }}
QRadioButton, QCheckBox {{ spacing: 8px; padding: 3px 0; }}
QRadioButton::indicator, QCheckBox::indicator {{ width: 18px; height: 18px; }}
QRadioButton::indicator {{ border-radius: 10px; border: 2px solid {ACCENT.name()}; background: white; }}
QRadioButton::indicator:checked {{ background: qradialgradient(cx:0.5, cy:0.5, radius:0.5, fx:0.5, fy:0.5,
  stop:0 {ACCENT.name()}, stop:0.5 {ACCENT.name()}, stop:0.6 white, stop:1 white); }}
QCheckBox::indicator {{ border-radius: 5px; border: 2px solid {ACCENT.name()}; background: white; }}
QCheckBox::indicator:checked {{ background: {ACCENT.name()}; }}
QScrollArea {{ border: none; background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 4px; }}
QScrollBar::handle:vertical {{ background: {ACCENT_SOFT.name()}; border-radius: 4px; min-height: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
QMenu {{ background: white; border: 2px solid {INK.name()}; border-radius: 10px; padding: 6px; }}
QMenu::item {{ padding: 7px 18px; border-radius: 6px; }}
QMenu::item:selected {{ background: {SURFACE.name()}; color: {FG.name()}; }}
QMenu::separator {{ height: 2px; background: {LINE.name()}; margin: 4px 8px; }}
QToolTip {{ background: white; color: {FG.name()}; border: 2px solid {INK.name()}; border-radius: 6px; padding: 4px; }}
"""
