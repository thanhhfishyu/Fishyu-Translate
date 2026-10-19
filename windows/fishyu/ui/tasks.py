import threading

from PySide6.QtCore import QObject, Signal

from .. import crashlog


class _Bridge(QObject):
    done = Signal(object, object, object)

    def __init__(self):
        super().__init__()
        self.done.connect(self._deliver)

    @staticmethod
    def _deliver(cb, value, err):
        try:
            cb(value, err)
        except RuntimeError:
            pass
        except Exception as e:
            crashlog.save(e, "ui-callback")


_bridge = None


def run_async(fn, callback, name="task"):
    global _bridge
    if _bridge is None:
        _bridge = _Bridge()
    bridge = _bridge

    def target():
        try:
            v = fn()
            bridge.done.emit(callback, v, None)
        except Exception as e:
            bridge.done.emit(callback, None, e)

    t = threading.Thread(target=target, name=name, daemon=True)
    t.start()
    return t
