import sys

from PySide6.QtCore import QTimer, QObject, Signal
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

from pynput.mouse import Button, Controller
from pynput import keyboard

def key_name(key):
    """Превращает клавишу pynput в текстовое значение."""
    if isinstance(key, keyboard.KeyCode):
        if key.char:
            return key.char.lower()
        return None

    name = key.name

    aliases = {
        "ctrl_l": "ctrl",
        "ctrl_r": "ctrl",
        "alt_l": "alt",
        "alt_r": "alt",
        "shift_l": "shift",
        "shift_r": "shift",
        "cmd_l": "cmd",
        "chd_r": "cmd",
        "esc": "esc",
        "return": "enter",
    }

    return aliases.get(name, name)

def normalize_hotkey(value):
    """Нормализует комбинацию клавиш."""
    if not value:
        return set()

    aliases = {
        "ctrl_l": "ctrl",
        "ctrl_r": "ctrl",
        "alt_l": "alt",
        "alt_r": "alt",
        "shift_l": "shift",
        "shift_r": "shift",
        "cmd_l": "cmd",
        "chd_r": "cmd",
    }

    return {
        aliases.get(part.strip().lower(), part.strip().lower())
        for part in value.split("+")
        if part.strip()
    }

def format_hotkey(value):
    """Форматирует комбинацию для отображения в окне."""
    names = normalize_hotkey(value)

    order = ["ctrl", "alt", "shift", "cmd"]
    result = [name.title() for name in order if name in names]

    other_names = sorted(names - set(order))
    result.extend(name.upper() if name.startswith("f") and name[1:].isdigit()
                  else name.title() for name in other_names)

    return " + ".join(result)

def serialize_hotkey(names):
    order = ["ctrl", "alt", "shift", "cmd"]
    result = [name for name in order if name in names]
    result.extend(sorted(names - set(order)))
    return "+".join(result)

class KeyboardBridge(QObject):
    """Обрабатывает глобальные клавиши и передает события в GUI-поток."""

    start_requested = Signal()
    stop_requested = Signal()
    capture_finished = Signal(str, str)

    def __init__(self):
        super().__init__()

        self.pressed_keys = set()
        self.captured_keys = set()
        self.capture_target = None
        self.start_hotkey = {"ctrl", "f6"}
        self.stop_hotkey = {"ctrl", "f7"}
        self.trigger_latched = False

        self.listener = keyboard.Listener(
            on_press=self.on_press,
            on_release=self.on_release,
        )
        self.listener.start()

    def set_hotkeys(self, start_hotkey, stop_hotkey):
        self.start_hotkey = normalize_hotkey(start_hotkey)
        self.stop_hotkey = normalize_hotkey(stop_hotkey)

    def begin_capture(self, target):
        self.capture_target = target
        self.captured_keys.clear()

    def cancel_capture(self):
        self.capture_target = None
        self.captured_keys.clear()

    def on_press(self, key):
        name = key_name(key)

        if name is None:
            return

        self.pressed_keys.add(name)

        if self.capture_target is not None:
            self.captured_keys.add(name)
            return

        if self.trigger_latched:
            return

        if self.pressed_keys == self.start_hotkey:
            self.trigger_latched = True
            self.start_requested.emit()

        elif self.pressed_keys == self.stop_hotkey:
            self.trigger_latched = True
            self.stop_requested.emit()

    def on_release(self, key):
        name = key_name(key)

        if name is not None:
            self.pressed_keys.discard(name)

        if self.capture_target is not None:
            if not self.pressed_keys:
                target = self.capture_target
                combo = serialize_hotkey(self.captured_keys)

                self.capture_target = None
                self.captured_keys.clear()

                self.capture_finished.emit(target, combo)

        if not self.pressed_keys:
            self.trigger_latched = False

    def close(self):
        self.cancel_capture()
        self.listener.stop()

class AutoClicker(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Presence")
        self.setMinimumWidth(380)

        self.settings = (
            QApplication.instance().settings
            if hasattr(QApplication.instance(), "settings")
            else None
        )

        #QSettings сохраняет настройки между запусками.
        from PySide6.QtCore import QSettings

        self.settings = QSettings(
            "Presence",
            "AutoClicker",
        )

        self.start_hotkey = self.settings.value(
            "start_hotkey", "ctrl+f6", type=str
        )
        self.stop_hotkey = self.settings.value(
            "stop_hotkey", "ctrl+f7", type=str
        )

        self.mouse = Controller()
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

        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.perform_clicks)

        self.click_count = 0
        self.remaining_clicks = 0
        self.batch_remaining = 0
        self.interval_ms = 0
        self.running = False

        self.capture_target = None

        self.create_interface()
        self.create_tray_icon()

    def create_tray_icon(self):
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)
        )
        self.tray_icon.setToolTip("Presence - autoclicker")

        tray_menu = QMenu()
        show_action = tray_menu.addAction("Открыть Presence")
        show_action.triggered.connect(self.show_from_tray)
        tray_menu.addSeparator()
        quit_action = tray_menu.addAction("Выйти")
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
            "Отменить запись клавиш"
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

        interval = (
            self.minutes.value() * 60
            + self.seconds.value()
        )

        if interval < 1:
            QMessageBox.warning(
                self,
                "Некорректный интервал",
                "Интервал должен быть не меньше 1 секунды.",
            )    
            return

        self.click_count = 0
        self.remaining_clicks = self.amount.value()
        self.batch_remaining = 0
        self.interval_ms = interval * 1000
        self.running = True

        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.mode.setEnabled(False)
        self.minutes.setEnabled(False)
        self.seconds.setEnabled(False)
        self.amount.setEnabled(False)

        self.status.setText("Состояние: работает")
        self.counter.setText("Выполнено кликов: 0")

        self.timer.start(self.interval_ms)

    def perform_clicks(self):
        if not self.running:
            return

        try:
            self.mouse.click(Button.left, 1)
            self.click_count += 1

            self.counter.setText(
                f"Выполнено кликов: {self.click_count}"
            )

            if self.mode.currentData() == "repeat":
                self.batch_remaining -= 1

                if self.batch_remaining > 0:
                    QTimer.singleShot(
                        0, self.perform_one_click
                    )
                else:
                    self.timer.start(self.interval_ms)

            else:
                self.remaining_clicks -= 1

                if self.remaining_clicks == 0:
                    self.stop_clicking("Состояние: завершено")
                else:
                    self.timer.start(self.interval_ms)

        except Exception as error:
            self.stop_clicking("Состояние: ошибка")
            QMessageBox.critical(
                self,
                "Ошибка управления мышью",
                str(error)
            )

    def stop_clicking(self, status_text=None):
        self.running = False
        self.timer.stop()
        self.batch_remaining = 0

        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.mode.setEnabled(True)
        self.minutes.setEnabled(True)
        self.seconds.setEnabled(True)
        self.amount.setEnabled(True)

        self.status.setText(
            status_text or "Состояние: остановлено"
        )

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

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    app.setOrganizationName("Presence")
    app.setApplicationName("Presence")

    window = AutoClicker()
    window.show()

    sys.exit(app.exec())
    