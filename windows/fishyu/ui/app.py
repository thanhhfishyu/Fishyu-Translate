import time

from PySide6.QtCore import QObject, QPoint, QRect, Qt, QTimer
from PySide6.QtGui import QCursor, QGuiApplication
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from .. import config, crashlog, ocr, winapi
from ..hotkeys import HotkeyManager
from . import theme
from .bubble import Bubble
from .common import grab_screen, qimage_to_np
from .live import LiveSession
from .panel import ResultPanel
from .selector import RegionSelector
from .settings import SettingsWindow
from .tasks import run_async

SERVER_NAME = "FishyuTranslateForWindows"


def already_running() -> bool:
    s = QLocalSocket()
    s.connectToServer(SERVER_NAME)
    if s.waitForConnected(400):
        s.write(b"show")
        s.flush()
        s.waitForBytesWritten(400)
        s.disconnectFromServer()
        return True
    return False


class Controller(QObject):
    def __init__(self, app: QApplication, start_hidden=False):
        super().__init__()
        self.app = app
        self.panels = []
        self.selectors = []
        self.live = None
        self.prev_fg = 0
        self._last_copy = (0.0, "")
        self._hidden_notified = False
        self._capturing = False
        self._op = 0

        self.server = QLocalServer(self)
        QLocalServer.removeServer(SERVER_NAME)
        self.server.listen(SERVER_NAME)
        self.server.newConnection.connect(self._on_instance)

        self.bubble = Bubble()
        self.bubble.clicked.connect(lambda: self.start_capture(False))
        self.bubble.menu_requested.connect(self.show_menu)

        self.tray = None
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray = QSystemTrayIcon(theme.app_icon(), self)
            self.tray.setToolTip("Fishyu Translate for Windows")
            self.tray_menu = QMenu()
            self._fill_menu(self.tray_menu)
            self.tray.setContextMenu(self.tray_menu)
            self.tray.activated.connect(self._tray_activated)
            self.tray.show()

        self.settings = SettingsWindow(self)
        self.settings.hotkeys_changed.connect(self.apply_hotkeys)
        self.settings.bubble_toggled.connect(self.set_bubble_visible)
        self.settings.test_translate.connect(lambda t: self.open_panel(t))

        self.hotkeys = HotkeyManager()
        self.hotkeys.triggered.connect(self._on_hotkey)
        self.apply_hotkeys()

        QGuiApplication.clipboard().dataChanged.connect(self._on_clipboard)

        self.set_bubble_visible(config.get().bubble_visible)
        if not start_hidden or not self.tray:
            self.show_settings()
        QTimer.singleShot(1500, lambda: run_async(ocr.warmup, lambda *_: None, "ocr-warmup"))

    def tray_available(self):
        return self.tray is not None

    def notify_hidden_once(self):
        if self.tray and not self._hidden_notified:
            self._hidden_notified = True
            self.tray.showMessage("Fishyu Translate", "App vẫn chạy ở khay hệ thống. Chuột phải vào biểu tượng để mở menu.",
                                  QSystemTrayIcon.Information, 3000)

    def _on_instance(self):
        c = self.server.nextPendingConnection()
        if c:
            c.readyRead.connect(lambda: (c.readAll(), self.show_settings()))

    def _tray_activated(self, reason):
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self.show_settings()

    def show_settings(self):
        self.settings.show()
        self.settings.raise_()
        self.settings.activateWindow()

    def set_bubble_visible(self, v):
        if v:
            self.bubble.restore_position()
            self.bubble.show()
        else:
            self.bubble.hide()

    def _menu_items(self):
        st = config.get()
        live_item = ("Dừng dịch trực tiếp", self.stop_live) if self.live else \
            (f"Dịch trực tiếp (game)    {st.hotkey_live}", lambda: self.start_capture(True))
        return [
            (f"Khoanh vùng để dịch    {st.hotkey_capture}", lambda: self.start_capture(False)),
            live_item,
            (f"Dịch chữ đã copy    {st.hotkey_clipboard}", self.translate_clipboard),
            None,
            ("Ẩn bong bóng" if self.bubble.isVisible() else "Hiện bong bóng", self._toggle_bubble_menu),
            ("Cài đặt", self.show_settings),
            None,
            ("Thoát", self.quit),
        ]

    def _fill_menu(self, m: QMenu):
        m.setStyleSheet(theme.STYLE)
        self._refill(m)
        m.aboutToShow.connect(lambda: self._refill(m))

    def _refill(self, m):
        m.clear()
        for it in self._menu_items():
            if it is None:
                m.addSeparator()
            else:
                m.addAction(it[0], it[1])

    def show_menu(self, pos: QPoint):
        m = QMenu()
        m.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        m.setStyleSheet(theme.STYLE)
        for it in self._menu_items():
            if it is None:
                m.addSeparator()
            else:
                m.addAction(it[0], it[1])
        m.exec(pos)

    def _toggle_bubble_menu(self):
        v = not self.bubble.isVisible()
        config.get().bubble_visible = v
        config.save()
        self.set_bubble_visible(v)

    def apply_hotkeys(self):
        st = config.get()
        self.hotkeys.start({"capture": st.hotkey_capture, "live": st.hotkey_live, "clipboard": st.hotkey_clipboard})
        self.settings.update_hotkey_warning(self.hotkeys.failed)

    def _on_hotkey(self, name):
        if name == "capture":
            self.start_capture(False)
        elif name == "live":
            self.start_capture(True)
        elif name == "clipboard":
            self.translate_clipboard()

    def _on_clipboard(self):
        if not config.get().double_copy:
            return
        text = QGuiApplication.clipboard().text()
        now = time.monotonic()
        last_t, last_text = self._last_copy
        self._last_copy = (now, text)
        if text and text == last_text and now - last_t < 0.7:
            self._last_copy = (0.0, "")
            pos = QCursor.pos()
            self.open_panel(text.strip(), anchor=QRect(pos.x() - 40, pos.y() - 10, 80, 20))

    def translate_clipboard(self):
        text = QGuiApplication.clipboard().text().strip()
        if not text:
            if self.tray:
                self.tray.showMessage("Fishyu Translate", "Bộ nhớ tạm đang trống. Hãy bôi đen chữ và bấm Ctrl+C trước.",
                                      QSystemTrayIcon.Information, 2500)
            return
        self.open_panel(text)

    def close_panels(self):
        for p in list(self.panels):
            try:
                p.close_panel()
            except RuntimeError:
                pass
        self.panels.clear()

    def open_panel(self, text=None, lang=None, context=None, anchor: QRect = None) -> ResultPanel:
        if text is not None:
            self._op += 1
        self.close_panels()
        p = ResultPanel(on_close=lambda pp: self.panels.remove(pp) if pp in self.panels else None)
        self.panels.append(p)
        p.place_near(anchor)
        p.show()
        if text is not None:
            p.start(text, lang, context)
        return p

    def start_capture(self, live_mode: bool):
        if self._capturing or self.selectors:
            return
        self._op += 1
        self._capturing = True
        try:
            self.prev_fg = winapi.foreground()
            self.close_panels()
            if self.live:
                self.live.set_hidden(True)
            QApplication.processEvents()
            saved = self._saved_live_region() if live_mode else None
            hint = "Khoanh vùng khung thoại để dịch liên tục" if live_mode else \
                "Kéo chuột để khoanh vùng  -  bấm vào đoạn chữ để dịch cả đoạn"
            second = ("Vùng lần trước" if saved else "Cả màn hình") if live_mode else "Cả màn hình"
            for scr in QGuiApplication.screens():
                img = grab_screen(scr)
                if img.isNull():
                    continue
                sel = RegionSelector(scr, img, hint, second)
                sel.region.connect(lambda s, r, lm=live_mode: self._on_region(s, r, lm))
                sel.tapped.connect(lambda s, pt, lm=live_mode: self._on_tap(s, pt, lm))
                sel.second.connect(lambda s, lm=live_mode, sv=saved: self._on_second(s, lm, sv))
                sel.cancelled.connect(self.cancel_selection)
                self.selectors.append(sel)
                sel.show()
            if not self.selectors:
                self._end_selection()
            else:
                cur = QGuiApplication.screenAt(QCursor.pos())
                for s in self.selectors:
                    if s.screen_ is cur:
                        s.activateWindow()
                        s.raise_()
        except Exception as e:
            crashlog.save(e, "start_capture")
            self._end_selection()
        finally:
            self._capturing = False

    def cancel_selection(self):
        self._op += 1
        self._end_selection()

    def _end_selection(self, restore_focus=True):
        for s in self.selectors:
            try:
                s.hide()
                s.close()
            except RuntimeError:
                pass
        self.selectors = []
        if self.live:
            self.live.set_hidden(False)
        if restore_focus:
            QTimer.singleShot(50, lambda h=self.prev_fg: winapi.restore_foreground(h))

    @staticmethod
    def _to_global(sel: RegionSelector, local: QRect) -> QRect:
        g = sel.screen_.geometry()
        return local.translated(g.topLeft())

    def _on_region(self, sel, local: QRect, live_mode):
        glob = self._to_global(sel, local)
        crop = sel.crop(local)
        self._end_selection()
        if live_mode:
            self.start_live(glob)
            return
        p = self.open_panel(anchor=glob)
        p.show_loading("Đang nhận diện chữ...")
        arr = qimage_to_np(crop)
        pref = config.get().source_lang
        op = self._op

        def done(res, err):
            if op != self._op or p not in self.panels:
                return
            if err:
                p.show_error(f"Lỗi nhận diện chữ: {err}")
            else:
                p.start(res.text, res.lang)

        run_async(lambda: ocr.recognize(arr, pref), done, "ocr")

    def _on_tap(self, sel: RegionSelector, pt: QPoint, live_mode):
        sel.set_busy("Đang tìm đoạn chữ...")
        arr = qimage_to_np(sel.image)
        k = sel.scale
        pref = config.get().source_lang
        op = self._op

        def done(res, err):
            if op != self._op:
                return
            if err or res is None:
                self._end_selection()
                return
            b = ocr.block_at(res, pt.x() * k, pt.y() * k)
            if b is None:
                sel.set_busy("Không thấy chữ ở chỗ này")
                QTimer.singleShot(900, self._end_selection)
                return
            x0, y0, x1, y1 = b.rect
            local = QRect(int(x0 / k), int(y0 / k), int((x1 - x0) / k), int((y1 - y0) / k))
            glob = self._to_global(sel, local)
            idx = res.blocks.index(b)
            ctx = "\n".join(bb.text for bb in res.blocks[max(0, idx - 1): idx + 2])
            self._end_selection()
            if live_mode:
                self.start_live(glob.adjusted(-24, -16, 24, 16))
            else:
                self.open_panel(b.text, res.lang, ctx, anchor=glob)

        run_async(lambda: ocr.recognize(arr, pref), done, "ocr-tap")

    def _on_second(self, sel, live_mode, saved):
        if live_mode:
            region = saved or sel.screen_.geometry()
            self._end_selection()
            self.start_live(region)
            return
        sel.set_busy("Đang nhận diện cả màn hình...")
        arr = qimage_to_np(sel.image)
        pref = config.get().source_lang
        op = self._op

        def done(res, err):
            if op != self._op:
                return
            self._end_selection()
            if err:
                self.open_panel().show_error(f"Lỗi: {err}")
            else:
                self.open_panel(res.text, res.lang)

        run_async(lambda: ocr.recognize(arr, pref), done, "ocr-full")

    def _saved_live_region(self):
        v = config.get().live_region
        if isinstance(v, list) and len(v) == 5:
            name, x, y, w, h = v
            for scr in QGuiApplication.screens():
                if scr.name() == name and scr.geometry().contains(QRect(x, y, w, h)):
                    return QRect(x, y, w, h)
        return None

    def start_live(self, region: QRect):
        self._op += 1
        self.stop_live()
        self.close_panels()
        scr = QGuiApplication.screenAt(region.center()) or QGuiApplication.primaryScreen()
        region = region.intersected(scr.geometry())
        if region.width() < 20 or region.height() < 12:
            return
        config.get().live_region = [scr.name(), region.x(), region.y(), region.width(), region.height()]
        config.save()
        self.live = LiveSession(region, on_stop=self._live_stopped)
        self.live.start()

    def _live_stopped(self, s):
        if self.live is s:
            self.live = None

    def stop_live(self):
        if self.live:
            self.live.stop()
            self.live = None

    def quit(self):
        try:
            self.settings.save()
        except Exception:
            pass
        self.hotkeys.stop()
        self.stop_live()
        if self.tray:
            self.tray.hide()
        self.app.quit()
