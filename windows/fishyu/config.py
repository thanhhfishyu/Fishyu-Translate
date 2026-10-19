import json
import threading
from dataclasses import asdict, dataclass, field, fields

from .paths import data_dir

SOURCE_LANGS = {"AUTO": "Tự động", "ZH": "Tiếng Trung", "JA": "Tiếng Nhật"}
ENGINES = {"DEEPL": "DeepL (chuẩn ngữ cảnh)", "OFFLINE": "Offline (miễn phí, kém hơn)"}

DOMAIN_PRESETS = [
    ("Y học", "Medical / clinical text. Use precise standard medical terminology."),
    ("Sinh học", "Biology / life-science text. Use precise scientific terminology."),
    ("Tiểu thuyết", "Chinese web novel / fiction. Natural literary style, keep character names consistent."),
    ("Game", "Video game story dialogue. Natural, casual spoken style; keep character names consistent."),
    ("Kỹ thuật", "Technical documentation. Use precise technical terminology."),
]


@dataclass
class Settings:
    deepl_key: str = ""
    engine: str = "DEEPL"
    live_engine: str = "DEEPL"
    fallback_offline: bool = True
    source_lang: str = "AUTO"
    domain_hint: str = ""
    glossary: str = ""
    live_font: int = 16
    live_show_source: bool = False
    live_click_through: bool = False
    live_region: list = field(default_factory=list)
    panel_pinned: bool = True
    panel_font: int = 15
    bubble_visible: bool = True
    bubble_pos: list = field(default_factory=list)
    hotkey_capture: str = "Ctrl+Alt+Q"
    hotkey_live: str = "Ctrl+Alt+W"
    hotkey_clipboard: str = "Ctrl+Alt+E"
    double_copy: bool = True
    start_with_windows: bool = False
    first_run_done: bool = False

    def glossary_pairs(self):
        out = []
        for line in self.glossary.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            a, b = line.split("=", 1)
            a, b = a.strip(), b.strip()
            if a and b:
                out.append((a, b))
        out.sort(key=lambda p: -len(p[0]))
        return out


_lock = threading.Lock()
_settings = None


def _path():
    return data_dir() / "settings.json"


def get() -> Settings:
    global _settings
    with _lock:
        if _settings is None:
            s = Settings()
            try:
                raw = json.loads(_path().read_text(encoding="utf-8"))
                names = {f.name for f in fields(Settings)}
                for k, v in raw.items():
                    if k in names and isinstance(v, type(getattr(s, k))):
                        setattr(s, k, v)
            except Exception:
                pass
            if s.engine not in ENGINES:
                s.engine = "DEEPL"
            if s.live_engine not in ENGINES:
                s.live_engine = "DEEPL"
            if s.source_lang not in SOURCE_LANGS:
                s.source_lang = "AUTO"
            s.live_font = max(10, min(32, s.live_font))
            _settings = s
        return _settings


def save() -> None:
    s = get()
    with _lock:
        tmp = _path().with_suffix(".tmp")
        tmp.write_text(json.dumps(asdict(s), ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(_path())


def reset_for_tests():
    global _settings
    _settings = None
