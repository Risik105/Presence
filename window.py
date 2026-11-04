from PySide6.QtCore import QSettings
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
    QStyle,
)

from clicker import Clicker
from hotkeys import KeyboardBridge, format_hotkey, normalize_hotkey

class AutoClicker(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Presence")
        self.setMinimumWidth(380)

        self.settings = QSettings(
            "Presense",
            "AutoClicker",
        )

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

        self.capture_target = None

        self.create_interface()
        self.create_tray_icon()

    def create_tray_icon(self):
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)
        )
        self.tray_icon.setToolTip("Presence - Autoclicker")

        tray_menu = QMenu()
        show_action = tray_menu.addAction("Открыть Presence")
        show_action.triggered.connect(self.show_from_tray)
        tray_menu.addSeparator()
        quit_action = tray_menu.addAction("Quit")
        quit_action.triggered.connect(self.quit_application)
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.on_tray_activated)

        self.tray_available = QSystemTrayIcon.isSystemTrayAvailable()
        if self.tray_available:
            self.tray_icon.show()

    def create_interface(self):
        layout = QVBoxLayout()

        layout.addWidget(QLabel("Режим работы:"))

        self.mode = QComboBox()
        self.mode.addItem("Повторять сериями", "repeat")
        self.mode.addItem("Ограниченное количество кликов", "limited")
        self.mode.currentIndexChanged.connect(self.update_mode)
        layout.addWidget(self.mode)

        layout.addWidget(QLabel("Интервал между действиями:"))

        time_layout = QHBoxLayout()

        self.minutes = QSpinBox()
        self.minutes.setRange(0, 999)
        self.minutes.setSuffix(" мин")
        time_layout.addWidget(self.minutes)

        self.seconds = QSpinBox()
        self.seconds.setRange(0, 59)
        self.seconds.setValue(4)
        self.seconds.setSuffix(" с")
        time_layout.addWidget(self.seconds)

        layout.addLayout(time_layout)

        self.amount_label = QLabel()
        layout.addWidget(self.amount_label)

        self.amount = QSpinBox()
        self.amount.setRange(1, 100000)
        self.amount.setValue(1)
        layout.addWidget(self.amount)

        self.start_button = QPushButton("Запустить")
        self.start_button.clicked.connect(self.start_clicking)
        layout.addWidget(self.start_button)

        self.stop_button = QPushButton("Остановить")
        self.stop_button.clicked.connect(self.stop_clicking)
        self.stop_button.setEnabled(False)
        layout.addWidget(self.stop_button)

        self.status = QLabel("Состояние: ожидание")
        layout.addWidget(self.status)

        self.counter = QLabel("Выполнено кликов: 0")
        layout.addWidget(self.counter)

        layout.addWidget(QLabel("Горячие клавиши"))

        start_layout = QHBoxLayout()
        start_layout.addWidget(QLabel("Запуск:"))

        self.start_hotkey_label = QLabel(
            format_hotkey(self.start_hotkey)
        )
        start_layout.addWidget(self.start_hotkey_label)

        self.start_record_button = QPushButton("Изменить")
        self.start_record_button.clicked.connect(
            lambda: self.begin_capture("start")
        )
        start_layout.addWidget(self.start_record_button)
        layout.addLayout(start_layout)

        stop_layout = QHBoxLayout()
        stop_layout.addWidget(QLabel("Остановка:"))

        self.stop_hotkey_label = QLabel(
            format_hotkey(self.stop_hotkey)
        )
        stop_layout.addWidget(self.stop_hotkey_label)

        self.stop_record_button = QPushButton("Изменить")
        self.stop_record_button.clicked.connect(
            lambda: self.begin_capture("stop")
        )
        stop_layout.addWidget(self.stop_record_button)
        layout.addLayout(stop_layout)

        self.capture_status = QLabel(
            "Нажми «Изменить», чтобы назначить комбинацию."
        )
        layout.addWidget(self.capture_status)

        self.cancel_capture_button = QPushButton(
            "Отменить запись клавиши"
        )
        self.cancel_capture_button.clicked.connect(
            self.cancel_capture
        )
        self.cancel_capture_button.setEnabled(False)
        layout.addWidget(self.cancel_capture_button)

        self.setLayout(layout)
        self.update_mode()

    def update_mode(self):
        if self.mode.currentData() == "repeat":
            self.amount_label.setText(
                "Количество кликов в серии:"
            )
        else:
            self.amount_label.setText(
                "Общее количество кликов:"
            )

    def begin_capture(self, target):
        self.capture_target = target
        self.keyboard_bridge.begin_capture(target)

        self.start_record_button.setEnabled(False)
        self.stop_record_button.setEnabled(False)
        self.cancel_capture_button.setEnabled(True)

        action = "запуску" if target == "start" else "остановки"
        self.capture_status.setText(
            f"Нажми клавишу или комбинацию для {action}..."
        )

    def cancel_capture(self):
        self.keyboard_bridge.cancel_capture()
        self.capture_target = None

        self.start_record_button.setEnabled(True)
        self.stop_record_button.setEnabled(True)
        self.cancel_capture_button.setEnabled(False)

        self.capture_status.setText("Запись отменена.")

    def finish_capture(self, target, combo):
        self.capture_target = None

        self.start_record_button.setEnabled(True)
        self.stop_record_button.setEnabled(True)
        self.cancel_capture_button.setEnabled(False)

        if not combo:
            self.capture_status.setText(
                "Не удалось записать клавишу."
            )
            return

        if not normalize_hotkey(combo) - {
            "ctrl", "alt", "shift", "cmd"
        }:
            self.capture_status.setText(
                "Выберите клавишу или комбинацию, "
                "которая содержит не только модификаторы."
            )
            return

        if target == "start":
            if normalize_hotkey(combo) == normalize_hotkey(
                self.stop_hotkey
            ):
                self.capture_status.setText(
                    "Комбинация уже используется для остановки."
                )
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
                self.capture_status.setText(
                    "Комбинация уже используется для запуска."
                )
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

        self.capture_status.setText(
            "Горячие клавиши сохранены."
        )

    def start_clicking(self):
        if self.running:
            return

        interval = self.minutes.value() * 60 + self.seconds.value()
        if interval < 1:
            QMessageBox.warning(
                self,
                "Некорректный интервал",
                "Интервал должен быть не меньше 1 секунды.",
            )
            return

        self.clicker.start(
            interval * 1000,
            self.mode.currentData(),
            self.amount.value(),
        )
        self.running = True
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.mode.setEnabled(False)
        self.minutes.setEnabled(False)
        self.seconds.setEnabled(False)
        self.amount.setEnabled(False)
        self.status.setText("Состояние: работает")
        self.counter.setText("Выполнено кликов: 0")

    def update_click_count(self, count):
        self.counter.setText(f"Выполнено кликов: {count}")

    def clicking_finished(self):
        self.stop_clicking("Состояние: завершено")

    def clicking_failed(self, message):
        self.stop_clicking("Состояние: ошибка")
        QMessageBox.critical(self, "Ошибка управления мышью", message)

    def stop_clicking(self, status_text=None):
        self.clicker.stop()
        self.running = False
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.mode.setEnabled(True)
        self.minutes.setEnabled(True)
        self.seconds.setEnabled(True)
        self.amount.setEnabled(True)
        self.status.setText(status_text or "Состояние: остановлено")

    def closeEvent(self, event):
        if self.tray_available and not getattr(self, "quitting", False):
            self.hide()
            self.tray_icon.showMessage(
                "Presence",
                "Автокликер работает в системном трее.",
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
        