import os
import select
import sys
import threading

from PySide6.QtCore import QObject, Signal

IS_WIN = sys.platform == "win32"
IS_LINUX = sys.platform.startswith("linux")

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


_X11_NAMES = {
    "SPACE": "space", "TAB": "Tab", "ENTER": "Return", "RETURN": "Return", "ESC": "Escape", "ESCAPE": "Escape",
    "INS": "Insert", "INSERT": "Insert", "DEL": "Delete", "DELETE": "Delete", "HOME": "Home", "END": "End",
    "PGUP": "Prior", "PAGEUP": "Prior", "PGDOWN": "Next", "PAGEDOWN": "Next", "LEFT": "Left", "UP": "Up",
    "RIGHT": "Right", "DOWN": "Down", "`": "grave", "-": "minus", "=": "equal", "[": "bracketleft",
    "]": "bracketright", ";": "semicolon", "'": "apostrophe", ",": "comma", ".": "period", "/": "slash",
    "\\": "backslash",
}


def parse_x11(seq: str):
    if not seq or not seq.strip():
        return None
    from Xlib import X
    mods = 0
    key = None
    for part in [p.strip() for p in seq.replace(" ", "").split("+") if p.strip()]:
        u = part.upper()
        if u in ("CTRL", "CONTROL"):
            mods |= X.ControlMask
        elif u == "ALT":
            mods |= X.Mod1Mask
        elif u == "SHIFT":
            mods |= X.ShiftMask
        elif u in ("WIN", "META", "SUPER"):
            mods |= X.Mod4Mask
        elif len(u) == 1 and ("A" <= u <= "Z" or "0" <= u <= "9"):
            key = u.lower()
        elif u.startswith("F") and u[1:].isdigit() and 1 <= int(u[1:]) <= 24:
            key = u
        elif u in _X11_NAMES:
            key = _X11_NAMES[u]
        else:
            return None
    if key is None or mods == 0:
        return None
    return mods, key


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
        self.backend = "none"
        self.note = ""
        self._ready = threading.Event()
        self._stop = threading.Event()
        self._portal = None

    def start(self, mapping: dict, descriptions: dict = None):
        self.stop()
        self.failed = []
        self.note = ""
        self._ready.clear()
        self._stop.clear()
        if IS_WIN:
            self.backend = "win32"
            self._thread = threading.Thread(target=self._run_win, args=(dict(mapping),), name="hotkeys", daemon=True)
            self._thread.start()
            self._ready.wait(3)
        elif IS_LINUX:
            from . import sysapi
            st = sysapi.session_type()
            if st == "x11":
                self.backend = "x11"
                self._thread = threading.Thread(target=self._run_x11, args=(dict(mapping),), name="hotkeys", daemon=True)
                self._thread.start()
                self._ready.wait(3)
            elif st == "wayland":
                self._start_portal(mapping, descriptions or {})
            else:
                self.backend = "none"
                self.failed = [k for k, v in mapping.items() if v]

    def _start_portal(self, mapping, descriptions):
        from .portal import GlobalShortcuts
        self.backend = "portal"
        self._portal = GlobalShortcuts(lambda sid: self.triggered.emit(sid))
        self._portal.start({k: (descriptions.get(k, k), v) for k, v in mapping.items()})
        self._portal.ready.wait(20)
        if self._portal.error is not None:
            self.note = str(self._portal.error)
            self.failed = [k for k, v in mapping.items() if v]

    def _run_win(self, mapping):
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

    def _run_x11(self, mapping):
        from Xlib import X, XK, display, error
        try:
            d = display.Display()
        except Exception as e:
            self.note = f"không mở được X11 ({e})"
            self.failed = [k for k, v in mapping.items() if v]
            self._ready.set()
            return
        root = d.screen().root
        extra = [0, X.LockMask, X.Mod2Mask, X.LockMask | X.Mod2Mask]
        grabs = {}
        for name, seq in mapping.items():
            p = parse_x11(seq)
            if not p:
                if seq:
                    self.failed.append(name)
                continue
            mods, keyname = p
            keysym = XK.string_to_keysym(keyname)
            code = d.keysym_to_keycode(keysym) if keysym else 0
            if not code:
                self.failed.append(name)
                continue
            catcher = error.CatchError(error.BadAccess)
            for e in extra:
                root.grab_key(code, mods | e, True, X.GrabModeAsync, X.GrabModeAsync, onerror=catcher)
            d.sync()
            if catcher.get_error():
                for e in extra:
                    root.ungrab_key(code, mods | e)
                self.failed.append(name)
            else:
                grabs[(code, mods)] = name
        root.change_attributes(event_mask=X.KeyPressMask)
        d.sync()
        self._ready.set()
        clean = ~(X.LockMask | X.Mod2Mask) & 0xFF
        fd = d.fileno()
        try:
            while not self._stop.is_set():
                if not d.pending_events():
                    r, _, _ = select.select([fd], [], [], 0.3)
                    if not r:
                        continue
                while d.pending_events():
                    ev = d.next_event()
                    if ev.type == X.KeyPress:
                        name = grabs.get((ev.detail, ev.state & clean))
                        if name:
                            self.triggered.emit(name)
        finally:
            try:
                for (code, mods) in grabs:
                    for e in extra:
                        root.ungrab_key(code, mods | e)
                d.close()
            except Exception:
                pass

    def stop(self):
        self._stop.set()
        if self._portal is not None:
            self._portal.stop()
            self._portal = None
        if IS_WIN and self._thread and self._thread.is_alive() and self._tid:
            import ctypes
            ctypes.WinDLL("user32").PostThreadMessageW(self._tid, WM_QUIT, 0, 0)
        if self._thread and self._thread.is_alive():
            self._thread.join(2)
        self._thread = None
        self._tid = 0
