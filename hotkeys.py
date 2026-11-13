from PySide6.QtCore import QObject, Signal
from pynput import keyboard

def key_name(key):
    """Convert a pynput key into a normalized name."""
    if isinstance(key, keyboard.KeyCode):
        return key.char.lower() if key.char else None

    aliases = {
        "ctrl_l": "ctrl", "ctrl_r": "ctrl",
        "alt_l": "alt", "alt_r": "alt",
        "shift_l": "shift", "shift_r": "shift",
        "cmd_l": "cmd", "cmd_r": "cmd",
        "return": "enter",
    }
    return aliases.get(key.name, key.name)

def normalize_hotkey(value):
    """Return a hotkey string as a set of normalized key names."""
    if not value:
        return set()

    aliases = {
        "ctrl_l": "ctrl", "ctrl_r": "ctrl",
        "alt_l": "alt", "alt_r": "alt",
        "shift_l": "shift", "shift_r": "shift",
        "cmd_l": "cmd", "cmd_r": "cmd",
    }
    return {
        aliases.get(part.strip().lower(), part.strip().lower())
        for part in value.split("+") if part.strip()
    }

def format_hotkey(value):
    names = normalize_hotkey(value)
    order = ["ctrl", "alt", "shift", "cmd"]
    result = [name.title() for name in order if name in names]
    other_names = sorted(names - set(order))
    result.extend(
        name.upper() if name.startswith("f") and name[1:].isdigit()
        else name.title()
        for name in other_names
    )
    return " + ".join(result)

def serialize_hotkey(names):
    order = ["ctrl", "alt", "shift", "cmd"]
    result = [name for name in order if name in names]
    result.extend(sorted(names - set(order)))
    return "+".join(result)

class KeyboardBridge(QObject):
    """Listen for global hotkeys and forward events to the GUI thread."""

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
            on_press=self.on_press, on_release=self.on_release
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

        if self.capture_target is not None and not self.pressed_keys:
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
        