"""
ReType 4.0 - a realistic human-typing simulator.

Paste text, set a target speed, hit Start. After a countdown ReType types the
text wherever your cursor is focused, modelling the way a real person types:

  * speed is set in words-per-minute and *drifts* as it goes (bursts and fatigue)
  * letters slow down for digits/symbols and rest after spaces and punctuation
  * occasional "thinking" pauses at the start of words
  * five realistic mistake patterns, each with its own correction behaviour:
        - adjacent-key slip      (type a neighbouring key, backspace, fix)
        - transposition          ("teh" -> notices -> "the")
        - doubled letter         ("hello" -> "helllo" -> backspace)
        - case slip              (forgot shift, fixes it)
        - delayed correction     (types a few more chars, *then* notices and fixes)

The whole engine is a single stream of low-level ops (type / backspace / pause)
driven by Tk's `after` scheduler, so the window never freezes - Pause, Stop and
the corner failsafe all work mid-type.

Failsafe: shove the mouse into any screen corner to abort instantly.
"""

import os
import sys
import random
import tkinter as tk
from tkinter import ttk, messagebox

import pyautogui

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0

# Physically adjacent QWERTY keys - a real slip lands on a neighbour.
ADJACENT_KEYS = {
    'a': 'qwsz',   'b': 'vghn',   'c': 'xdfv',   'd': 'serfcx', 'e': 'wsdr',
    'f': 'drtgvc', 'g': 'ftyhbv', 'h': 'gyujnb', 'i': 'ujko',   'j': 'huikmn',
    'k': 'jiolm',  'l': 'kop',    'm': 'njk',    'n': 'bhjm',   'o': 'iklp',
    'p': 'ol',     'q': 'wa',     'r': 'edft',   's': 'awedxz', 't': 'rfgy',
    'u': 'yhji',   'v': 'cfgb',   'w': 'qase',   'x': 'zsdc',   'y': 'tghu',
    'z': 'asx',
}

SENTENCE_END = ".!?"
PUNCTUATION = ",;:" + SENTENCE_END


def adjacent(ch):
    """A neighbouring key for `ch`, preserving case. None if not a letter."""
    low = ch.lower()
    if low not in ADJACENT_KEYS:
        return None
    wrong = random.choice(ADJACENT_KEYS[low])
    return wrong.upper() if ch.isupper() else wrong


