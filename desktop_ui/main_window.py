import datetime
import os
import sys
import threading

import pytz
from PySide6.QtCore import QSettings, QTimer, QUrl, Signal, Qt
from PySide6.QtGui import QAction, QColor, QDesktopServices, QFontMetrics, QGuiApplication, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QApplication, QCheckBox, QDialog, QDialogButtonBox, QHBoxLayout, QLabel, QMenu, QMessageBox, QPushButton, QSystemTrayIcon, QVBoxLayout, QWidget
from qfluentwidgets import FluentIcon, FluentWindow, InfoBar, InfoBarPosition, NavigationItemPosition, Theme, isDarkTheme, setTheme

from desktop_ui.controller import ChannelOperationController, RtmpMonitorController, ServiceProcessController, UpdateController
from desktop_ui.pages.channels import ChannelCenterPage
from desktop_ui.pages.about import AboutPage
from desktop_ui.pages.dashboard import DashboardPage, next_scheduled_update
from desktop_ui.pages.logs import LogsPage
from desktop_ui.pages.rtmp import RtmpPage
from desktop_ui.pages.settings import SettingsPage
from desktop_ui.pages.sources import SourcesPage
from desktop_ui.pages.tasks import TasksPage
from desktop_ui.models import ChannelLogoLoader
from desktop_ui.widgets import NavigationStatusIndicator, apply_dialog_theme, localize_dialog_buttons
from desktop_ui.platform_integration import set_macos_activation_policy, suspend_macos_window_flush
import utils.constants as constants
from utils.config import config, resource_path
from utils.i18n import get_language, set_language, t
from utils.rtmp_runtime import install_rtmp_runtime
from utils.tools import get_public_url, get_version_info


def _update_notification_icon() -> QPixmap:
    pixmap = QPixmap(40, 40)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#DBEAFE"))
    painter.drawEllipse(1, 1, 38, 38)
    painter.setPen(QPen(
        QColor("#2563EB"),
        3.5,
        Qt.PenStyle.SolidLine,
        Qt.PenCapStyle.RoundCap,
        Qt.PenJoinStyle.RoundJoin,
    ))
    painter.drawLine(20, 29, 20, 11)
    painter.drawLine(12, 19, 20, 11)
    painter.drawLine(28, 19, 20, 11)
    painter.end()
    return pixmap


