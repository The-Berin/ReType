"""
The runner: play a humanizer op-stream into a "sink".

TypeEngine pulls ops one at a time and schedules the next with Tk's `after`, so
the GUI stays live - Pause, Resume and Stop take effect between any two ops.

Op kinds:
    ('type', ch, ms)        type a character at the cursor
    ('back', None, ms)      backspace at the cursor
    ('left'/'right', ...)   move the cursor one character
    ('cursor_home'/'cursor_end', ...)   jump to document start / end
    ('pause', None, ms)     just wait

Where the keystrokes go is a swappable sink:
    KeyboardSink    - the real keyboard via OS-level injection (other windows)
    TextWidgetSink  - a Tk Text, cursor-aware, for the in-app Demo preview

Anti-detection notes for KeyboardSink:
    * keystrokes go in at the OS level (SendInput), so the browser sees genuine
      isTrusted key events - JS / reCAPTCHA can't tell them from a real keyboard.
    * every printable key is pressed DOWN, held a randomised human dwell
      (35-95 ms), then released - instead of pyautogui's instant down+up, whose
      near-zero dwell is the clearest keystroke-biometric bot tell.
    * the corner failsafe still works: write() calls pyautogui.failSafeCheck().
"""

import sys
import random

import pyautogui

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0


# --- Unicode-capable, dwell-controllable keystroke injection (Windows) -------
if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    _ULONG_PTR = ctypes.c_size_t
    _KEYEVENTF_UNICODE = 0x0004
    _KEYEVENTF_KEYUP = 0x0002
    _INPUT_KEYBOARD = 1

    class _KEYBDINPUT(ctypes.Structure):
        _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD),
                    ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
                    ("dwExtraInfo", _ULONG_PTR)]

    class _MOUSEINPUT(ctypes.Structure):       # only here to size the union right
        _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG),
                    ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
                    ("time", wintypes.DWORD), ("dwExtraInfo", _ULONG_PTR)]

    class _INPUTUNION(ctypes.Union):
        _fields_ = [("ki", _KEYBDINPUT), ("mi", _MOUSEINPUT)]

    class _INPUT(ctypes.Structure):
        _fields_ = [("type", wintypes.DWORD), ("u", _INPUTUNION)]

    def _send_units(units, keyup):
        flags = _KEYEVENTF_UNICODE | (_KEYEVENTF_KEYUP if keyup else 0)
        for unit in units:
            inp = _INPUT(type=_INPUT_KEYBOARD,
                         u=_INPUTUNION(ki=_KEYBDINPUT(0, unit, flags, 0, 0)))
            ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(_INPUT))

    def _units_for(ch):
        o = ord(ch)
        if o <= 0xFFFF:
            return [o]
        o -= 0x10000                           # astral plane -> UTF-16 surrogate pair
        return [0xD800 + (o >> 10), 0xDC00 + (o & 0x3FF)]

    def unicode_key(ch, *, up):
        _send_units(_units_for(ch), keyup=up)

    def type_unicode_char(ch):
        units = _units_for(ch)
        _send_units(units, keyup=False)
        _send_units(units, keyup=True)
else:
    def unicode_key(ch, *, up):
        if not up:
            pyautogui.write(ch)

    def type_unicode_char(ch):
        pyautogui.write(ch)


class KeyboardSink:
    """Types into whatever window has focus: OS-level, Unicode, with key dwell."""
    can_failsafe = True

    def __init__(self, root=None, dwell=(35, 95)):
        self.root = root                       # if set (and Windows), enables dwell
        self.dwell = dwell
        self._held = []                        # outstanding key-up timers

    def _printable(self, ch):
        return len(ch) == 1 and ord(ch) >= 32

    def write(self, ch):
        pyautogui.failSafeCheck()              # keep the corner-abort alive
        if ch in ("\n", "\r"):
            pyautogui.press("enter")
            return
        if ch == "\t":
            pyautogui.press("tab")
            return
        if self.root is not None and sys.platform == "win32" and self._printable(ch):
            unicode_key(ch, up=False)          # press down now...
            ref = {"ch": ch}
            ref["jid"] = self.root.after(random.randint(*self.dwell),
                                         lambda r=ref: self._release(r))
            self._held.append(ref)             # ...release after a human dwell
        elif self._printable(ch):
            type_unicode_char(ch) if ord(ch) >= 127 else pyautogui.write(ch)
        else:
            type_unicode_char(ch)

    def _release(self, ref):
        try:
            unicode_key(ref["ch"], up=True)
        except Exception:
            pass
        try:
            self._held.remove(ref)
        except ValueError:
            pass

    def backspace(self):
        pyautogui.failSafeCheck()
        pyautogui.press("backspace")

    def left(self):
        pyautogui.failSafeCheck()
        pyautogui.press("left")

    def right(self):
        pyautogui.failSafeCheck()
        pyautogui.press("right")

    def doc_home(self):
        pyautogui.failSafeCheck()
        pyautogui.hotkey("ctrl", "home")

    def doc_end(self):
        pyautogui.failSafeCheck()
        pyautogui.hotkey("ctrl", "end")

    def release(self):
        """Cancel pending key-ups and make sure nothing is left held down."""
        for ref in list(self._held):
            if self.root is not None:
                try:
                    self.root.after_cancel(ref["jid"])
                except Exception:
                    pass
            try:
                unicode_key(ref["ch"], up=True)
            except Exception:
                pass
        self._held.clear()

    def reset(self):
        self.release()


