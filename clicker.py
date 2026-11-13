from PySide6.QtCore import QObject, QTimer, Signal
from pynput.mouse import Button, Controller

class Clicker(QObject):
    """Runs timed clicks independently of the window and its widgets."""

    click_count_changed = Signal(int)
    finished = Signal()
    failed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.mouse = Controller()
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self._perform_click)
        self.running = False
        self.mode = "limited"
        self.interval_ms = 0
        self.remaining_clicks = 0
        self.batch_remaining = 0
        self.click_count = 0

    def start(self, interval_ms, mode, amount):
        if self.running:
            return
        self.running = True
        self.mode = mode
        self.interval_ms = interval_ms
        self.remaining_clicks = amount
        self.batch_remaining = amount if mode == "repeat" else 0
        self.click_count = 0
        self.timer.start(self.interval_ms)

    def stop(self):
        self.running = False
        self.timer.stop()
        self.batch_remaining = 0

    def _perform_click(self):
        if not self.running:
            return
        try:
            self.mouse.click(Button.left, 1)
        except Exception as error:
            self.stop()
            self.failed.emit(str(error))
            return

        self.click_count += 1
        self.click_count_changed.emit(self.click_count)

        if self.mode == "repeat":
            self.batch_remaining -= 1
            if self.batch_remaining > 0:
                QTimer.singleShot(0, self._perform_click)
            else:
                self.batch_remaining = self.remaining_clicks
                self.timer.start(self.interval_ms)
        else:
            self.remaining_clicks -= 1
            if self.remaining_clicks == 0:
                self.stop()
                self.finished.emit()
            else:
                self.timer.start(self.interval_ms)
                