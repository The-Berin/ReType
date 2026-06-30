"""
Global hotkey watcher.

Lets you trigger a typing run from ANY window without alt-tabbing back to ReType.
It polls Windows' GetAsyncKeyState on the Tk event loop (no extra threads, no
keyboard hook to install or detect) and fires once per fresh press of the chosen
combo. Off Windows it's a harmless no-op.
"""

import sys

if sys.platform == "win32":
    import ctypes
    _get_async = ctypes.windll.user32.GetAsyncKeyState

    def _is_down(vk):
        return bool(_get_async(vk) & 0x8000)
else:
    def _is_down(vk):
        return False

VK_SHIFT = 0x10
VK_CTRL = 0x11
VK_ALT = 0x12

# name -> (need_ctrl, need_alt, need_shift, main_vk)
HOTKEYS = {
    "Ctrl+Alt+T": (True, True, False, 0x54),
    "Ctrl+Alt+B": (True, True, False, 0x42),
    "Ctrl+Alt+Space": (True, True, False, 0x20),
    "F9": (False, False, False, 0x78),
}
DEFAULT_HOTKEY = "Ctrl+Alt+T"


def combo_pressed(combo):
    """True while every key of `combo` (ctrl, alt, shift, vk) is held down."""
    ctrl, alt, shift, vk = combo
    if not _is_down(vk):
        return False
    if ctrl and not _is_down(VK_CTRL):
        return False
    if alt and not _is_down(VK_ALT):
        return False
    if shift and not _is_down(VK_SHIFT):
        return False
    return True


class HotkeyWatcher:
    """
    Edge-triggered global-hotkey poller driven by Tk's `after`.

    get_combo() returns the current (ctrl, alt, shift, vk) tuple (or None to
    disable); on_trigger() is called once each time the combo transitions from
    up to down.
    """

    def __init__(self, root, get_combo, on_trigger, interval=60):
        self.root = root
        self.get_combo = get_combo
        self.on_trigger = on_trigger
        self.interval = interval
        self._down = False
        self._job = None

    def start(self):
        if sys.platform == "win32" and self._job is None:
            self._poll()

    def stop(self):
        if self._job is not None:
            try:
                self.root.after_cancel(self._job)
            except Exception:
                pass
            self._job = None

    def _poll(self):
        combo = self.get_combo()
        pressed = bool(combo) and combo_pressed(combo)
        if pressed and not self._down:
            self._down = True
            try:
                self.on_trigger()
            except Exception:
                pass
        elif not pressed:
            self._down = False
        self._job = self.root.after(self.interval, self._poll)
