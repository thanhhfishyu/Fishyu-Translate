import os
import threading
from pathlib import Path

_local = threading.local()


def _display():
    d = getattr(_local, "dpy", None)
    if d is None:
        from Xlib import display
        d = display.Display()
        _local.dpy = d
    return d


def _x11():
    return bool(os.environ.get("DISPLAY"))


def set_topmost(widget, on=True):
    if on and widget.isVisible():
        widget.raise_()


def set_noactivate(widget, on=True):
    pass


def set_click_through(widget, on=True):
    pass


def exclude_from_capture(widget) -> bool:
    return False


def foreground():
    if not _x11():
        return 0
    from Xlib import X
    d = _display()
    root = d.screen().root
    atom = d.intern_atom("_NET_ACTIVE_WINDOW")
    prop = root.get_full_property(atom, X.AnyPropertyType)
    return int(prop.value[0]) if prop and len(prop.value) else 0


def restore_foreground(wid):
    if not wid or not _x11():
        return
    from Xlib import X
    from Xlib.protocol import event
    d = _display()
    root = d.screen().root
    atom = d.intern_atom("_NET_ACTIVE_WINDOW")
    win = d.create_resource_object("window", int(wid))
    ev = event.ClientMessage(window=win, client_type=atom, data=(32, [2, X.CurrentTime, 0, 0, 0]))
    root.send_event(ev, event_mask=X.SubstructureRedirectMask | X.SubstructureNotifyMask)
    d.flush()


def has_compositor() -> bool:
    if not _x11():
        return True
    try:
        d = _display()
        atom = d.intern_atom(f"_NET_WM_CM_S{d.get_default_screen()}")
        owner = d.get_selection_owner(atom)
        return int(getattr(owner, "id", owner) or 0) != 0
    except Exception:
        return True


def autostart_file() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "autostart" / "fishyu-translate.desktop"


def set_startup(on: bool) -> bool:
    from .sysapi import launch_command
    f = autostart_file()
    if not on:
        if f.exists():
            f.unlink()
        return True
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(
        "[Desktop Entry]\nType=Application\nName=Fishyu Translate\n"
        f"Exec={launch_command()} --tray\nIcon=fishyu-translate\nX-GNOME-Autostart-enabled=true\nTerminal=false\n",
        encoding="utf-8",
    )
    return True


def window_state(wid: int):
    from Xlib import X
    d = _display()
    w = d.create_resource_object("window", int(wid))
    names = []
    prop = w.get_full_property(d.intern_atom("_NET_WM_STATE"), X.AnyPropertyType)
    if prop:
        names = [d.get_atom_name(a) for a in prop.value]
    hints = w.get_wm_hints()
    accepts_focus = bool(hints.input) if hints and (hints.flags & 1) else True
    return {"state": names, "accepts_focus": accepts_focus}


def input_shape_empty(wid: int) -> bool:
    from Xlib.ext import shape
    d = _display()
    if not d.has_extension("SHAPE"):
        return False
    w = d.create_resource_object("window", int(wid))
    rects = w.shape_get_rectangles(shape.SK.Input).rectangles
    return len(rects) == 0


def toplevel_frame(wid: int) -> int:
    d = _display()
    w = d.create_resource_object("window", int(wid))
    root = d.screen().root.id
    cur = w
    while True:
        t = cur.query_tree()
        if t.parent.id == root or t.parent.id == 0:
            return cur.id
        cur = t.parent