class ReTypeApp:
    def __init__(self, root):
        self.root = root
        self.text = ""
        self.events = None      # generator producing low-level ops
        self.job = None         # pending after id
        self.running = False
        self.paused = False

        self.drift = 1.0        # current speed multiplier (random-walks over time)
        self.net = 0            # net chars committed, for the progress bar

        self._build_ui()
        self._bind_icon()

    # ------------------------------------------------------------------ UI ---
    def _build_ui(self):
        self.root.title("ReType 4.0")
        self.root.geometry("540x680")
        self.root.minsize(440, 600)

        outer = ttk.Frame(self.root, padding=12)
        outer.pack(fill="both", expand=True)

        ttk.Label(outer, text="Text to type",
                  font=("Segoe UI", 10, "bold")).pack(anchor="w")
        self.text_entry = tk.Text(outer, width=52, height=10, wrap="word",
                                  font=("Consolas", 10))
        self.text_entry.pack(fill="both", expand=True, pady=(2, 8))

        # --- Speed (words per minute) --------------------------------------
        speed_row = ttk.Frame(outer)
        speed_row.pack(fill="x")
        ttk.Label(speed_row, text="Typing speed").pack(side="left")
        self.speed_value = ttk.Label(speed_row, text="", width=10, anchor="e")
        self.speed_value.pack(side="right")
        self.wpm = tk.IntVar(value=55)
        ttk.Scale(outer, from_=15, to=140, orient="horizontal", variable=self.wpm,
                  command=self._update_speed_label).pack(fill="x", pady=(0, 8))
        self._update_speed_label()

        # --- Countdown ------------------------------------------------------
        delay_row = ttk.Frame(outer)
        delay_row.pack(fill="x", pady=(0, 8))
        ttk.Label(delay_row, text="Countdown before typing (seconds)").pack(side="left")
        self.start_delay = tk.IntVar(value=3)
        ttk.Spinbox(delay_row, from_=0, to=30, width=5,
                    textvariable=self.start_delay).pack(side="right")

        # --- Mistakes -------------------------------------------------------
        self.errors = tk.BooleanVar(value=True)
        ttk.Checkbutton(outer, text="Make realistic mistakes and correct them",
                        variable=self.errors, command=self._toggle_error_row
                        ).pack(anchor="w")

        self.err_row = ttk.Frame(outer)
        self.err_row.pack(fill="x", pady=(0, 8))
        ttk.Label(self.err_row, text="Mistake frequency").pack(side="left")
        self.err_value = ttk.Label(self.err_row, text="", width=8, anchor="e")
        self.err_value.pack(side="right")
        self.err_rate = tk.IntVar(value=4)  # percent chance per letter
        ttk.Scale(self.err_row, from_=1, to=15, orient="horizontal", length=180,
                  variable=self.err_rate, command=self._update_err_label
                  ).pack(side="right", padx=8)
        self._update_err_label()

        # --- Progress -------------------------------------------------------
        self.progress = ttk.Progressbar(outer, mode="determinate", maximum=100)
        self.progress.pack(fill="x", pady=(2, 4))

        # --- Buttons --------------------------------------------------------
        btn_row = ttk.Frame(outer)
        btn_row.pack(fill="x")
        self.start_btn = ttk.Button(btn_row, text="Start", command=self.start)
        self.start_btn.pack(side="left", expand=True, fill="x", padx=(0, 4))
        self.pause_btn = ttk.Button(btn_row, text="Pause", command=self.toggle_pause,
                                    state="disabled")
        self.pause_btn.pack(side="left", expand=True, fill="x", padx=4)
        self.stop_btn = ttk.Button(btn_row, text="Stop", command=self.stop,
                                   state="disabled")
        self.stop_btn.pack(side="left", expand=True, fill="x", padx=4)
        ttk.Button(btn_row, text="Clear", command=self.clear).pack(
            side="left", expand=True, fill="x", padx=(4, 0))

        # --- Status ---------------------------------------------------------
        self.status = tk.StringVar(value="Ready.")
        ttk.Label(outer, textvariable=self.status, anchor="w",
                  foreground="#555").pack(fill="x", pady=(8, 0))
        ttk.Button(outer, text="Quit", command=self.quit).pack(
            side="bottom", fill="x", pady=(8, 0))

        self.root.protocol("WM_DELETE_WINDOW", self.quit)

    def _bind_icon(self):
        if not sys.platform.startswith("win"):
            return
        here = os.path.dirname(os.path.abspath(__file__))
        for name in ("ReType.ico", os.path.join("..", "ReType.ico")):
            path = os.path.join(here, name)
            if os.path.exists(path):
                try:
                    self.root.iconbitmap(path)
                except tk.TclError:
                    pass
                return

    def _update_speed_label(self, *_):
        self.speed_value.config(text=f"{self.wpm.get()} wpm")

    def _update_err_label(self, *_):
        self.err_value.config(text=f"{self.err_rate.get()}%")

    def _toggle_error_row(self):
        state = "normal" if self.errors.get() else "disabled"
        for child in self.err_row.winfo_children():
            try:
                child.config(state=state)
            except tk.TclError:
                pass

    # ------------------------------------------------------------- control ---
    def start(self):
        if self.running:
            return
        self.text = self.text_entry.get("1.0", tk.END).rstrip("\n")
        if not self.text:
            messagebox.showinfo("ReType", "There's no text to type.")
            return

        self.events = self._build_events()
        self.drift = 1.0
        self.net = 0
        self.running = True
        self.paused = False
        self.progress["value"] = 0
        self.start_btn.config(state="disabled")
        self.pause_btn.config(state="normal", text="Pause")
        self.stop_btn.config(state="normal")

        self._countdown(max(0, self.start_delay.get()))

    def _countdown(self, remaining):
        if not self.running:
            return
        if remaining > 0:
            self.status.set(f"Click into your target window... typing in {remaining}")
            self.job = self.root.after(1000, self._countdown, remaining - 1)
        else:
            self.status.set("Typing...  (mouse to a screen corner aborts)")
            self._tick()

    def toggle_pause(self):
        if not self.running:
            return
        self.paused = not self.paused
        if self.paused:
            self._cancel_job()
            self.pause_btn.config(text="Resume")
            self.status.set("Paused.")
        else:
            self.pause_btn.config(text="Pause")
            self.status.set("Typing...  (mouse to a screen corner aborts)")
            self._tick()

    def stop(self):
        self._cancel_job()
        self.running = False
        self.paused = False
        self.events = None
        self.start_btn.config(state="normal")
        self.pause_btn.config(state="disabled", text="Pause")
        self.stop_btn.config(state="disabled")
        self.status.set("Stopped.")

    def clear(self):
        self.text_entry.delete("1.0", tk.END)

    def quit(self):
        self._cancel_job()
        self.root.destroy()

    def _cancel_job(self):
        if self.job is not None:
            self.root.after_cancel(self.job)
            self.job = None

    # -------------------------------------------------------------- engine ---
    def _tick(self):
        """Execute one low-level op, then schedule the next. Single chain."""
        if not self.running or self.paused:
            return
        try:
            op, value, delay = next(self.events)
        except StopIteration:
            self._finish()
            return

        try:
            if op == "type":
                pyautogui.write(value)
                self.net += 1
            elif op == "back":
                pyautogui.press("backspace")
                self.net -= 1
        except pyautogui.FailSafeException:
            self.status.set("Aborted by failsafe (mouse hit a corner).")
            self.stop()
            return

        if self.text:
            pct = max(0, min(100, self.net * 100 // len(self.text)))
            self.progress["value"] = pct

        self.job = self.root.after(max(1, int(delay)), self._tick)

    def _char_delay(self, ch):
        """Milliseconds before the next keystroke, given the WPM target + drift."""
        # Random-walk the drift so speed ebbs and flows like a real typist.
        self.drift += random.gauss(0, 0.04)
        self.drift = max(0.65, min(1.5, self.drift * 0.98 + 0.02))  # mean-revert to 1

        cps = max(1.0, self.wpm.get() * 5 / 60.0)   # chars per second
        base = 1000.0 / cps
        delay = random.gauss(base, base * 0.30) * self.drift

        if ch == " ":
            delay *= 1.4
        elif ch in SENTENCE_END:
            delay *= 2.4
        elif ch in PUNCTUATION:
            delay *= 1.8
        elif not ch.isalpha():
            delay *= 1.5                              # digits/symbols: less muscle memory

        return max(8, int(delay))

    def _choose_error_kind(self, text, i):
        kinds = ["adjacent", "double", "case", "delayed"]
        if i + 1 < len(text) and text[i + 1].isalpha():
            kinds.append("transpose")
        return random.choice(kinds)

    def _build_events(self):
        """Yield (op, value, delay_ms) low-level ops for the whole text."""
        text = self.text
        i, n = 0, len(text)

        while i < n:
            ch = text[i]

            # Thinking pause at the start of a word, now and then.
            if ch != " " and (i == 0 or text[i - 1] == " ") and random.random() < 0.03:
                yield ("pause", None, random.randint(350, 1400))

            rate = self.err_rate.get() / 100.0
            do_error = self.errors.get() and ch.isalpha() and random.random() < rate

            if do_error:
                kind = self._choose_error_kind(text, i)

                if kind == "adjacent":
                    wrong = adjacent(ch)
                    if wrong:
                        yield ("type", wrong, self._char_delay(wrong))
                        yield ("pause", None, random.randint(120, 400))
                        yield ("back", None, random.randint(90, 220))
                    # fall through and type the right char

                elif kind == "case":
                    wrong = ch.upper() if ch.islower() else ch.lower()
                    yield ("type", wrong, self._char_delay(wrong))
                    yield ("pause", None, random.randint(120, 350))
                    yield ("back", None, random.randint(90, 200))
                    # fall through and type the right char

                elif kind == "double":
                    yield ("type", ch, self._char_delay(ch))
                    yield ("type", ch, int(self._char_delay(ch) * 0.55))
                    yield ("pause", None, random.randint(150, 450))
                    yield ("back", None, random.randint(90, 220))
                    i += 1
                    continue

                elif kind == "transpose":
                    a, b = text[i], text[i + 1]
                    yield ("type", b, self._char_delay(b))
                    yield ("type", a, int(self._char_delay(a) * 0.7))
                    yield ("pause", None, random.randint(160, 480))
                    yield ("back", None, random.randint(90, 200))
                    yield ("back", None, random.randint(80, 160))
                    yield ("type", a, self._char_delay(a))
                    yield ("type", b, self._char_delay(b))
                    i += 2
                    continue

                elif kind == "delayed":
                    wrong = adjacent(ch)
                    if wrong:
                        yield ("type", wrong, self._char_delay(wrong))
                        extra = text[i + 1:i + 1 + random.randint(1, 3)]
                        for c in extra:
                            yield ("type", c, self._char_delay(c))
                        yield ("pause", None, random.randint(250, 700))  # notice it
                        for _ in range(len(extra) + 1):
                            yield ("back", None, random.randint(70, 160))
                        yield ("type", ch, self._char_delay(ch))
                        for c in extra:
                            yield ("type", c, self._char_delay(c))
                        i += 1 + len(extra)
                        continue
                    # adjacent() returned None: fall through to a clean type

            yield ("type", ch, self._char_delay(ch))
            i += 1

    def _finish(self):
        self.running = False
        self.paused = False
        self.job = None
        self.events = None
        self.progress["value"] = 100
        self.start_btn.config(state="normal")
        self.pause_btn.config(state="disabled", text="Pause")
        self.stop_btn.config(state="disabled")
        self.status.set(f"Done - typed {len(self.text)} characters.")


def main():
    root = tk.Tk()
    ReTypeApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