class MainWindow(FluentWindow):
    MACOS_TITLE_BAR_HEIGHT = 32

    rtmp_install_finished = Signal(dict)
    rtmp_install_output = Signal(str)

    def __init__(self, start_runtime: bool = True):
        super().__init__()
        self._start_runtime = bool(start_runtime)
        info = get_version_info()
        self._version = str(info.get("version") or "--")
        self.setWindowTitle(str(info.get("name") or "IPTV-API"))
        icon_path = "static/images/macos_app_icon.icns" if sys.platform == "darwin" else "favicon.ico"
        self.setWindowIcon(QIcon(resource_path(icon_path)))
        self._window_geometry_timer = QTimer(self)
        self._window_geometry_timer.setSingleShot(True)
        self._window_geometry_timer.setInterval(300)
        self._window_geometry_timer.timeout.connect(self._save_window_geometry)
        self._configure_initial_geometry()
        # [PT-BR] The navigation stack's pop-up animation offsets pages vertically.
        # [PT-BR] Keep page changes stationary so they cannot be mistaken for window resizing.
        self.stackedWidget.setAnimationEnabled(False)
        self.navigationInterface.setIndicatorAnimationEnabled(False)
        self.navigationInterface.setReturnButtonVisible(False)
        if sys.platform == "darwin":
            self.setSystemTitleBarButtonVisible(True)
            self.titleBar.minBtn.hide()
            self.titleBar.maxBtn.hide()
            self.titleBar.closeBtn.hide()
            self.titleBar.setFixedHeight(self.MACOS_TITLE_BAR_HEIGHT)
            self.widgetLayout.setContentsMargins(
                0, self.MACOS_TITLE_BAR_HEIGHT, 0, 0
            )
            margins = self.titleBar.hBoxLayout.contentsMargins()
            self.titleBar.hBoxLayout.setContentsMargins(
                margins.left(),
                margins.top(),
                margins.right(),
                self.MACOS_TITLE_BAR_HEIGHT - 32,
            )
        self.navigationInterface.setExpandWidth(220)
        self.navigationInterface.setMinimumExpandWidth(840)
        self.channel_logo_loader = ChannelLogoLoader(self)
        self.dashboard = DashboardPage(self, self.channel_logo_loader)
        self.channels = ChannelCenterPage(self, self.channel_logo_loader)
        self.rtmp = RtmpPage(self)
        self.sources = SourcesPage(self)
        self.logs = LogsPage(self)
        self.tasks = TasksPage(self)
        self.settings = SettingsPage(self)
        self.about = AboutPage(self)
        self.dashboard_item = self.addSubInterface(self.dashboard, FluentIcon.HOME, t("desktop.dashboard"))
        self.channels_item = self.addSubInterface(self.channels, FluentIcon.LIBRARY, t("desktop.channel_center"))
        self.sources_item = self.addSubInterface(self.sources, FluentIcon.FOLDER, t("desktop.sources"))
        self.rtmp_item = self.addSubInterface(self.rtmp, FluentIcon.IOT, t("desktop.play_streaming"))
        self.logs_item = self.addSubInterface(self.logs, FluentIcon.COMMAND_PROMPT, t("desktop.logs"))
        self.tasks_item = self.addSubInterface(self.tasks, FluentIcon.HISTORY, t("desktop.task_history"))
        self.settings_item = self.addSubInterface(self.settings, FluentIcon.SETTING, t("desktop.settings"), NavigationItemPosition.BOTTOM)
        self.about_item = self.addSubInterface(self.about, FluentIcon.INFO, t("desktop.about"), NavigationItemPosition.BOTTOM)
        self._navigation_items = {
            "dashboard": (self.dashboard_item, "desktop.dashboard", self.dashboard),
            "channels": (self.channels_item, "desktop.channel_center", self.channels),
            "sources": (self.sources_item, "desktop.sources", self.sources),
            "rtmp": (self.rtmp_item, "desktop.play_streaming", self.rtmp),
            "logs": (self.logs_item, "desktop.logs", self.logs),
            "tasks": (self.tasks_item, "desktop.task_history", self.tasks),
            "settings": (self.settings_item, "desktop.settings", self.settings),
            "about": (self.about_item, "desktop.about", self.about),
        }
        self._navigation_statuses = {}
        self._navigation_indicators = {}
        for name, (item, _, _) in self._navigation_items.items():
            indicator = NavigationStatusIndicator(item)
            indicator.move(24, 3)
            self._navigation_indicators[name] = indicator
        self.language_item = self.navigationInterface.addItem(
            "languageToggle",
            FluentIcon.LANGUAGE,
            "",
            self.toggle_language,
            selectable=False,
            position=NavigationItemPosition.BOTTOM,
        )
        self.language_item.setEnabled(not self._language_environment_override())
        self.theme_item = self.navigationInterface.addItem(
            "themeToggle",
            FluentIcon.CONSTRACT,
            "",
            self.toggle_theme,
            selectable=False,
            position=NavigationItemPosition.BOTTOM,
        )
        panel = self.navigationInterface.panel
        navigation_top = self.MACOS_TITLE_BAR_HEIGHT if sys.platform == "darwin" else 48
        panel.vBoxLayout.setContentsMargins(0, navigation_top, 0, 5)
        panel.topLayout.removeWidget(panel.menuButton)
        panel.bottomLayout.addWidget(panel.menuButton, 0, Qt.AlignmentFlag.AlignBottom)
        self._update_language_item()
        self._update_theme_item()
        self._remove_navigation_tooltips()
        self._fit_navigation_width()
        self.controller = UpdateController(self)
        self._update_activity_state = "idle"
        self._update_progress_value = 0
        self._service_status = "unknown"
        self._rtmp_snapshot = {}
        self._tray_refresh_timer = QTimer(self)
        self._tray_refresh_timer.setSingleShot(True)
        self._tray_refresh_timer.setInterval(500)
        self._tray_refresh_timer.timeout.connect(self._refresh_tray_menu)
        self.operation_controller = ChannelOperationController(self)
        self.rtmp_controller = RtmpMonitorController(self)
        self.service_controller = ServiceProcessController(self)
        self.dashboard.run_requested.connect(self._start_update)
        self.dashboard.pause_requested.connect(self._pause_update)
        self.dashboard.resume_requested.connect(self._resume_update)
        self.dashboard.cancel_requested.connect(self._cancel_update)
        self.dashboard.destination_requested.connect(self._navigate_from_dashboard)
        self.settings.settings_saved.connect(self.dashboard.refresh_schedule)
        self.settings.settings_saved.connect(self._refresh_tray_menu)
        self.controller.started.connect(self._update_started)
        self.controller.progress.connect(self.dashboard.set_progress)
        self.controller.progress.connect(self._update_tray_progress)
        self.controller.output.connect(self._on_runtime_output)
        self.controller.finished.connect(self._update_finished)
        self.controller.failed.connect(self._update_failed)
        self.channels.retest_channel_requested.connect(
            lambda row: self.operation_controller.enqueue("retest_channel", {"channel_key": row["channel_key"]})
        )
        self.channels.retest_result_requested.connect(
            lambda row: self.operation_controller.enqueue(
                "retest_result",
                {"channel_key": row["channel_key"], "result_key": row["result_key"]},
            )
        )
        self.channels.retest_results_requested.connect(
            lambda rows: self.operation_controller.enqueue(
                "retest_results",
                {
                    "channel_key": rows[0]["channel_key"],
                    "result_keys": [row["result_key"] for row in rows],
                },
            )
        )
        self.channels.capture_screenshot_requested.connect(
            lambda row: self.operation_controller.enqueue(
                "capture_result_screenshot",
                {"channel_key": row["channel_key"], "result_key": row["result_key"]},
            )
        )
        self.channels.capture_screenshots_requested.connect(
            lambda rows: self.operation_controller.enqueue(
                "capture_result_screenshots",
                {
                    "channel_key": rows[0]["channel_key"],
                    "result_keys": [row["result_key"] for row in rows],
                },
            )
        )
        self.operation_controller.task_started.connect(self.channels.set_task_started)
        self.operation_controller.task_started.connect(self._operation_started)
        self.operation_controller.task_progress.connect(self.channels.set_task_progress)
        self.operation_controller.task_succeeded.connect(self._operation_succeeded)
        self.operation_controller.task_failed.connect(self._operation_failed)
        self.rtmp_controller.snapshot.connect(self.rtmp.set_snapshot)
        self.rtmp_controller.snapshot.connect(self.dashboard.set_stream_snapshot)
        self.rtmp_controller.snapshot.connect(self.channels.set_stream_snapshot)
        self.rtmp_controller.snapshot.connect(self._update_rtmp_navigation_status)
        self.rtmp.stream_control_many_requested.connect(self.rtmp_controller.control_many)
        self.dashboard.stream_control_many_requested.connect(self.rtmp_controller.control_many)
        self.channels.stream_control_many_requested.connect(self.rtmp_controller.control_many)
        self.rtmp.refresh_requested.connect(self.rtmp_controller.refresh)
        self.rtmp.install_requested.connect(self._install_rtmp_from_ui)
        self.rtmp.settings_requested.connect(self._open_rtmp_limit_settings)
        self.channels.playback_workspace_requested.connect(self._open_playback_workspace)
        self.channels.playback_batch_requested.connect(self._open_playback_batch)
        self.channels.stream_monitor_requested.connect(lambda: self.switchTo(self.rtmp))
        self.rtmp_controller.control_finished.connect(self._stream_control_finished)
        self.rtmp_controller.batch_control_finished.connect(self._stream_batch_control_finished)
        self.service_controller.status_changed.connect(self._service_status_changed)
        self.service_controller.output.connect(self._on_runtime_output)
        self.about.status_changed.connect(self._update_about_navigation_status)
        self.about.update_notification_requested.connect(self._show_update_notification)
        self.rtmp_install_finished.connect(self._finish_rtmp_install)
        self.rtmp_install_output.connect(self._append_runtime_log)
        self.stackedWidget.currentChanged.connect(self._navigation_page_changed)
        if self._start_runtime and config.open_service:
            self._start_service()
        else:
            self._service_status_changed("stopped")
        if self._start_runtime:
            self.rtmp_controller.start()
        QApplication.instance().aboutToQuit.connect(self.shutdown)
        self._force_quit = False
        self.tray = None
        if self._start_runtime and QSystemTrayIcon.isSystemTrayAvailable():
            self.tray = QSystemTrayIcon(self.windowIcon(), self)
            self._create_tray_menu()
            self.tray.activated.connect(lambda reason: self.show_and_raise() if reason == QSystemTrayIcon.ActivationReason.Trigger else None)
            self._refresh_tray_menu()
            self.tray.show()
        else:
            QApplication.instance().setQuitOnLastWindowClosed(True)

    def _updateSystemButtonRect(self):
        if sys.platform == "darwin":
            # [PT-BR] AppKit already keeps the native traffic lights stable. Moving
            # [PT-BR] them manually makes page layout events expose two positions.
            return
        updater = getattr(super(), "_updateSystemButtonRect", None)
        if updater is not None:
            return updater()

    def resizeEvent(self, event):
        if sys.platform == "darwin":
            # [PT-BR] FluentWindow first lays the title bar out at x=46. Setting the
            # [PT-BR] final macOS geometry directly avoids exposing that intermediate
            # [PT-BR] frame when a page activation produces a same-size resize event.
            self.titleBar.setGeometry(90, 0, max(0, self.width() - 90), self.titleBar.height())
        else:
            super().resizeEvent(event)
        if self.isVisible():
            self._window_geometry_timer.start()

    def switchTo(self, interface):
"""
[PT-BR]         with suspend_macos_window_flush(self):

[PT-BR]             super().switchTo(interface)

[PT-BR]             if sys.platform == "darwin":

[PT-BR]                 QApplication.sendPostedEvents()



[PT-BR]     def moveEvent(self, event):

[PT-BR]         super().moveEvent(event)

[PT-BR]         if self.isVisible():

[PT-BR]             self._window_geometry_timer.start()



[PT-BR]     def _configure_initial_geometry(self):

[PT-BR]         screen = QApplication.primaryScreen()

[PT-BR]         available = screen.availableGeometry()

[PT-BR]         minimum_width = min(960, available.width())

[PT-BR]         minimum_height = min(640, available.height())

[PT-BR]         self.setMinimumSize(minimum_width, minimum_height)



[PT-BR]         saved_geometry = QSettings().value("appearance/window_geometry")

[PT-BR]         if saved_geometry is not None and self.restoreGeometry(saved_geometry):

[PT-BR]             return



[PT-BR]         width = max(minimum_width, min(1280, round(available.width() * 0.9)))

[PT-BR]         height = max(minimum_height, min(800, round(available.height() * 0.9)))

[PT-BR]         self.resize(width, height)

[PT-BR]         self.move(

[PT-BR]             available.x() + (available.width() - width) // 2,

[PT-BR]             available.y() + (available.height() - height) // 2,

[PT-BR]         )



[PT-BR]     def _save_window_geometry(self):

[PT-BR]         QSettings().setValue("appearance/window_geometry", self.saveGeometry())



[PT-BR]     def toggle_theme(self):

[PT-BR]         self.set_dark_theme(not isDarkTheme())



[PT-BR]     @staticmethod

[PT-BR]     def _language_environment_override():

[PT-BR]         names = ("language", "LANGUAGE", "Settings_language", "SETTINGS_LANGUAGE")

[PT-BR]         return any(os.getenv(name) is not None for name in names)



[PT-BR]     def toggle_language(self):

[PT-BR]         language = "zh_CN" if get_language().startswith("en") else "en"

[PT-BR]         config.set("Settings", "language", language)

[PT-BR]         config.save()

[PT-BR]         set_language(language)

[PT-BR]         self.retranslate()



[PT-BR]     def set_dark_theme(self, dark: bool):

[PT-BR]         setTheme(Theme.DARK if dark else Theme.LIGHT)

[PT-BR]         QSettings().setValue("appearance/theme", "dark" if dark else "light")

[PT-BR]         self._update_theme_item()



[PT-BR]     def _update_theme_item(self):

[PT-BR]         text = t("desktop.light_mode" if isDarkTheme() else "desktop.dark_mode")

[PT-BR]         self.theme_item.setText(text)



[PT-BR]     def _update_language_item(self):

[PT-BR]         text = t("desktop.chinese" if get_language().startswith("en") else "desktop.english")

[PT-BR]         self.language_item.setText(text)



[PT-BR]     def _fit_navigation_width(self):
"""
        items = [item for item, _, _ in self._navigation_items.values()]
        items.extend((self.language_item, self.theme_item))
        longest = max(QFontMetrics(item.font()).horizontalAdvance(item.text()) for item in items)
        width = max(164, longest + 83)  # 44px icon inset, 13px end inset, plus panel padding.
        self.navigationInterface.setExpandWidth(width)
        panel = self.navigationInterface.panel
        if not panel.isCollapsed():
            panel.resize(width, panel.height())
            for item in items:
                if not item.isCompacted:
                    item.setFixedWidth(width - 10)

    def _remove_navigation_tooltips(self):
