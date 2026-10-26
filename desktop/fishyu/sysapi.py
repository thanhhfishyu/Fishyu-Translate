import os
import sys

IS_WIN = sys.platform == "win32"
IS_LINUX = sys.platform.startswith("linux")


def session_type() -> str:
    if IS_WIN:
        return "windows"
    if IS_LINUX:
        if os.environ.get("WAYLAND_DISPLAY") or os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland":
            return "wayland"
        if os.environ.get("DISPLAY"):
            return "x11"
        return "none"
    return "other"


def is_wayland() -> bool:
    return session_type() == "wayland"


if IS_WIN:
    from . import winapi as _impl
elif IS_LINUX:
    from . import linuxapi as _impl
else:
    _impl = None


def _call(name, *a, default=None):
    fn = getattr(_impl, name, None) if _impl else None
    if fn is None:
        return default
    try:
        return fn(*a)
    except Exception:
        return default


def set_topmost(w, on=True):
    _call("set_topmost", w, on)


def set_noactivate(w, on=True):
    _call("set_noactivate", w, on)


def set_click_through(w, on=True):
    _call("set_click_through", w, on)


def exclude_from_capture(w) -> bool:
    return bool(_call("exclude_from_capture", w, default=False))


def foreground():
    return _call("foreground", default=0) or 0


def restore_foreground(h):
    _call("restore_foreground", h)


def set_startup(on: bool) -> bool:
    return bool(_call("set_startup", on, default=False))


_mask_cache = [0.0, False]


def needs_shape_mask() -> bool:
    if not IS_LINUX or session_type() != "x11":
        return False
    import time
    now = time.monotonic()
    if now - _mask_cache[0] > 20:
        _mask_cache[0] = now
        _mask_cache[1] = not bool(_call("has_compositor", default=True))
    return _mask_cache[1]


def hide_mode() -> str:
    return "opacity" if IS_WIN else "hide"


def launch_command() -> str:
    if getattr(sys, "frozen", False):
        if os.environ.get("APPIMAGE"):
            return f'"{os.environ["APPIMAGE"]}"'
        if IS_LINUX and sys.executable.startswith("/opt/fishyu-translate/"):
            return "fishyu-translate"
        return f'"{sys.executable}"'
    return f'"{sys.executable}" "{os.path.abspath(sys.argv[0])}"'
