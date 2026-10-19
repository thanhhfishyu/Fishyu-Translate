import sys
import threading

from PySide6.QtCore import QObject, Signal

IS_WIN = sys.platform == "win32"

MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_WIN, MOD_NOREPEAT = 0x1, 0x2, 0x4, 0x8, 0x4000
WM_HOTKEY = 0x0312
WM_QUIT = 0x0012

_NAMED = {
    "SPACE": 0x20, "TAB": 0x09, "ENTER": 0x0D, "RETURN": 0x0D, "ESC": 0x1B, "ESCAPE": 0x1B,
    "INS": 0x2D, "INSERT": 0x2D, "DEL": 0x2E, "DELETE": 0x2E, "HOME": 0x24, "END": 0x23,
    "PGUP": 0x21, "PAGEUP": 0x21, "PGDOWN": 0x22, "PAGEDOWN": 0x22,
    "LEFT": 0x25, "UP": 0x26, "RIGHT": 0x27, "DOWN": 0x28, "`": 0xC0, "-": 0xBD, "=": 0xBB,
    "[": 0xDB, "]": 0xDD, ";": 0xBA, "'": 0xDE, ",": 0xBC, ".": 0xBE, "/": 0xBF, "\\": 0xDC,
}


def parse(seq: str):
    if not seq or not seq.strip():
        return None
    mods = 0
    vk = None
    for part in [p.strip() for p in seq.replace(" ", "").split("+") if p.strip()]:
        u = part.upper()
        if u in ("CTRL", "CONTROL"):
            mods |= MOD_CONTROL
        elif u == "ALT":
            mods |= MOD_ALT
        elif u == "SHIFT":
            mods |= MOD_SHIFT
        elif u in ("WIN", "META", "SUPER"):
            mods |= MOD_WIN
        elif len(u) == 1 and ("A" <= u <= "Z" or "0" <= u <= "9"):
            vk = ord(u)
        elif u.startswith("F") and u[1:].isdigit() and 1 <= int(u[1:]) <= 24:
            vk = 0x70 + int(u[1:]) - 1
        elif u in _NAMED:
            vk = _NAMED[u]
        else:
            return None
    if vk is None or mods == 0:
        return None
    return mods, vk


class HotkeyManager(QObject):
    triggered = Signal(str)

    def __init__(self):
        super().__init__()
        self._thread = None
        self._tid = 0
        self.failed = []
        self._ready = threading.Event()

    def start(self, mapping: dict):
        self.stop()
        self.failed = []
        if not IS_WIN:
            return
        self._ready.clear()
        self._thread = threading.Thread(target=self._run, args=(dict(mapping),), name="hotkeys", daemon=True)
        self._thread.start()
        self._ready.wait(3)

    def _run(self, mapping):
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32")
        self._tid = kernel32.GetCurrentThreadId()
        ids = {}
        for i, (name, seq) in enumerate(mapping.items(), start=1):
            p = parse(seq)
            if not p:
                if seq:
                    self.failed.append(name)
                continue
            if user32.RegisterHotKey(None, i, p[0] | MOD_NOREPEAT, p[1]):
                ids[i] = name
            else:
                self.failed.append(name)
        self._ready.set()
        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            if msg.message == WM_HOTKEY and msg.wParam in ids:
                self.triggered.emit(ids[msg.wParam])
        for i in ids:
            user32.UnregisterHotKey(None, i)

    def stop(self):
        if IS_WIN and self._thread and self._thread.is_alive() and self._tid:
            import ctypes
            ctypes.WinDLL("user32").PostThreadMessageW(self._tid, WM_QUIT, 0, 0)
            self._thread.join(2)
        self._thread = None
        self._tid = 0
