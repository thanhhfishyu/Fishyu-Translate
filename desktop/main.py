import os
import sys


def _prepare_linux():
    if not sys.platform.startswith("linux") or os.environ.get("QT_QPA_PLATFORM"):
        return
    if os.environ.get("WAYLAND_DISPLAY") and os.environ.get("DISPLAY"):
        os.environ["QT_QPA_PLATFORM"] = "xcb"


def _command():
    for c in ("capture", "live", "clipboard", "show", "quit"):
        if f"--{c}" in sys.argv:
            return c
    return None


def main():
    from fishyu import crashlog
    crashlog.install()
    _prepare_linux()
    if "--selftest" in sys.argv:
        from fishyu.selftest import run
        sys.exit(run())

    from PySide6.QtWidgets import QApplication
    from fishyu.ui import theme
    from fishyu.ui.app import Controller, already_running

    app = QApplication(sys.argv)
    app.setApplicationName("Fishyu Translate")
    app.setQuitOnLastWindowClosed(False)
    cmd = _command()
    if already_running(cmd or "show"):
        return 0
    if cmd == "quit":
        return 0
    theme.load_fonts()
    theme.apply_app_font(app)
    app.setWindowIcon(theme.app_icon())
    app.setStyleSheet(theme.STYLE)
    ctl = Controller(app, start_hidden="--tray" in sys.argv or cmd in ("capture", "live", "clipboard"))
    app._controller = ctl
    if cmd and cmd != "show":
        from PySide6.QtCore import QTimer
        QTimer.singleShot(400, lambda: ctl.run_command(cmd))
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
