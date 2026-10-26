import os
import shutil
import subprocess
import sys
import threading
import time

import pytest

pytestmark = pytest.mark.skipif(not sys.platform.startswith("linux"), reason="Linux only")


@pytest.fixture
def session_bus(monkeypatch, tmp_path):
    if not shutil.which("dbus-daemon"):
        pytest.skip("dbus-daemon not installed")
    proc = subprocess.Popen(["dbus-daemon", "--session", "--nofork", "--print-address=1"],
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    addr = proc.stdout.readline().strip()
    monkeypatch.setenv("DBUS_SESSION_BUS_ADDRESS", addr)
    yield addr
    proc.terminate()
    proc.wait(5)


class FakePortal:
    def __init__(self, tmp_path, shot_size=(1280, 800), deny=False):
        self.tmp = tmp_path
        self.shot_size = shot_size
        self.deny = deny
        self.calls = []
        self.stop = threading.Event()
        self.ready = threading.Event()
        self.session = "/org/freedesktop/portal/desktop/session/1_1/fishyu"
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()
        assert self.ready.wait(5)

    def _req_path(self, msg, token):
        from jeepney import HeaderFields
        sender = msg.header.fields[HeaderFields.sender]
        return f"/org/freedesktop/portal/desktop/request/{sender[1:].replace('.', '_')}/{token}"

    def run(self):
        from jeepney import DBusAddress, HeaderFields, MessageType, message_bus, new_method_return, new_signal
        from jeepney.io.blocking import Proxy, open_dbus_connection
        conn = open_dbus_connection(bus="SESSION")
        Proxy(message_bus, conn).RequestName("org.freedesktop.portal.Desktop")
        self.ready.set()
        while not self.stop.is_set():
            try:
                msg = conn.receive(timeout=0.3)
            except TimeoutError:
                continue
            if msg.header.message_type != MessageType.method_call:
                continue
            member = msg.header.fields.get(HeaderFields.member)
            iface = msg.header.fields.get(HeaderFields.interface)
            self.calls.append((iface, member))

            def respond(path, code, results):
                sig = new_signal(DBusAddress(path, interface="org.freedesktop.portal.Request"), "Response",
                                 "ua{sv}", (code, results))
                conn.send(sig)

            if member == "Screenshot":
                token = msg.body[1]["handle_token"][1]
                path = self._req_path(msg, token)
                conn.send(new_method_return(msg, "o", (path,)))
                if self.deny:
                    respond(path, 1, {})
                    continue
                from PIL import Image, ImageDraw
                im = Image.new("RGB", self.shot_size, (240, 240, 240))
                ImageDraw.Draw(im).rectangle([100, 100, 199, 149], fill=(255, 0, 0))
                f = self.tmp / f"shot_{len(self.calls)}.png"
                im.save(f)
                respond(path, 0, {"uri": ("s", "file://" + str(f).replace(" ", "%20"))})
            elif member == "CreateSession":
                token = msg.body[0]["handle_token"][1]
                path = self._req_path(msg, token)
                conn.send(new_method_return(msg, "o", (path,)))
                respond(path, 0, {"session_handle": ("s", self.session)})
            elif member == "BindShortcuts":
                session, shortcuts, _, opts = msg.body
                self.bound = shortcuts
                path = self._req_path(msg, opts["handle_token"][1])
                conn.send(new_method_return(msg, "o", (path,)))
                respond(path, 0, {"shortcuts": ("a(sa{sv})", shortcuts)})

                def fire():
                    time.sleep(0.5)
                    sig = new_signal(DBusAddress("/org/freedesktop/portal/desktop",
                                                 interface="org.freedesktop.portal.GlobalShortcuts"),
                                     "Activated", "osta{sv}", (self.session, "capture", 1, {}))
                    conn.send(sig)
                threading.Thread(target=fire, daemon=True).start()
        conn.close()

    def close(self):
        self.stop.set()
        self.thread.join(3)


def test_portal_screenshot(session_bus, tmp_path):
    from fishyu import portal
    fake = FakePortal(tmp_path)
    try:
        path = portal.screenshot()
        assert os.path.exists(path) and path.endswith(".png")
        assert ("org.freedesktop.portal.Screenshot", "Screenshot") in fake.calls
    finally:
        fake.close()


def test_portal_denied(session_bus, tmp_path):
    from fishyu import portal
    fake = FakePortal(tmp_path, deny=True)
    try:
        with pytest.raises(portal.PortalError, match="từ chối"):
            portal.screenshot()
    finally:
        fake.close()


def test_portal_missing(session_bus):
    from fishyu import portal
    with pytest.raises(portal.PortalError):
        portal.screenshot()


def test_global_shortcuts(session_bus, tmp_path):
    from fishyu import portal
    fake = FakePortal(tmp_path)
    got = []
    gs = portal.GlobalShortcuts(got.append)
    try:
        gs.start({"capture": ("Khoanh vùng", "Ctrl+Alt+Q"), "live": ("Dịch trực tiếp", "Ctrl+Alt+W")})
        assert gs.ready.wait(10)
        assert gs.error is None
        end = time.time() + 5
        while not got and time.time() < end:
            time.sleep(0.05)
        assert got == ["capture"]
        triggers = {sid: opts["preferred_trigger"][1] for sid, opts in fake.bound}
        assert triggers == {"capture": "CTRL+ALT+q", "live": "CTRL+ALT+w"}
    finally:
        gs.stop()
        fake.close()


def test_portal_backend_crop(session_bus, tmp_path, monkeypatch):
    from PySide6.QtCore import QRect
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from fishyu.ui import capture
    fake = FakePortal(tmp_path, shot_size=(1600, 1200))
    try:
        be = capture.PortalBackend(min_interval=0.0)
        from PySide6.QtGui import QGuiApplication
        scr = QGuiApplication.primaryScreen()
        vg = scr.virtualGeometry()
        img = be.grab_screen(scr)
        assert not img.isNull() and img.width() == 1600 * scr.geometry().width() // vg.width()
        monkeypatch.setattr(capture.QtBackend, "grab_rect", lambda self, s, r: None)
        k = 1600 / vg.width()
        r = QRect(int(100 / k), int(100 / (1200 / vg.height())), int(100 / k), int(50 / (1200 / vg.height())))
        crop = be.grab_rect(scr, r)
        px = crop.pixelColor(crop.width() // 2, crop.height() // 2)
        assert (px.red(), px.green(), px.blue()) == (255, 0, 0)
        left = [p for p in os.listdir(tmp_path) if p.startswith("shot_")]
        assert left == [], "ảnh tạm phải được xoá"
    finally:
        fake.close()


def test_x11_parse_and_portal_trigger():
    from Xlib import X
    from fishyu.hotkeys import parse_x11
    from fishyu.portal import to_portal_trigger
    assert parse_x11("Ctrl+Alt+Q") == (X.ControlMask | X.Mod1Mask, "q")
    assert parse_x11("Ctrl+Shift+F12") == (X.ControlMask | X.ShiftMask, "F12")
    assert parse_x11("Q") is None
    assert to_portal_trigger("Ctrl+Alt+Q") == "CTRL+ALT+q"
    assert to_portal_trigger("Meta+Shift+F5") == "LOGO+SHIFT+F5"


def test_autostart_file(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    from fishyu import linuxapi
    assert linuxapi.set_startup(True)
    f = tmp_path / "autostart" / "fishyu-translate.desktop"
    txt = f.read_text()
    assert "Exec=" in txt and "--tray" in txt
    assert linuxapi.set_startup(False)
    assert not f.exists()


def test_session_detection(monkeypatch):
    from fishyu import sysapi
    monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
    assert sysapi.session_type() == "wayland"
    monkeypatch.delenv("WAYLAND_DISPLAY")
    monkeypatch.setenv("XDG_SESSION_TYPE", "x11")
    monkeypatch.setenv("DISPLAY", ":0")
    assert sysapi.session_type() == "x11"


def test_hotkey_manager_wayland(session_bus, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-test")
    from fishyu.hotkeys import HotkeyManager
    fake = FakePortal(tmp_path)
    hk = HotkeyManager()
    got = []
    hk.triggered.connect(got.append)
    try:
        hk.start({"capture": "Ctrl+Alt+Q", "live": "Ctrl+Alt+W", "clipboard": "Ctrl+Alt+E"},
                 {"capture": "Khoanh vùng"})
        assert hk.backend == "portal" and hk.failed == []
        end = time.time() + 5
        while not got and time.time() < end:
            app.processEvents()
            time.sleep(0.05)
        assert got == ["capture"]
    finally:
        hk.stop()
        fake.close()


def test_hotkey_manager_wayland_without_portal(session_bus, monkeypatch):
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-test")
    from fishyu.hotkeys import HotkeyManager
    hk = HotkeyManager()
    hk.start({"capture": "Ctrl+Alt+Q"})
    try:
        assert hk.backend == "portal" and hk.failed == ["capture"] and hk.note
    finally:
        hk.stop()
