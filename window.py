from pathlib import Path

from PySide6.QtCore import QElapsedTimer, QSettings, QTimer, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QComboBox,
    QSpinBox,
    QMessageBox,
    QSystemTrayIcon,
    QMenu,
    QFrame,
)

from clicker import Clicker
from hotkeys import KeyboardBridge, format_hotkey, normalize_hotkey
from translations import LANGUAGE_NAMES, TRANSLATIONS

class AutoClicker(QWidget):
    def __init__(self):
        super().__init__()

        self.setObjectName("mainWindow")
        self.setWindowTitle("Presence")
        self.setMinimumSize(760, 470)
        images_dir = Path(__file__).resolve().parent / "images"
        self.app_icon = QIcon(str(images_dir / "presence_icon_app.svg"))
        self.setWindowIcon(self.app_icon)
        QApplication.instance().setWindowIcon(self.app_icon)
        self.settings = QSettings(
            "Presence",
            "AutoClicker",
        )
        saved_theme = self.settings.value("theme", "dark", type=str)
        self.theme_code = (
            saved_theme
            if saved_theme in {"dark", "light", "system"}
            else "dark"
        )
        self.apply_theme()
        QApplication.styleHints().colorSchemeChanged.connect(
            self.on_system_color_scheme_changed
        )

        saved_language = self.settings.value("language", "en", type=str)
        self.language_code = saved_language if saved_language in TRANSLATIONS else "en"
        self.status_key = "status_waiting"
        self.capture_status_key = "capture_hint"

        self.start_hotkey = self.settings.value(
            "start_hotkey", "ctrl+f6", type=str
        )
        self.stop_hotkey = self.settings.value(
            "stop_hotkey", "ctrl+f7", type=str
        )

        self.clicker = Clicker(self)
        self.clicker.click_count_changed.connect(self.update_click_count)
        self.clicker.finished.connect(self.clicking_finished)
        self.clicker.failed.connect(self.clicking_failed)

        self.keyboard_bridge = KeyboardBridge()
        self.keyboard_bridge.set_hotkeys(
            self.start_hotkey,
            self.stop_hotkey,
        )

        self.keyboard_bridge.start_requested.connect(
            self.start_clicking
        )
        self.keyboard_bridge.stop_requested.connect(
            self.stop_clicking
        )
        self.keyboard_bridge.capture_finished.connect(
            self.finish_capture
        )

        self.running = False
        self.elapsed_clock = QElapsedTimer()
        self.elapsed_timer = QTimer(self)
        self.elapsed_timer.setInterval(1000)
        self.elapsed_timer.timeout.connect(self.update_elapsed_time)

        self.capture_target = None

        self.create_interface()
        self.create_tray_icon()

    def create_tray_icon(self):
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(self.app_icon)
        self.tray_icon.setToolTip(self.tr("tray_tooltip"))

        tray_menu = QMenu()
        self.show_action = tray_menu.addAction(self.tr("tray_open"))
        self.show_action.triggered.connect(self.show_from_tray)
        tray_menu.addSeparator()
        self.quit_action = tray_menu.addAction(self.tr("tray_quit"))
        self.quit_action.triggered.connect(self.quit_application)
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.on_tray_activated)

        self.tray_available = QSystemTrayIcon.isSystemTrayAvailable()
        if self.tray_available:
            self.tray_icon.show()

    def create_interface(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(20)

        header = QHBoxLayout()
        header.setSpacing(18)
        title_stack = QVBoxLayout()
        title_stack.setSpacing(1)
        self.title_label = QLabel("Presence")
        self.title_label.setObjectName("appTitle")
        self.subtitle_label = QLabel()
        self.subtitle_label.setObjectName("appSubtitle")
        title_stack.addWidget(self.title_label)
        title_stack.addWidget(self.subtitle_label)
        header.addLayout(title_stack)
        header.addStretch()
        self.theme_label = QLabel()
        header.addWidget(self.theme_label)
        self.theme_selector = QComboBox()
        self.theme_selector.addItem("", "dark")
        self.theme_selector.addItem("", "light")
        self.theme_selector.addItem("", "system")
        self.theme_selector.setMinimumWidth(110)
        self.theme_selector.currentIndexChanged.connect(self.change_theme)
        header.addWidget(self.theme_selector)
        self.language_label = QLabel()
        header.addWidget(self.language_label)
        self.language_selector = QComboBox()
        for code, name in LANGUAGE_NAMES.items():
            self.language_selector.addItem(name, code)
        self.language_selector.setMinimumWidth(140)
        self.language_selector.currentIndexChanged.connect(self.change_language)
        header.addWidget(self.language_selector)
        layout.addLayout(header)

        content = QHBoxLayout()
        content.setSpacing(18)
        settings_panel = QFrame()
        settings_panel.setObjectName("panel")
        settings_layout = QVBoxLayout(settings_panel)
        settings_layout.setContentsMargins(20, 20, 20, 20)
        settings_layout.setSpacing(10)

        self.settings_title = QLabel()
        self.settings_title.setObjectName("sectionTitle")
        settings_layout.addWidget(self.settings_title)

        self.mode_label = QLabel()
        settings_layout.addWidget(self.mode_label)
        self.mode = QComboBox()
        self.mode.addItem("", "repeat")
        self.mode.addItem("", "limited")
        self.mode.currentIndexChanged.connect(self.update_mode)
        settings_layout.addWidget(self.mode)

        self.interval_label = QLabel()
        settings_layout.addWidget(self.interval_label)
        time_layout = QHBoxLayout()
        time_layout.setSpacing(10)
        self.minutes = QSpinBox()
        self.minutes.setRange(0, 999)
        self.minutes.lineEdit().setTextMargins(12, 0, 12, 0)
        time_layout.addWidget(self.minutes, 2)
        self.seconds = QSpinBox()
        self.seconds.setRange(0, 59)
        self.seconds.setValue(4)
        self.seconds.lineEdit().setTextMargins(12, 0, 12, 0)
        time_layout.addWidget(self.seconds, 1)
        settings_layout.addLayout(time_layout)

        self.amount_label = QLabel()
        settings_layout.addWidget(self.amount_label)
        self.amount = QSpinBox()
        self.amount.setRange(1, 100000)
        self.amount.setValue(1)
        self.amount.lineEdit().setTextMargins(12, 0, 12, 0)
        settings_layout.addWidget(self.amount)

        buttons = QHBoxLayout()
        buttons.setSpacing(10)
        self.start_button = QPushButton()
        self.start_button.setObjectName("startButton")
        self.start_button.clicked.connect(self.start_clicking)
        buttons.addWidget(self.start_button)
        self.stop_button = QPushButton()
        self.stop_button.setObjectName("stopButton")
        self.stop_button.clicked.connect(self.stop_clicking)
        self.stop_button.setEnabled(False)
        buttons.addWidget(self.stop_button)
        settings_layout.addLayout(buttons)

        self.status = QLabel()
        self.status.setObjectName("statusLabel")
        settings_layout.addWidget(self.status)
        settings_layout.addStretch()

        activity_panel = QFrame()
        activity_panel.setObjectName("panel")
        activity_layout = QVBoxLayout(activity_panel)
        activity_layout.setContentsMargins(20, 20, 20, 20)
        activity_layout.setSpacing(12)
        self.activity_title = QLabel()
        self.activity_title.setObjectName("sectionTitle")
        activity_layout.addWidget(self.activity_title)

        self.counter = QLabel()
        self.counter.setObjectName("metricLabel")
        activity_layout.addWidget(self.counter)
        self.elapsed_label = QLabel()
        self.elapsed_label.setObjectName("metricLabel")
        activity_layout.addWidget(self.elapsed_label)

        self.hotkeys_title = QLabel()
        self.hotkeys_title.setObjectName("sectionTitle")
        activity_layout.addWidget(self.hotkeys_title)

        start_layout = QHBoxLayout()
        start_layout.setSpacing(10)
        self.start_hotkey_title = QLabel()
        start_layout.addWidget(self.start_hotkey_title)
        self.start_hotkey_label = QLabel(format_hotkey(self.start_hotkey))
        self.start_hotkey_label.setMinimumWidth(65)
        start_layout.addWidget(self.start_hotkey_label)
        self.start_record_button = QPushButton()
        self.start_record_button.clicked.connect(
            lambda: self.begin_capture("start")
        )
        start_layout.addWidget(self.start_record_button)
        activity_layout.addLayout(start_layout)

        stop_layout = QHBoxLayout()
        stop_layout.setSpacing(10)
        self.stop_hotkey_title = QLabel()
        stop_layout.addWidget(self.stop_hotkey_title)
        self.stop_hotkey_label = QLabel(format_hotkey(self.stop_hotkey))
        self.stop_hotkey_label.setMinimumWidth(65)
        stop_layout.addWidget(self.stop_hotkey_label)
        self.stop_record_button = QPushButton()
        self.stop_record_button.clicked.connect(
            lambda: self.begin_capture("stop")
        )
        stop_layout.addWidget(self.stop_record_button)
        activity_layout.addLayout(stop_layout)

        self.capture_status = QLabel()
        self.capture_status.setObjectName("captureStatus")
        self.capture_status.setWordWrap(True)
        activity_layout.addWidget(self.capture_status)
        self.cancel_capture_button = QPushButton()
        self.cancel_capture_button.clicked.connect(self.cancel_capture)
        self.cancel_capture_button.setEnabled(False)
        activity_layout.addWidget(self.cancel_capture_button)
        activity_layout.addStretch()

        content.addWidget(settings_panel, 11)
        content.addWidget(activity_panel, 10)
        layout.addLayout(content, 1)

        language_index = self.language_selector.findData(self.language_code)
        self.language_selector.setCurrentIndex(language_index)
        theme_index = self.theme_selector.findData(self.theme_code)
        self.theme_selector.setCurrentIndex(theme_index)
        self.minutes.setSuffix(self.tr("minutes"))
        self.seconds.setSuffix(self.tr("seconds"))
        self.update_language()
        self.update_mode()

    def tr(self, key, **values):
        return TRANSLATIONS[self.language_code][key].format(**values)

    def apply_theme(self):
        project_dir = Path(__file__).resolve().parent
        style_dir = project_dir / "styles"
        images_dir = project_dir / "images"
        if self.theme_code == "system":
            system_scheme = QApplication.styleHints().colorScheme()
            self.active_theme = (
                "light" if system_scheme == Qt.ColorScheme.Light else "dark"
            )
        else:
            self.active_theme = self.theme_code

        stylesheet = (style_dir / f"{self.active_theme}.qss").read_text(
            encoding="utf-8"
        )
        icon_suffix = "-light" if self.active_theme == "light" else ""
        for direction in ("down", "up"):
            icon_name = f"chevron-{direction}{icon_suffix}.svg"
            icon_path = (images_dir / icon_name).resolve().as_posix()
            stylesheet = stylesheet.replace(
                f"url(../images/{icon_name})", f'url("{icon_path}")'
            )
        self.setStyleSheet(stylesheet)

    def on_system_color_scheme_changed(self, _scheme):
        if self.theme_code == "system":
            self.apply_theme()

    def change_theme(self):
        theme_code = self.theme_selector.currentData()
        if not theme_code or theme_code == self.theme_code:
            return
        self.theme_code = theme_code
        self.settings.setValue("theme", theme_code)
        self.apply_theme()

    def change_language(self):
        language_code = self.language_selector.currentData()
        if not language_code or language_code == self.language_code:
            return
        self.language_code = language_code
        self.settings.setValue("language", language_code)
        self.update_language()

    def update_language(self):
        self.subtitle_label.setText(self.tr("app_subtitle"))
        self.language_label.setText(self.tr("language"))
        self.theme_label.setText(self.tr("theme"))
        self.theme_selector.setItemText(0, self.tr("dark_theme"))
        self.theme_selector.setItemText(1, self.tr("light_theme"))
        self.theme_selector.setItemText(2, self.tr("system_theme"))
        self.settings_title.setText(self.tr("settings_title"))
        self.activity_title.setText(self.tr("activity_title"))
        self.mode_label.setText(self.tr("mode_label"))
        self.interval_label.setText(self.tr("interval"))
        self.minutes.setSuffix(self.tr("minutes"))
        self.seconds.setSuffix(self.tr("seconds"))
        self.mode.setItemText(0, self.tr("repeat_mode"))
        self.mode.setItemText(1, self.tr("limited_mode"))
        self.start_button.setText(self.tr("start"))
        self.stop_button.setText(self.tr("stop"))
        self.hotkeys_title.setText(self.tr("hotkeys"))
        self.start_hotkey_title.setText(self.tr("launch"))
        self.stop_hotkey_title.setText(self.tr("halt"))
        self.start_record_button.setText(self.tr("change"))
        self.stop_record_button.setText(self.tr("change"))
        self.cancel_capture_button.setText(self.tr("cancel_capture"))
        self.status.setText(self.tr(self.status_key))
        self.counter.setText(self.tr("click_count", count=self.clicker.click_count))
        self.update_elapsed_time()
        self.update_mode()
        self.capture_status.setText(self.tr(self.capture_status_key))
        if hasattr(self, "tray_icon"):
            self.tray_icon.setToolTip(self.tr("tray_tooltip"))
            self.show_action.setText(self.tr("tray_open"))
            self.quit_action.setText(self.tr("tray_quit"))

    def update_mode(self):
        if self.mode.currentData() == "repeat":
            self.amount_label.setText(self.tr("batch_count"))
        else:
            self.amount_label.setText(self.tr("total_count"))

    def begin_capture(self, target):
        self.capture_target = target
        self.keyboard_bridge.begin_capture(target)

        self.start_record_button.setEnabled(False)
        self.stop_record_button.setEnabled(False)
        self.cancel_capture_button.setEnabled(True)

        self.capture_status_key = f"capturing_{target}"
        self.capture_status.setText(self.tr(self.capture_status_key))

    def cancel_capture(self):
        self.keyboard_bridge.cancel_capture()
        self.capture_target = None

        self.start_record_button.setEnabled(True)
        self.stop_record_button.setEnabled(True)
        self.cancel_capture_button.setEnabled(False)

        self.capture_status_key = "capture_cancelled"
        self.capture_status.setText(self.tr(self.capture_status_key))

    def finish_capture(self, target, combo):
        self.capture_target = None

        self.start_record_button.setEnabled(True)
        self.stop_record_button.setEnabled(True)
        self.cancel_capture_button.setEnabled(False)

        if not combo:
            self.capture_status_key = "capture_failed"
            self.capture_status.setText(self.tr(self.capture_status_key))
            return

        if not normalize_hotkey(combo) - {
            "ctrl", "alt", "shift", "cmd"
        }:
            self.capture_status_key = "modifier_error"
            self.capture_status.setText(self.tr(self.capture_status_key))
            return

        if target == "start":
            if normalize_hotkey(combo) == normalize_hotkey(
                self.stop_hotkey
            ):
                self.capture_status_key = "duplicate_stop"
                self.capture_status.setText(self.tr(self.capture_status_key))
                return

            self.start_hotkey = combo
            self.start_hotkey_label.setText(
                format_hotkey(combo)
            )
            self.settings.setValue("start_hotkey", combo)

        else:
            if normalize_hotkey(combo) == normalize_hotkey(
                self.start_hotkey
            ):
                self.capture_status_key = "duplicate_start"
                self.capture_status.setText(self.tr(self.capture_status_key))
                return

            self.stop_hotkey = combo
            self.stop_hotkey_label.setText(
                format_hotkey(combo)
            )
            self.settings.setValue("stop_hotkey", combo)

        self.keyboard_bridge.set_hotkeys(
            self.start_hotkey,
            self.stop_hotkey,
        )

        self.capture_status_key = "hotkeys_saved"
        self.capture_status.setText(self.tr(self.capture_status_key))

    def start_clicking(self):
        if self.running:
            return

        interval = self.minutes.value() * 60 + self.seconds.value()
        if interval < 1:
            QMessageBox.warning(
                self,
                self.tr("invalid_interval_title"),
                self.tr("invalid_interval"),
            )
            return

        self.clicker.start(
            interval * 1000,
            self.mode.currentData(),
            self.amount.value(),
        )
        self.running = True
        self.elapsed_clock.start()
        self.elapsed_timer.start()
        self.update_elapsed_time()
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.mode.setEnabled(False)
        self.minutes.setEnabled(False)
        self.seconds.setEnabled(False)
        self.amount.setEnabled(False)
        self.status_key = "status_running"
        self.status.setText(self.tr(self.status_key))
        self.counter.setText(self.tr("click_count", count=0))

    def update_click_count(self, count):
        self.counter.setText(self.tr("click_count", count=count))

    def update_elapsed_time(self):
        elapsed_seconds = (
            self.elapsed_clock.elapsed() // 1000
            if self.elapsed_clock.isValid()
            else 0
        )
        hours, remainder = divmod(elapsed_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        self.elapsed_label.setText(
            self.tr("elapsed", time=f"{hours:02d}:{minutes:02d}:{seconds:02d}")
        )

    def clicking_finished(self):
        self.stop_clicking("status_completed")

    def clicking_failed(self, message):
        self.stop_clicking("status_error")
        QMessageBox.critical(self, self.tr("mouse_error_title"), message)

    def stop_clicking(self, status_text=None):
        self.clicker.stop()
        self.elapsed_timer.stop()
        if self.elapsed_clock.isValid():
            self.update_elapsed_time()
        self.running = False
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.mode.setEnabled(True)
        self.minutes.setEnabled(True)
        self.seconds.setEnabled(True)
        self.amount.setEnabled(True)
        self.status_key = status_text or "status_stopped"
        self.status.setText(self.tr(self.status_key))

    def closeEvent(self, event):
        if self.tray_available and not getattr(self, "quitting", False):
            self.hide()
            self.tray_icon.showMessage(
                "Presence",
                self.tr("tray_hidden"),
                QSystemTrayIcon.MessageIcon.Information,
                2500,
            )
            event.ignore()
            return

        self.stop_clicking()
        self.keyboard_bridge.close()
        event.accept()

    def show_from_tray(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def on_tray_activated(self, reason):
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            if self.isVisible():
                self.hide()
            else:
                self.show_from_tray()

    def quit_application(self):
        self.quitting = True
        self.tray_icon.hide()
        self.close()
        QApplication.quit()
        