"""
[PT-BR]         items = [item for item, _, _ in self._navigation_items.values()]

[PT-BR]         items.extend((self.language_item, self.theme_item))

[PT-BR]         for item in items:

[PT-BR]             item.setToolTip("")

[PT-BR]             for child in item.children():

[PT-BR]                 if child.__class__.__name__ == "NavigationToolTipFilter":

[PT-BR]                     item.removeEventFilter(child)

[PT-BR]                     child.deleteLater()



[PT-BR]     def retranslate(self, _language=None):

[PT-BR]         navigation_items = (

[PT-BR]             (self.dashboard_item, "desktop.dashboard"),

[PT-BR]             (self.channels_item, "desktop.channel_center"),

[PT-BR]             (self.sources_item, "desktop.sources"),

[PT-BR]             (self.rtmp_item, "desktop.play_streaming"),

[PT-BR]             (self.logs_item, "desktop.logs"),

[PT-BR]             (self.tasks_item, "desktop.task_history"),

[PT-BR]             (self.settings_item, "desktop.settings"),

[PT-BR]             (self.about_item, "desktop.about"),

[PT-BR]         )

[PT-BR]         for item, key in navigation_items:

[PT-BR]             text = t(key)

[PT-BR]             item.setText(text)

[PT-BR]         for page in (

[PT-BR]             self.dashboard,

[PT-BR]             self.channels,

[PT-BR]             self.sources,

[PT-BR]             self.rtmp,

[PT-BR]             self.logs,

[PT-BR]             self.tasks,

[PT-BR]             self.settings,

[PT-BR]             self.about,

[PT-BR]         ):

[PT-BR]             page.retranslate()

[PT-BR]         if self.tray:

[PT-BR]             self._refresh_tray_menu()

[PT-BR]         self._update_language_item()

[PT-BR]         self._update_theme_item()

[PT-BR]         self._fit_navigation_width()

[PT-BR]         self._refresh_navigation_statuses()



[PT-BR]     def _set_navigation_status(

[PT-BR]             self,

[PT-BR]             name: str,

[PT-BR]             icon,

[PT-BR]             color: str,

[PT-BR]             status_key: str,

[PT-BR]             status_args: dict | None = None,

[PT-BR]             dismiss_on_visit: bool = False,

[PT-BR]             icon_color: str = "#FFFFFF",

[PT-BR]     ):

[PT-BR]         if name not in self._navigation_items:

[PT-BR]             return

[PT-BR]         _, _, page = self._navigation_items[name]

[PT-BR]         if dismiss_on_visit and self.stackedWidget.currentWidget() is page:

[PT-BR]             self._clear_navigation_status(name)

[PT-BR]             return

[PT-BR]         self._navigation_statuses[name] = {

[PT-BR]             "icon": icon,

[PT-BR]             "color": color,

[PT-BR]             "status_key": status_key,

[PT-BR]             "status_args": status_args or {},

[PT-BR]             "dismiss_on_visit": dismiss_on_visit,

[PT-BR]             "icon_color": icon_color,

[PT-BR]         }

[PT-BR]         self._refresh_navigation_status(name)



[PT-BR]     def _clear_navigation_status(self, name: str):

[PT-BR]         self._navigation_statuses.pop(name, None)

[PT-BR]         indicator = self._navigation_indicators.get(name)

[PT-BR]         if indicator:

[PT-BR]             indicator.hide()

[PT-BR]         if name in self._navigation_items:

[PT-BR]             item, _, _ = self._navigation_items[name]

[PT-BR]             item.setToolTip("")



[PT-BR]     def _refresh_navigation_status(self, name: str):

[PT-BR]         status = self._navigation_statuses.get(name)

[PT-BR]         if not status:

[PT-BR]             return

[PT-BR]         item, _, _ = self._navigation_items[name]

[PT-BR]         detail = t(status["status_key"]).format(**status["status_args"])

[PT-BR]         item.setToolTip("")

[PT-BR]         indicator = self._navigation_indicators[name]

[PT-BR]         indicator.setToolTip("")

[PT-BR]         if self.stackedWidget.currentWidget() is self._navigation_items[name][2]:

[PT-BR]             indicator.hide()

[PT-BR]         else:

[PT-BR]             indicator.set_status(

[PT-BR]                 status["icon"], status["color"], status.get("icon_color", "#FFFFFF")

[PT-BR]             )



[PT-BR]     def _refresh_navigation_statuses(self):

[PT-BR]         for name in self._navigation_statuses:

[PT-BR]             self._refresh_navigation_status(name)



[PT-BR]     def _navigation_page_changed(self, _index: int):

[PT-BR]         current = self.stackedWidget.currentWidget()

[PT-BR]         for name, (_, _, page) in self._navigation_items.items():

[PT-BR]             status = self._navigation_statuses.get(name)

[PT-BR]             if page is current and status and status.get("dismiss_on_visit"):

[PT-BR]                 self._clear_navigation_status(name)

[PT-BR]                 if name == "about":

[PT-BR]                     self.about.mark_update_read()

[PT-BR]         self._refresh_navigation_statuses()



[PT-BR]     def show_and_raise(self):

[PT-BR]         if sys.platform == "darwin":

[PT-BR]             set_macos_activation_policy(False)

[PT-BR]         self.show()

[PT-BR]         self.raise_()

[PT-BR]         self.activateWindow()



[PT-BR]     def quit_app(self):

[PT-BR]         if self._has_active_work() and not self._confirm_tray_action(

[PT-BR]             t("desktop.tray_quit_busy_title"),

[PT-BR]             t("desktop.tray_quit_busy_prompt"),

[PT-BR]         ):

[PT-BR]             return

[PT-BR]         self._force_quit = True

[PT-BR]         QApplication.quit()



[PT-BR]     def _create_tray_menu(self):

[PT-BR]         menu = QMenu(self)

[PT-BR]         self.tray_title_action = QAction(self)

[PT-BR]         self.tray_service_status_action = QAction(self)

[PT-BR]         self.tray_update_status_action = QAction(self)

[PT-BR]         self.tray_schedule_action = QAction(self)

[PT-BR]         self.tray_stream_status_action = QAction(self)

[PT-BR]         for action in (

[PT-BR]             self.tray_title_action,

[PT-BR]             self.tray_service_status_action,

[PT-BR]             self.tray_update_status_action,

[PT-BR]             self.tray_schedule_action,

[PT-BR]             self.tray_stream_status_action,

[PT-BR]         ):

[PT-BR]             action.setEnabled(False)

[PT-BR]             menu.addAction(action)

[PT-BR]         menu.addSeparator()



[PT-BR]         self.show_action = QAction(self)

[PT-BR]         self.show_action.triggered.connect(self.show_and_raise)

[PT-BR]         menu.addAction(self.show_action)

[PT-BR]         menu.setDefaultAction(self.show_action)



[PT-BR]         self.tray_task_menu = QMenu(self)

[PT-BR]         self.tray_run_update_action = QAction(self)

[PT-BR]         self.tray_pause_update_action = QAction(self)

[PT-BR]         self.tray_resume_update_action = QAction(self)

[PT-BR]         self.tray_cancel_update_action = QAction(self)

[PT-BR]         self.tray_task_history_action = QAction(self)

[PT-BR]         self.tray_run_update_action.triggered.connect(self._start_update)

[PT-BR]         self.tray_pause_update_action.triggered.connect(self._pause_update)

[PT-BR]         self.tray_resume_update_action.triggered.connect(self._resume_update)

[PT-BR]         self.tray_cancel_update_action.triggered.connect(self._cancel_update_from_tray)

[PT-BR]         self.tray_task_history_action.triggered.connect(lambda: self._open_tray_page(self.tasks))

[PT-BR]         for action in (

[PT-BR]             self.tray_run_update_action,

[PT-BR]             self.tray_pause_update_action,

[PT-BR]             self.tray_resume_update_action,

[PT-BR]             self.tray_cancel_update_action,

[PT-BR]         ):

[PT-BR]             self.tray_task_menu.addAction(action)

[PT-BR]         self.tray_task_menu.addSeparator()

[PT-BR]         self.tray_task_menu.addAction(self.tray_task_history_action)

[PT-BR]         menu.addMenu(self.tray_task_menu)



[PT-BR]         self.tray_result_menu = QMenu(self)

[PT-BR]         self.tray_open_results_action = QAction(self)

[PT-BR]         self.tray_copy_service_url_action = QAction(self)

[PT-BR]         self.tray_open_output_action = QAction(self)

[PT-BR]         self.tray_start_service_action = QAction(self)

[PT-BR]         self.tray_restart_service_action = QAction(self)

[PT-BR]         self.tray_stop_service_action = QAction(self)

[PT-BR]         self.tray_open_results_action.triggered.connect(

[PT-BR]             lambda: QDesktopServices.openUrl(QUrl(self._service_url()))

[PT-BR]         )

[PT-BR]         self.tray_copy_service_url_action.triggered.connect(self._copy_service_url_from_tray)

[PT-BR]         self.tray_open_output_action.triggered.connect(self.dashboard.open_output)

[PT-BR]         self.tray_start_service_action.triggered.connect(self._start_service_from_tray)

[PT-BR]         self.tray_restart_service_action.triggered.connect(self._restart_service_from_tray)

[PT-BR]         self.tray_stop_service_action.triggered.connect(self._stop_service_from_tray)

[PT-BR]         for action in (

[PT-BR]             self.tray_open_results_action,

[PT-BR]             self.tray_copy_service_url_action,

[PT-BR]             self.tray_open_output_action,

[PT-BR]         ):

[PT-BR]             self.tray_result_menu.addAction(action)

[PT-BR]         self.tray_result_menu.addSeparator()

[PT-BR]         for action in (

[PT-BR]             self.tray_start_service_action,

[PT-BR]             self.tray_restart_service_action,

[PT-BR]             self.tray_stop_service_action,

[PT-BR]         ):

[PT-BR]             self.tray_result_menu.addAction(action)

[PT-BR]         menu.addMenu(self.tray_result_menu)



[PT-BR]         menu.addSeparator()

[PT-BR]         self.tray_logs_action = QAction(self)

[PT-BR]         self.tray_settings_action = QAction(self)

[PT-BR]         self.tray_logs_action.triggered.connect(lambda: self._open_tray_page(self.logs))

[PT-BR]         self.tray_settings_action.triggered.connect(lambda: self._open_tray_page(self.settings))

[PT-BR]         menu.addAction(self.tray_logs_action)

[PT-BR]         menu.addAction(self.tray_settings_action)

[PT-BR]         menu.addSeparator()



[PT-BR]         self.quit_action = QAction(self)

[PT-BR]         self.quit_action.triggered.connect(self.quit_app)

[PT-BR]         menu.addAction(self.quit_action)

[PT-BR]         menu.aboutToShow.connect(self._refresh_tray_menu)

[PT-BR]         self.tray.setContextMenu(menu)



[PT-BR]     def _refresh_tray_menu(self):

[PT-BR]         if not getattr(self, "tray", None):

[PT-BR]             return

[PT-BR]         self.tray_title_action.setText(

[PT-BR]             t("desktop.tray_title").format(version=getattr(self, "_version", "--"))

[PT-BR]         )



[PT-BR]         service_label = {

[PT-BR]             "running": t("desktop.running"),

[PT-BR]             "external": t("desktop.external_service"),

[PT-BR]             "stopped": t("desktop.stopped"),

[PT-BR]             "failed": t("desktop.unavailable"),

[PT-BR]         }.get(self._service_status, t("desktop.unknown"))

[PT-BR]         self.tray_service_status_action.setText(t("desktop.tray_service_status").format(

[PT-BR]             status=service_label,

[PT-BR]         ))



[PT-BR]         update_key = {

[PT-BR]             "running": "desktop.tray_update_running",

[PT-BR]             "paused": "desktop.tray_update_paused",

[PT-BR]             "stopping": "desktop.tray_update_stopping",

[PT-BR]             "failed": "desktop.tray_update_failed",

[PT-BR]         }.get(self._update_activity_state, "desktop.tray_update_idle")

[PT-BR]         update_args = {"progress": self._update_progress_value}

[PT-BR]         self.tray_update_status_action.setText(t(update_key).format(**update_args))

[PT-BR]         schedule_text, schedule_detail = self._tray_schedule_text()

[PT-BR]         self.tray_schedule_action.setText(schedule_text)



[PT-BR]         active_streams = max(0, int(self._rtmp_snapshot.get("active_count") or 0))

[PT-BR]         self.tray_stream_status_action.setVisible(active_streams > 0)

[PT-BR]         self.tray_stream_status_action.setText(

[PT-BR]             t("desktop.tray_active_streams").format(count=active_streams)

[PT-BR]         )



[PT-BR]         is_running = self._update_activity_state == "running"

[PT-BR]         is_paused = self._update_activity_state == "paused"

[PT-BR]         is_stopping = self._update_activity_state == "stopping"

[PT-BR]         is_idle = not (is_running or is_paused or is_stopping)

[PT-BR]         self.tray_run_update_action.setVisible(is_idle)

[PT-BR]         self.tray_run_update_action.setEnabled(is_idle and not self.operation_controller.is_busy)

[PT-BR]         self.tray_pause_update_action.setVisible(is_running)

[PT-BR]         self.tray_resume_update_action.setVisible(is_paused)

[PT-BR]         self.tray_cancel_update_action.setVisible(is_running or is_paused or is_stopping)

[PT-BR]         self.tray_cancel_update_action.setEnabled(not is_stopping)



[PT-BR]         service_available = self._service_status in {"running", "external"}

[PT-BR]         service_owned = self.service_controller.owns_process and self._service_status == "running"

[PT-BR]         self.tray_open_results_action.setEnabled(service_available)

[PT-BR]         self.tray_copy_service_url_action.setEnabled(service_available)

[PT-BR]         self.tray_start_service_action.setVisible(not service_available)

[PT-BR]         self.tray_start_service_action.setEnabled(self._service_status != "unknown")

[PT-BR]         self.tray_restart_service_action.setVisible(service_owned)

[PT-BR]         self.tray_stop_service_action.setVisible(service_owned)

[PT-BR]         self.tray_logs_action.setText(

[PT-BR]             t("desktop.tray_view_logs_error")

[PT-BR]             if "logs" in self._navigation_statuses

[PT-BR]             else t("desktop.tray_view_logs")

[PT-BR]         )



[PT-BR]         tooltip_lines = [

[PT-BR]             "IPTV API",

[PT-BR]             t("desktop.tray_tooltip_service").format(status=service_label),

[PT-BR]             self.tray_update_status_action.text(),

[PT-BR]             schedule_detail,

[PT-BR]         ]

[PT-BR]         if active_streams:

[PT-BR]             tooltip_lines.append(t("desktop.tray_active_streams").format(count=active_streams))

[PT-BR]         self.tray.setToolTip("\n".join(tooltip_lines))

[PT-BR]         self._update_tray_icon()

[PT-BR]         self._retranslate_tray_actions()



[PT-BR]     def _update_tray_icon(self):

[PT-BR]         if self._service_status == "failed" or "logs" in self._navigation_statuses:

[PT-BR]             color = "#DC2626"

[PT-BR]         elif (

[PT-BR]             self._update_activity_state in {"running", "paused", "stopping"}

[PT-BR]             or int(self._rtmp_snapshot.get("starting_count") or 0) > 0

[PT-BR]         ):

[PT-BR]             color = "#2563EB"

[PT-BR]         elif self._service_status not in {"running", "external"}:

[PT-BR]             color = "#D97706"

[PT-BR]         else:

[PT-BR]             color = "#059669"

[PT-BR]         pixmap = self.windowIcon().pixmap(32, 32)

[PT-BR]         painter = QPainter(pixmap)

[PT-BR]         painter.setRenderHint(QPainter.RenderHint.Antialiasing)

[PT-BR]         painter.setPen(Qt.PenStyle.NoPen)

[PT-BR]         painter.setBrush(QColor("#FFFFFF"))

[PT-BR]         painter.drawEllipse(20, 20, 12, 12)

[PT-BR]         painter.setBrush(QColor(color))

[PT-BR]         painter.drawEllipse(22, 22, 8, 8)

[PT-BR]         painter.end()

[PT-BR]         self.tray.setIcon(QIcon(pixmap))



[PT-BR]     def _retranslate_tray_actions(self):

[PT-BR]         self.show_action.setText(t("desktop.show_window"))

[PT-BR]         self.tray_task_menu.setTitle(t("desktop.tray_update_tasks"))

[PT-BR]         self.tray_run_update_action.setText(t("desktop.run_once"))

[PT-BR]         self.tray_pause_update_action.setText(t("desktop.pause"))

[PT-BR]         self.tray_resume_update_action.setText(t("desktop.resume"))

[PT-BR]         self.tray_cancel_update_action.setText(t("desktop.tray_cancel_update"))

[PT-BR]         self.tray_task_history_action.setText(t("desktop.task_history"))

[PT-BR]         self.tray_result_menu.setTitle(t("desktop.tray_results_service"))

[PT-BR]         self.tray_open_results_action.setText(t("desktop.tray_open_results"))

[PT-BR]         self.tray_copy_service_url_action.setText(t("desktop.tray_copy_service_url"))

[PT-BR]         self.tray_open_output_action.setText(t("desktop.open_output"))

[PT-BR]         self.tray_start_service_action.setText(t("desktop.tray_start_service"))

[PT-BR]         self.tray_restart_service_action.setText(t("desktop.tray_restart_service"))

[PT-BR]         self.tray_stop_service_action.setText(t("desktop.tray_stop_service"))

[PT-BR]         self.tray_settings_action.setText(t("desktop.settings"))

[PT-BR]         self.quit_action.setText(t("desktop.quit"))



[PT-BR]     def _tray_schedule_text(self):

[PT-BR]         try:

[PT-BR]             next_time = next_scheduled_update()

[PT-BR]             if next_time is None:

[PT-BR]                 value = t("desktop.tray_schedule_disabled")

[PT-BR]                 return value, value

[PT-BR]             timezone = pytz.timezone(config.time_zone)

[PT-BR]             now = datetime.datetime.now(timezone)

[PT-BR]             next_time = next_time.astimezone(timezone)

[PT-BR]             delta_days = (next_time.date() - now.date()).days

[PT-BR]             if delta_days == 0:

[PT-BR]                 key = "desktop.tray_next_update_today"

[PT-BR]                 value = next_time.strftime("%H:%M")

[PT-BR]             elif delta_days == 1:

[PT-BR]                 key = "desktop.tray_next_update_tomorrow"

[PT-BR]                 value = next_time.strftime("%H:%M")

[PT-BR]             else:

[PT-BR]                 key = "desktop.tray_next_update_date"

[PT-BR]                 value = next_time.strftime("%m-%d %H:%M")

[PT-BR]             return (

[PT-BR]                 t(key).format(time=value),

[PT-BR]                 t("desktop.next_update_time").format(time=next_time.strftime("%Y-%m-%d %H:%M:%S")),

[PT-BR]             )

[PT-BR]         except Exception:

[PT-BR]             value = t("desktop.tray_schedule_unavailable")

[PT-BR]             return value, value



[PT-BR]     def _open_tray_page(self, page):

[PT-BR]         self.show_and_raise()

[PT-BR]         self.switchTo(page)



[PT-BR]     def _copy_service_url_from_tray(self):

[PT-BR]         QGuiApplication.clipboard().setText(self._service_url())

[PT-BR]         self.tray.showMessage(

[PT-BR]             t("desktop.tray_copy_service_url"),

[PT-BR]             t("desktop.tray_service_url_copied"),

[PT-BR]             QSystemTrayIcon.MessageIcon.Information,

[PT-BR]             2500,

[PT-BR]         )



[PT-BR]     def _service_port(self) -> int:

[PT-BR]         use_rtmp_proxy = (

[PT-BR]             self._service_status in {"running", "external"}

[PT-BR]             and bool(self._rtmp_snapshot.get("available"))

[PT-BR]         )

[PT-BR]         return config.service_port if use_rtmp_proxy else config.app_port



[PT-BR]     def _service_url(self) -> str:

[PT-BR]         if config.public_url and self._service_status in {"running", "external"}:

[PT-BR]             return get_public_url()

[PT-BR]         return get_public_url(self._service_port())



[PT-BR]     def _start_service_from_tray(self):

[PT-BR]         if self.service_controller.process is not None:

[PT-BR]             self.service_controller.stop()

[PT-BR]         self._start_service()



[PT-BR]     def _update_tray_progress(self, _title, progress, _finished=False, _metadata=None, _now=None):

[PT-BR]         self._update_progress_value = max(0, min(100, int(progress)))

[PT-BR]         if not self._tray_refresh_timer.isActive():

[PT-BR]             self._tray_refresh_timer.start()



[PT-BR]     def _cancel_update_from_tray(self):

[PT-BR]         if self._confirm_tray_action(

[PT-BR]             t("desktop.tray_cancel_update"),

[PT-BR]             t("desktop.tray_cancel_update_prompt"),

[PT-BR]         ):

[PT-BR]             self._cancel_update()



[PT-BR]     def _stop_service_from_tray(self):

[PT-BR]         if not self._confirm_tray_action(

[PT-BR]             t("desktop.tray_stop_service"),

[PT-BR]             t("desktop.tray_stop_service_prompt"),

[PT-BR]         ):

[PT-BR]             return

[PT-BR]         self.service_controller.stop()

[PT-BR]         self._service_status_changed("stopped")



[PT-BR]     def _restart_service_from_tray(self):

[PT-BR]         active_streams = max(0, int(self._rtmp_snapshot.get("active_count") or 0))

[PT-BR]         message = (

[PT-BR]             t("desktop.tray_restart_service_prompt").format(count=active_streams)

[PT-BR]             if active_streams

[PT-BR]             else t("desktop.tray_restart_service_prompt_idle")

[PT-BR]         )

[PT-BR]         if not self._confirm_tray_action(

[PT-BR]             t("desktop.tray_restart_service"),

[PT-BR]             message,

[PT-BR]         ):

[PT-BR]             return

[PT-BR]         self.service_controller.stop()

[PT-BR]         self._service_status_changed("stopped")

[PT-BR]         self._start_service()



[PT-BR]     def _confirm_tray_action(self, title: str, message: str):

[PT-BR]         result = QMessageBox.question(

[PT-BR]             self,

[PT-BR]             title,

[PT-BR]             message,

[PT-BR]             QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,

[PT-BR]             QMessageBox.StandardButton.No,

[PT-BR]         )

[PT-BR]         return result == QMessageBox.StandardButton.Yes



[PT-BR]     def _has_active_work(self):

[PT-BR]         return (

[PT-BR]             self._update_activity_state in {"running", "paused", "stopping"}

[PT-BR]             or self.operation_controller.is_busy

[PT-BR]             or int(self._rtmp_snapshot.get("active_count") or 0) > 0

[PT-BR]             or int(self._rtmp_snapshot.get("starting_count") or 0) > 0

[PT-BR]         )



[PT-BR]     def _navigate_from_dashboard(self, destination: str):

[PT-BR]         page = {

[PT-BR]             "channels": self.channels,

[PT-BR]             "rtmp": self.rtmp,

[PT-BR]             "sources": self.sources,

[PT-BR]             "tasks": self.tasks,

[PT-BR]         }.get(destination)

[PT-BR]         if page:

[PT-BR]             self.switchTo(page)



[PT-BR]     def _open_playback_workspace(self, row: dict):

[PT-BR]         self.rtmp.select_result(row)

[PT-BR]         self.switchTo(self.rtmp)



[PT-BR]     def _open_playback_batch(self, rows: list[dict]):

[PT-BR]         channel_keys = [row["channel_key"] for row in rows if row.get("channel_key")]

[PT-BR]         selected_count = self.rtmp.select_channels(channel_keys)

[PT-BR]         expected_count = len(channel_keys)

[PT-BR]         if selected_count < expected_count:

[PT-BR]             InfoBar.warning(

[PT-BR]                 t("desktop.start_selected_streams"),

[PT-BR]                 t("desktop.channels_without_output").format(count=expected_count - selected_count),

[PT-BR]                 parent=self,

[PT-BR]                 position=InfoBarPosition.TOP,

[PT-BR]             )

[PT-BR]         self.switchTo(self.rtmp)



[PT-BR]     def _open_rtmp_limit_settings(self):

[PT-BR]         self.switchTo(self.settings)

[PT-BR]         self.settings.focus_setting("rtmp_max_streams")

[PT-BR]         InfoBar.info(

[PT-BR]             t("desktop.adjust_concurrency_limit"),

[PT-BR]             t("desktop.concurrency_limit_restart_notice"),

[PT-BR]             parent=self,

[PT-BR]             position=InfoBarPosition.TOP,

[PT-BR]             duration=8000,

[PT-BR]         )



[PT-BR]     def _update_finished(self):

[PT-BR]         outcome = self.dashboard.last_update_outcome or {}

[PT-BR]         if self._update_activity_state == "failed":

[PT-BR]             self._set_update_navigation_status("failed")

[PT-BR]         elif self._update_activity_state == "stopping":

[PT-BR]             self._set_update_navigation_status("cancelled")

[PT-BR]         elif outcome.get("status") == "empty":

[PT-BR]             self._set_update_navigation_status("warning")

[PT-BR]             detail = " ".join(

[PT-BR]                 part for part in (

[PT-BR]                     str(outcome.get("message") or "").strip(),

[PT-BR]                     t("desktop.update_needs_sources_detail"),

[PT-BR]                 )

[PT-BR]                 if part

[PT-BR]             )

[PT-BR]             InfoBar.warning(

[PT-BR]                 t("desktop.update_needs_sources"),

[PT-BR]                 detail,

[PT-BR]                 parent=self,

[PT-BR]                 position=InfoBarPosition.TOP,

[PT-BR]                 duration=10000,

[PT-BR]             )

[PT-BR]         else:

[PT-BR]             self._set_update_navigation_status("completed")

[PT-BR]         self.dashboard.set_running(False)

[PT-BR]         self.dashboard.refresh_metrics()

[PT-BR]         self.channels.reload()

[PT-BR]         self.rtmp.reload_channels()

[PT-BR]         self.operation_controller.resume()



[PT-BR]     def _start_service(self):

[PT-BR]         if config.open_rtmp and not config.rtmp_available:

[PT-BR]             if self._install_rtmp_from_ui(start_service=True):

[PT-BR]                 return

[PT-BR]             InfoBar.warning(

[PT-BR]                 t("name.error"),

[PT-BR]                 t("msg.rtmp_unavailable_fallback"),

[PT-BR]                 parent=self,

[PT-BR]                 position=InfoBarPosition.TOP,

[PT-BR]                 duration=-1,

[PT-BR]             )

[PT-BR]         self.service_controller.start()

[PT-BR]         self._refresh_tray_menu()



[PT-BR]     def _install_rtmp_from_ui(self, start_service=False):

[PT-BR]         dialog = QDialog(self)

[PT-BR]         apply_dialog_theme(dialog)

[PT-BR]         dialog.setWindowTitle(t("name.error"))

[PT-BR]         dialog.setWindowIcon(self.windowIcon())

[PT-BR]         layout = QVBoxLayout(dialog)

[PT-BR]         logo = QLabel(dialog)

[PT-BR]         logo.setPixmap(self.windowIcon().pixmap(64, 64))

[PT-BR]         logo.setAlignment(Qt.AlignmentFlag.AlignHCenter)

[PT-BR]         message = QLabel(t("msg.rtmp_install_confirm"), dialog)

[PT-BR]         message.setWordWrap(True)

[PT-BR]         message.setAlignment(Qt.AlignmentFlag.AlignHCenter)

[PT-BR]         buttons = QDialogButtonBox(

[PT-BR]             QDialogButtonBox.StandardButton.Yes | QDialogButtonBox.StandardButton.No,

[PT-BR]             parent=dialog,

[PT-BR]         )

[PT-BR]         localize_dialog_buttons(buttons)

[PT-BR]         buttons.accepted.connect(dialog.accept)

[PT-BR]         buttons.rejected.connect(dialog.reject)

[PT-BR]         layout.addWidget(logo)

[PT-BR]         layout.addWidget(message)

[PT-BR]         layout.addWidget(buttons)

[PT-BR]         if dialog.exec() != QDialog.DialogCode.Accepted:

[PT-BR]             return False

[PT-BR]         self._start_service_after_rtmp_install = start_service

[PT-BR]         self.rtmp.set_installing(True)

[PT-BR]         self._append_runtime_log(f"{t('msg.rtmp_installing')}\n")

[PT-BR]         threading.Thread(

[PT-BR]             target=lambda: self.rtmp_install_finished.emit(

[PT-BR]                 install_rtmp_runtime(self.rtmp_install_output.emit)

[PT-BR]             ),

[PT-BR]             daemon=True,

[PT-BR]         ).start()

[PT-BR]         return True



[PT-BR]     def _finish_rtmp_install(self, result: dict):

[PT-BR]         self.rtmp.set_installing(False)

[PT-BR]         if result.get("available"):

[PT-BR]             self._append_runtime_log(f"{t('msg.rtmp_install_success')}\n")

[PT-BR]             InfoBar.success(

[PT-BR]                 t("desktop.rtmp_service"),

[PT-BR]                 t("msg.rtmp_install_success"),

[PT-BR]                 parent=self,

[PT-BR]                 position=InfoBarPosition.TOP,

[PT-BR]             )

[PT-BR]         else:

[PT-BR]             self._mark_logs_error()

[PT-BR]             info = result.get("output") or t(

[PT-BR]                 f"msg.rtmp_{result.get('error_code')}", result.get("error_code")

[PT-BR]             ) or t("desktop.unknown")

[PT-BR]             self._append_runtime_log(f"{t('msg.rtmp_install_failed').format(info=info[-1000:])}\n")

[PT-BR]             InfoBar.error(

[PT-BR]                 t("name.error"),

[PT-BR]                 t("msg.rtmp_install_failed").format(info=info[-1000:]),

[PT-BR]                 parent=self,

[PT-BR]                 position=InfoBarPosition.TOP,

[PT-BR]                 duration=-1,

[PT-BR]             )

[PT-BR]         self.rtmp_controller.refresh()

[PT-BR]         if getattr(self, "_start_service_after_rtmp_install", False):

[PT-BR]             self._start_service_after_rtmp_install = False

[PT-BR]             self.service_controller.start()

[PT-BR]         elif result.get("available") and self.service_controller.owns_process:

[PT-BR]             self.service_controller.stop()

[PT-BR]             self.service_controller.start()



[PT-BR]     def _append_runtime_log(self, content: str):

[PT-BR]         self._on_runtime_output(content)

[PT-BR]         os.makedirs(os.path.dirname(constants.log_path), exist_ok=True)

[PT-BR]         with open(constants.log_path, "a", encoding="utf-8") as file:

[PT-BR]             file.write(content)



[PT-BR]     def _on_runtime_output(self, content: str):

[PT-BR]         self.logs.append_runtime(content)



[PT-BR]     def _mark_logs_error(self):

[PT-BR]         self._set_navigation_status(

[PT-BR]             "logs",

[PT-BR]             FluentIcon.CANCEL,

[PT-BR]             "#DC2626",

[PT-BR]             "desktop.nav_runtime_error",

[PT-BR]             dismiss_on_visit=True,

[PT-BR]         )



[PT-BR]     def _service_status_changed(self, status: str):

[PT-BR]         self._service_status = status

[PT-BR]         self.dashboard.set_service_status(status)

[PT-BR]         if status == "failed":

[PT-BR]             self._mark_logs_error()

[PT-BR]         self._refresh_tray_menu()



[PT-BR]     def _update_rtmp_navigation_status(self, snapshot: dict):

[PT-BR]         self._rtmp_snapshot = snapshot if isinstance(snapshot, dict) else {}

[PT-BR]         active_count = max(0, int(snapshot.get("active_count") or 0))

[PT-BR]         starting_count = max(0, int(snapshot.get("starting_count") or 0))

[PT-BR]         if active_count:

[PT-BR]             self._set_navigation_status(

[PT-BR]                 "rtmp",

[PT-BR]                 FluentIcon.PLAY,

[PT-BR]                 "#059669",

[PT-BR]                 "desktop.nav_streaming",

[PT-BR]                 {"count": active_count},

[PT-BR]             )

[PT-BR]         elif starting_count:

[PT-BR]             self._set_navigation_status(

[PT-BR]                 "rtmp",

[PT-BR]                 FluentIcon.SYNC,

[PT-BR]                 "#2563EB",

[PT-BR]                 "desktop.nav_stream_starting",

[PT-BR]                 {"count": starting_count},

[PT-BR]             )

[PT-BR]         else:

[PT-BR]             self._clear_navigation_status("rtmp")

[PT-BR]         self._refresh_tray_menu()



[PT-BR]     def _update_about_navigation_status(self, state: str, payload):

[PT-BR]         payload = payload if isinstance(payload, dict) else {}

[PT-BR]         if state == "checking":

[PT-BR]             self._set_navigation_status(

[PT-BR]                 "about", FluentIcon.SYNC, "#2563EB", "desktop.nav_checking_version",

[PT-BR]             )

[PT-BR]         elif state == "available":

[PT-BR]             if payload.get("unread"):

[PT-BR]                 self._set_navigation_status(

[PT-BR]                     "about",

[PT-BR]                     FluentIcon.DOWNLOAD,

[PT-BR]                     "#059669",

[PT-BR]                     "desktop.nav_version_available",

[PT-BR]                     {"version": payload.get("version", "")},

[PT-BR]                     dismiss_on_visit=True,

[PT-BR]                     icon_color="#D1FAE5",

[PT-BR]                 )

[PT-BR]             else:

[PT-BR]                 self._clear_navigation_status("about")

[PT-BR]         elif state == "downloading":

[PT-BR]             self._set_navigation_status(

[PT-BR]                 "about", FluentIcon.DOWNLOAD, "#2563EB", "desktop.nav_downloading_update",

[PT-BR]             )

[PT-BR]         elif state == "downloaded":

[PT-BR]             self._set_navigation_status(

[PT-BR]                 "about",

[PT-BR]                 FluentIcon.COMPLETED,

[PT-BR]                 "#059669",

[PT-BR]                 "desktop.nav_update_downloaded",

[PT-BR]                 dismiss_on_visit=True,

[PT-BR]             )

[PT-BR]         elif state == "failed":

[PT-BR]             self._set_navigation_status(

[PT-BR]                 "about",

[PT-BR]                 FluentIcon.CANCEL,

[PT-BR]                 "#DC2626",

[PT-BR]                 "desktop.nav_version_check_failed",

[PT-BR]                 dismiss_on_visit=True,

[PT-BR]             )

[PT-BR]         else:

[PT-BR]             self._clear_navigation_status("about")



[PT-BR]     def _show_update_notification(self, payload: dict):

[PT-BR]         if self.stackedWidget.currentWidget() is self.about:

[PT-BR]             self.about.mark_update_read()

[PT-BR]             return

[PT-BR]         version = str(payload.get("version") or "")

[PT-BR]         dialog = QDialog(self)

[PT-BR]         dialog.setWindowTitle(t("desktop.update_available_dialog_title"))

[PT-BR]         dialog.setMinimumWidth(360)

[PT-BR]         apply_dialog_theme(dialog)

[PT-BR]         layout = QVBoxLayout(dialog)

[PT-BR]         layout.setContentsMargins(22, 20, 22, 18)

[PT-BR]         layout.setSpacing(18)

[PT-BR]         message_layout = QHBoxLayout()

[PT-BR]         message_layout.setSpacing(14)

[PT-BR]         icon = QLabel(dialog)

[PT-BR]         icon.setPixmap(_update_notification_icon())

[PT-BR]         icon.setFixedSize(40, 40)

[PT-BR]         message = QLabel(t("desktop.update_available_dialog_body").format(version=version), dialog)

[PT-BR]         message.setWordWrap(True)

[PT-BR]         message.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

[PT-BR]         message.setStyleSheet("font-weight: 600;")

[PT-BR]         message_layout.addWidget(icon, 0, Qt.AlignmentFlag.AlignVCenter)

[PT-BR]         message_layout.addWidget(message, 1, Qt.AlignmentFlag.AlignVCenter)

[PT-BR]         actions = QHBoxLayout()

[PT-BR]         actions.addStretch(1)

[PT-BR]         ignore_button = QPushButton(t("desktop.ignore_update"), dialog)

[PT-BR]         upgrade_button = QPushButton(t("desktop.upgrade_now"), dialog)

[PT-BR]         ignore_button.setObjectName("updateIgnoreButton")

[PT-BR]         upgrade_button.setObjectName("updateUpgradeButton")

[PT-BR]         upgrade_button.setDefault(True)

[PT-BR]         secondary_background = "#373737" if isDarkTheme() else "#E5E7EB"

[PT-BR]         secondary_hover = "#4A4A4A" if isDarkTheme() else "#D1D5DB"

[PT-BR]         secondary_foreground = "#F3F4F6" if isDarkTheme() else "#1F2937"
"""
            QPushButton {{
                background-color: {secondary_background};
                border: 1px solid transparent;
                border-radius: 5px;
                color: {secondary_foreground};
                font-weight: 600;
            }}
            QPushButton:hover {{ background-color: {secondary_hover}; }}
        """)
        upgrade_button.setStyleSheet("""
            QPushButton {
                background-color: #2563EB;
                border: 1px solid #1D4ED8;
                border-radius: 5px;
                color: #FFFFFF;
                font-weight: 600;
            }
            QPushButton:hover { background-color: #1D4ED8; }
            QPushButton:pressed { background-color: #1E40AF; }
        """)
        ignore_button.setFixedSize(112, 24)
        upgrade_button.setFixedSize(112, 24)
        actions.addWidget(ignore_button)
        actions.addWidget(upgrade_button)
        layout.addLayout(message_layout)
        layout.addLayout(actions)
        choice = {"action": None}
        ignore_button.clicked.connect(lambda: (choice.update(action="ignore"), dialog.accept()))
        upgrade_button.clicked.connect(lambda: (choice.update(action="upgrade"), dialog.accept()))
        dialog.exec()
        if choice["action"] == "upgrade":
            self.about.mark_update_read()
            self.switchTo(self.about)
            if self.about.asset_url:
                self.about._download()
            else:
                QDesktopServices.openUrl(QUrl(self.about.release_url))
        elif choice["action"] == "ignore":
            self.about.ignore_available_update()
        else:
            self._update_about_navigation_status(
                "available", {"version": version, "unread": True}
            )

    def _start_update(self):
        if self.operation_controller.is_busy:
            InfoBar.warning(t("desktop.task_running"), t("desktop.wait_for_task"), parent=self, position=InfoBarPosition.TOP)
            return
        self.controller.start()

    def _update_started(self):
        self._update_progress_value = 0
        self._set_update_navigation_status("running")
        self.operation_controller.suspend()
        self.dashboard.set_running(True)

    def _update_failed(self, message: str):
        self._set_update_navigation_status("failed")
        self._mark_logs_error()
        InfoBar.error(t("desktop.update_failed"), message.splitlines()[-1] if message else t("name.error"), parent=self, position=InfoBarPosition.TOP, duration=8000)

    def _pause_update(self):
        self.controller.pause()
        self._set_update_navigation_status("paused")

    def _resume_update(self):
        self.controller.resume()
        self._set_update_navigation_status("running")

    def _cancel_update(self):
        self.controller.cancel()
        self._set_update_navigation_status("stopping")

    def _set_update_navigation_status(self, state: str):
        self._update_activity_state = state
        icon, color, key, dismiss = {
            "running": (FluentIcon.SYNC, "#2563EB", "desktop.nav_update_running", False),
            "paused": (FluentIcon.PAUSE, "#D97706", "desktop.nav_update_paused", False),
            "stopping": (FluentIcon.CLOSE, "#DC2626", "desktop.nav_update_stopping", False),
            "completed": (FluentIcon.COMPLETED, "#059669", "desktop.nav_update_completed", True),
            "warning": (FluentIcon.INFO, "#D97706", "desktop.nav_update_needs_sources", True),
            "cancelled": (FluentIcon.CANCEL, "#64748B", "desktop.nav_update_cancelled", True),
            "failed": (FluentIcon.CANCEL, "#DC2626", "desktop.nav_update_failed", True),
        }[state]
        self._set_navigation_status("dashboard", icon, color, key, dismiss_on_visit=dismiss)
        self._clear_navigation_status("tasks")
        self._refresh_tray_menu()

    def _operation_started(self, operation: str):
        self._set_navigation_status(
            "channels",
            FluentIcon.SYNC,
            "#7C3AED",
            "desktop.nav_channel_task_running",
            {"operation": t(f"desktop.{operation}", operation)},
        )
        self._clear_navigation_status("tasks")

    def _operation_succeeded(self, operation: str, result):
        args = {"operation": t(f"desktop.{operation}", operation)}
        self._set_navigation_status(
            "channels", FluentIcon.COMPLETED, "#059669",
            "desktop.nav_channel_task_completed", args, dismiss_on_visit=True,
        )
        self.channels.set_task_finished()
        self.dashboard.refresh_metrics()
        if operation == "capture_result_screenshot" and isinstance(result, dict):
            QTimer.singleShot(
                0,
                lambda: self.channels.show_result_screenshot(
                    result.get("result_key", ""),
                    notify=True,
                ),
            )
        elif (
            operation == "capture_result_screenshots"
            and isinstance(result, dict)
            and result.get("failed")
        ):
            InfoBar.warning(
                t("desktop.task_completed"),
                t("desktop.screenshot_batch_result").format(
                    success=result.get("success", 0),
                    failed=result.get("failed", 0),
                ),
                parent=self,
                position=InfoBarPosition.TOP,
            )
        else:
            InfoBar.success(t("desktop.task_completed"), t(f"desktop.{operation}", operation), parent=self, position=InfoBarPosition.TOP)

    def _operation_failed(self, operation: str, message: str):
        operation_label = t(f"desktop.{operation}", operation)
        failure_detail = message.strip() if message else operation
        self._append_runtime_log(
            f"{t('desktop.task_failed')}: {operation_label}\n"
            f"{failure_detail}\n"
        )
        self._mark_logs_error()
        args = {"operation": operation_label}
        self._set_navigation_status(
            "channels", FluentIcon.CANCEL, "#DC2626",
            "desktop.nav_channel_task_failed", args, dismiss_on_visit=True,
        )
        self.channels.set_task_finished()
        if operation == "capture_result_screenshot":
            QTimer.singleShot(
                0,
                lambda: self.channels.set_screenshot_capture_failed(
                    message,
                    notify=True,
                ),
            )
        else:
            InfoBar.error(t("desktop.task_failed"), message.splitlines()[-1] if message else operation, parent=self, position=InfoBarPosition.TOP, duration=8000)

    def _stream_control_finished(self, action: str, success: bool, message: str):
        if success:
            InfoBar.success(t("desktop.stream_action_sent"), t(f"desktop.{action}_stream", action), parent=self, position=InfoBarPosition.TOP)
        else:
            self._mark_logs_error()
            InfoBar.error(t("desktop.stream_action_failed"), message or action, parent=self, position=InfoBarPosition.TOP)

    def _stream_batch_control_finished(self, action: str, success: int, total: int, message: str):
        if success == total:
            InfoBar.success(
                t("desktop.stream_action_sent"),
                t("desktop.batch_stream_action_success").format(count=success),
                parent=self,
                position=InfoBarPosition.TOP,
            )
        else:
            self._mark_logs_error()
            InfoBar.error(
                t("desktop.stream_action_failed"),
                t("desktop.batch_stream_action_partial").format(success=success, total=total, info=message),
                parent=self,
                position=InfoBarPosition.TOP,
                duration=8000,
            )

    def shutdown(self):
        self._save_window_geometry()
        self.rtmp_controller.shutdown()
        self.service_controller.stop()
        self.operation_controller.shutdown()
        self.controller.shutdown()

    def closeEvent(self, event):
        if self._force_quit:
            event.accept()
            return
        if sys.platform == "win32" and self.tray and self.tray.isVisible():
            action = str(QSettings().value("behavior/windows_close_action", "ask"))
            if action == "ask":
                action = self._ask_windows_close_action()
            if action == "cancel":
                event.ignore()
                return
            if action == "quit":
                self._force_quit = True
                event.accept()
                QTimer.singleShot(0, QApplication.quit)
                return
            self.hide()
            event.ignore()
            return
        if self.tray and self.tray.isVisible():
            self.hide()
            event.ignore()
            if sys.platform == "darwin":
                QTimer.singleShot(0, lambda: set_macos_activation_policy(True))
            return
        super().closeEvent(event)

    def _ask_windows_close_action(self):
        dialog = QMessageBox(QMessageBox.Icon.Question, t("desktop.close_window"), t("desktop.close_window_prompt"), parent=self)
        minimize_button = dialog.addButton(t("desktop.minimize_to_tray"), QMessageBox.ButtonRole.AcceptRole)
        quit_button = dialog.addButton(t("desktop.quit_app"), QMessageBox.ButtonRole.DestructiveRole)
        dialog.addButton(t("desktop.cancel"), QMessageBox.ButtonRole.RejectRole)
        remember = QCheckBox(t("desktop.remember_close_action"), dialog)
        dialog.setCheckBox(remember)
        dialog.exec()
        clicked = dialog.clickedButton()
        action = "tray" if clicked is minimize_button else "quit" if clicked is quit_button else "cancel"
        if remember.isChecked() and action in {"tray", "quit"}:
            QSettings().setValue("behavior/windows_close_action", action)
        return action
