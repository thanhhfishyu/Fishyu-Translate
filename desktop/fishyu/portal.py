import threading
import uuid
from urllib.parse import unquote, urlparse

PORTAL_BUS = "org.freedesktop.portal.Desktop"
PORTAL_PATH = "/org/freedesktop/portal/desktop"


class PortalError(Exception):
    pass


def _connect():
    from jeepney.io.blocking import open_dbus_connection
    try:
        return open_dbus_connection(bus="SESSION")
    except Exception as e:
        raise PortalError(f"không kết nối được D-Bus ({type(e).__name__})")


def _request(conn, interface, method, signature, body_fn, timeout=120):
    from jeepney import DBusAddress, MatchRule, message_bus, new_method_call
    from jeepney.io.blocking import Proxy
    from jeepney.wrappers import DBusErrorResponse, unwrap_msg
    token = "fishyu_" + uuid.uuid4().hex[:10]
    sender = conn.unique_name[1:].replace(".", "_")
    path = f"{PORTAL_PATH}/request/{sender}/{token}"
    rule = MatchRule(type="signal", interface="org.freedesktop.portal.Request", member="Response", path=path)
    Proxy(message_bus, conn).AddMatch(rule)
    addr = DBusAddress(PORTAL_PATH, bus_name=PORTAL_BUS, interface=interface)
    with conn.filter(rule) as queue:
        msg = new_method_call(addr, method, signature, body_fn(token))
        try:
            unwrap_msg(conn.send_and_get_reply(msg, timeout=15))
        except DBusErrorResponse as e:
            raise PortalError(f"hệ thống không hỗ trợ {interface.rsplit('.', 1)[-1]} ({e.name})")
        except TimeoutError:
            raise PortalError("cổng hệ thống không phản hồi")
        try:
            sig = conn.recv_until_filtered(queue, timeout=timeout)
        except TimeoutError:
            raise PortalError("hết thời gian chờ hệ thống")
    code, results = sig.body
    if code != 0:
        raise PortalError("người dùng đã từ chối hoặc huỷ" if code == 1 else f"lỗi hệ thống (mã {code})")
    return results


def screenshot() -> str:
    conn = _connect()
    try:
        results = _request(conn, "org.freedesktop.portal.Screenshot", "Screenshot", "sa{sv}",
                           lambda t: ("", {"handle_token": ("s", t), "interactive": ("b", False)}))
    finally:
        conn.close()
    uri = results.get("uri", ("s", ""))[1]
    p = urlparse(uri)
    if p.scheme != "file" or not p.path:
        raise PortalError("hệ thống không trả về ảnh chụp")
    return unquote(p.path)


def to_portal_trigger(seq: str) -> str:
    out = []
    for part in [x.strip() for x in seq.replace(" ", "").split("+") if x.strip()]:
        u = part.upper()
        if u in ("CTRL", "CONTROL"):
            out.append("CTRL")
        elif u == "ALT":
            out.append("ALT")
        elif u == "SHIFT":
            out.append("SHIFT")
        elif u in ("WIN", "META", "SUPER"):
            out.append("LOGO")
        elif len(part) == 1:
            out.append(part.lower())
        else:
            out.append(part)
    return "+".join(out)


class GlobalShortcuts:
    def __init__(self, on_activated):
        self.on_activated = on_activated
        self._thread = None
        self._stop = threading.Event()
        self.error = None
        self.ready = threading.Event()
        self.bound = []

    def start(self, mapping: dict):
        self.stop()
        self._stop.clear()
        self.ready.clear()
        self.error = None
        self._thread = threading.Thread(target=self._run, args=(dict(mapping),), name="portal-shortcuts", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(3)
        self._thread = None

    def _run(self, mapping):
        from jeepney import MatchRule, message_bus
        from jeepney.io.blocking import Proxy
        try:
            conn = _connect()
        except PortalError as e:
            self.error = e
            self.ready.set()
            return
        try:
            iface = "org.freedesktop.portal.GlobalShortcuts"
            res = _request(conn, iface, "CreateSession", "a{sv}",
                           lambda t: ({"handle_token": ("s", t),
                                       "session_handle_token": ("s", "fishyu_s" + uuid.uuid4().hex[:8])},))
            session = res.get("session_handle", ("o", ""))[1]
            if not session:
                raise PortalError("không tạo được phiên phím tắt")
            shortcuts = [(sid, {"description": ("s", desc), "preferred_trigger": ("s", to_portal_trigger(trig))})
                         for sid, (desc, trig) in mapping.items() if trig]
            res = _request(conn, iface, "BindShortcuts", "oa(sa{sv})sa{sv}",
                           lambda t: (session, shortcuts, "", {"handle_token": ("s", t)}))
            self.bound = [s[0] for s in res.get("shortcuts", ("a(sa{sv})", []))[1]] or [s[0] for s in shortcuts]
            rule = MatchRule(type="signal", interface=iface, member="Activated", path="/org/freedesktop/portal/desktop")
            Proxy(message_bus, conn).AddMatch(rule)
            self.ready.set()
            with conn.filter(rule) as queue:
                while not self._stop.is_set():
                    try:
                        sig = conn.recv_until_filtered(queue, timeout=0.5)
                    except TimeoutError:
                        continue
                    sess, sid = sig.body[0], sig.body[1]
                    if sess == session:
                        self.on_activated(sid)
        except PortalError as e:
            self.error = e
        except Exception as e:
            self.error = PortalError(f"{type(e).__name__}: {e}")
        finally:
            self.ready.set()
            try:
                conn.close()
            except Exception:
                pass