class TextWidgetSink:
    """Cursor-aware sink into a Tk Text, for the in-app Demo preview."""
    can_failsafe = False

    def __init__(self, widget):
        self.w = widget

    def write(self, ch):
        self.w.insert("insert", ch)
        self.w.see("insert")

    def backspace(self):
        if self.w.index("insert") != "1.0":
            self.w.delete("insert -1c", "insert")

    def left(self):
        self.w.mark_set("insert", "insert -1c")
        self.w.see("insert")

    def right(self):
        self.w.mark_set("insert", "insert +1c")
        self.w.see("insert")

    def doc_home(self):
        self.w.mark_set("insert", "1.0")
        self.w.see("insert")

    def doc_end(self):
        self.w.mark_set("insert", "end -1c")
        self.w.see("insert")

    def release(self):
        pass

    def reset(self):
        self.w.delete("1.0", "end")
        self.w.mark_set("insert", "1.0")


class TypeEngine:
    def __init__(self, root, *, on_op=None, on_progress=None,
                 on_status=None, on_done=None, on_abort=None):
        self.root = root
        self.on_op = on_op                 # (kind, value, delay_ms) -> cardiogram
        self.on_progress = on_progress     # (net, total) -> progress bar
        self.on_status = on_status         # (text) -> status line
        self.on_done = on_done             # () -> finished cleanly
        self.on_abort = on_abort           # (reason) -> failsafe / error

        self.sink = KeyboardSink()
        self.ops = None
        self.total = 0
        self.net = 0
        self.job = None
        self.running = False
        self.paused = False

    # ----------------------------------------------------------- lifecycle ---
    def start(self, ops_iterable, total_chars, sink=None):
        self.stop()
        if sink is not None:
            self.sink = sink
        self.ops = iter(ops_iterable)
        self.total = max(1, total_chars)
        self.net = 0
        self.running = True
        self.paused = False
        self._tick()

    def pause(self):
        if self.running and not self.paused:
            self.paused = True
            self._cancel()

    def resume(self):
        if self.running and self.paused:
            self.paused = False
            self._tick()

    def stop(self):
        self._cancel()
        self.running = False
        self.paused = False
        self.ops = None
        try:
            self.sink.release()
        except Exception:
            pass

    def _cancel(self):
        if self.job is not None:
            self.root.after_cancel(self.job)
            self.job = None

    # ---------------------------------------------------------------- tick ---
    def _tick(self):
        if not self.running or self.paused:
            return
        try:
            kind, value, delay = next(self.ops)
        except StopIteration:
            self.running = False
            self.job = None
            try:
                self.sink.release()
            except Exception:
                pass
            if self.on_done:
                self.on_done()
            return

        try:
            if kind == "type":
                self.sink.write(value)
                self.net += 1
            elif kind == "back":
                self.sink.backspace()
                self.net -= 1
            elif kind == "left":
                self.sink.left()
            elif kind == "right":
                self.sink.right()
            elif kind == "cursor_home":
                self.sink.doc_home()
            elif kind == "cursor_end":
                self.sink.doc_end()
        except pyautogui.FailSafeException:
            self.stop()
            if self.on_abort:
                self.on_abort("failsafe")
            return

        if self.on_op:
            self.on_op(kind, value, delay)
        if self.on_progress and kind in ("type", "back"):
            self.on_progress(max(0, self.net), self.total)

        self.job = self.root.after(max(1, int(delay)), self._tick)
