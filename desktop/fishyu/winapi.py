import sys

IS_WIN = sys.platform == "win32"

GWL_EXSTYLE = -20
WS_EX_TOPMOST = 0x00000008
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_LAYERED = 0x00080000
WS_EX_NOACTIVATE = 0x08000000
HWND_TOPMOST = -1
HWND_NOTOPMOST = -2
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOACTIVATE = 0x0010
WDA_NONE = 0x0
WDA_EXCLUDEFROMCAPTURE = 0x11

if IS_WIN:
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
    user32.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.SetWindowLongPtrW.restype = ctypes.c_ssize_t
    user32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
    user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
                                    ctypes.c_int, ctypes.c_int, wintypes.UINT]
    user32.SetWindowDisplayAffinity.argtypes = [wintypes.HWND, wintypes.DWORD]
    user32.GetWindowDisplayAffinity.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.SetForegroundWindow.argtypes = [wintypes.HWND]
    user32.IsWindow.argtypes = [wintypes.HWND]


def hwnd(widget):
    try:
        return int(widget.winId())
    except Exception:
        return 0


def exstyle(widget) -> int:
    if not IS_WIN:
        return 0
    return int(user32.GetWindowLongPtrW(hwnd(widget), GWL_EXSTYLE))


def _set_ex(widget, add=0, remove=0):
    if not IS_WIN:
        return
    h = hwnd(widget)
    cur = user32.GetWindowLongPtrW(h, GWL_EXSTYLE)
    new = (cur | add) & ~remove
    if new != cur:
        user32.SetWindowLongPtrW(h, GWL_EXSTYLE, new)


def set_topmost(widget, on=True):
    if not IS_WIN:
        return
    user32.SetWindowPos(hwnd(widget), HWND_TOPMOST if on else HWND_NOTOPMOST, 0, 0, 0, 0,
                        SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)


def set_noactivate(widget, on=True):
    if on:
        _set_ex(widget, add=WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW)
    else:
        _set_ex(widget, remove=WS_EX_NOACTIVATE)


def set_click_through(widget, on=True):
    if on:
        _set_ex(widget, add=WS_EX_TRANSPARENT | WS_EX_LAYERED)
    else:
        _set_ex(widget, remove=WS_EX_TRANSPARENT)


def exclude_from_capture(widget) -> bool:
    if not IS_WIN:
        return False
    try:
        return bool(user32.SetWindowDisplayAffinity(hwnd(widget), WDA_EXCLUDEFROMCAPTURE))
    except Exception:
        return False


def display_affinity(widget) -> int:
    if not IS_WIN:
        return 0
    v = wintypes.DWORD(0)
    user32.GetWindowDisplayAffinity(hwnd(widget), ctypes.byref(v))
    return int(v.value)


def foreground():
    if not IS_WIN:
        return 0
    return user32.GetForegroundWindow() or 0


def restore_foreground(h):
    if IS_WIN and h and user32.IsWindow(h):
        try:
            user32.SetForegroundWindow(h)
        except Exception:
            pass


RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def set_startup(on: bool) -> bool:
    if not IS_WIN:
        return False
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
            if on:
                exe = sys.executable if getattr(sys, "frozen", False) else f'"{sys.executable}" "{sys.argv[0]}"'
                val = f'"{exe}" --tray' if getattr(sys, "frozen", False) else f"{exe} --tray"
                winreg.SetValueEx(k, "FishyuTranslate", 0, winreg.REG_SZ, val)
            else:
                try:
                    winreg.DeleteValue(k, "FishyuTranslate")
                except FileNotFoundError:
                    pass
        return True
    except Exception:
        return False
