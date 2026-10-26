import os
import sys
from pathlib import Path


def resource_dir() -> Path:
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return Path(base) / "assets"
    return Path(__file__).resolve().parent.parent / "assets"


def resource(name: str) -> Path:
    return resource_dir() / name


def license_file(name: str) -> Path:
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return Path(base) / "licenses" / name
    return Path(__file__).resolve().parents[2] / name


def data_dir() -> Path:
    root = os.environ.get("APPDATA")
    if root:
        d = Path(root) / "FishyuTranslate"
    elif sys.platform.startswith("linux"):
        d = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share") / "fishyu-translate"
    else:
        d = Path.home() / ".fishyu-translate"
    d.mkdir(parents=True, exist_ok=True)
    return d


def models_dir() -> Path:
    d = data_dir() / "models"
    d.mkdir(parents=True, exist_ok=True)
    return d
