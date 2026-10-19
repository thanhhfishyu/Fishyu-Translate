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


def data_dir() -> Path:
    root = os.environ.get("APPDATA")
    d = Path(root) / "FishyuTranslate" if root else Path.home() / ".fishyu-translate"
    d.mkdir(parents=True, exist_ok=True)
    return d


def models_dir() -> Path:
    d = data_dir() / "models"
    d.mkdir(parents=True, exist_ok=True)
    return d
