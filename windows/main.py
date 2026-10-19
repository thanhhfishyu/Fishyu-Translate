import sys


def main():
    from fishyu import crashlog
    crashlog.install()
    if "--selftest" in sys.argv:
        from fishyu.selftest import run
        sys.exit(run())

    from PySide6.QtWidgets import QApplication
    from fishyu.ui import theme
    from fishyu.ui.app import Controller, already_running

    app = QApplication(sys.argv)
    app.setApplicationName("Fishyu Translate")
    app.setQuitOnLastWindowClosed(False)
    if already_running():
        return 0
    theme.load_fonts()
    theme.apply_app_font(app)
    app.setWindowIcon(theme.app_icon())
    app.setStyleSheet(theme.STYLE)
    ctl = Controller(app, start_hidden="--tray" in sys.argv)
    app._controller = ctl
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
