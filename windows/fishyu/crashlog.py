import datetime
import platform
import sys
import threading
import traceback

from . import VERSION
from .paths import data_dir


def _file():
    return data_dir() / "last_error.txt"


def save(exc: BaseException, where: str) -> None:
    try:
        text = (
            f"Fishyu Translate for Windows {VERSION}\n"
            f"{datetime.datetime.now():%Y-%m-%d %H:%M:%S}\n"
            f"{platform.platform()} - Python {platform.python_version()}\n"
            f"Vị trí: {where}\n\n"
            + "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))[-6000:]
        )
        _file().write_text(text, encoding="utf-8")
    except Exception:
        pass


def read():
    try:
        f = _file()
        return f.read_text(encoding="utf-8") if f.exists() else None
    except Exception:
        return None


def clear():
    try:
        _file().unlink()
    except Exception:
        pass


def install():
    def hook(t, v, tb):
        save(v, "crash")
        sys.__excepthook__(t, v, tb)

    def thook(args):
        save(args.exc_value, f"thread {args.thread.name if args.thread else ''}")

    sys.excepthook = hook
    threading.excepthook = thook


def short_reason(e: BaseException) -> str:
    return (str(e) or type(e).__name__)[:160]
