"""
ReType 3.0 - a human-like automated typing assistant.

You paste text, pick a speed, hit Start, and after a short countdown ReType types
the text wherever your cursor is focused - one character at a time, with optional
human imperfections (variable rhythm, thinking pauses, and realistic typos that
get corrected).

Everything is driven by Tk's `after` scheduler rather than time.sleep(), so the
window stays responsive and the Stop button actually works mid-type.

Failsafe: slam the mouse cursor into any screen corner to abort instantly
(pyautogui's built-in FAILSAFE).
"""

import os
import sys
import random
import tkinter as tk
from tkinter import ttk, messagebox

import pyautogui

# Typing into another window can run away from you. Keep the corner failsafe on
# and drop pyautogui's own per-call pause to zero - we do all our own timing.
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0

# Keys physically adjacent on a QWERTY keyboard. Used to generate believable
# typos: a real person's slip is usually a neighbouring key, not a random one.
ADJACENT_KEYS = {
    'a': 'qwsz',   'b': 'vghn',  'c': 'xdfv',  'd': 'serfcx', 'e': 'wsdr',
    'f': 'drtgvc', 'g': 'ftyhbv', 'h': 'gyujnb', 'i': 'ujko', 'j': 'huikmn',
    'k': 'jiolm',  'l': 'kop',   'm': 'njk',    'n': 'bhjm',  'o': 'iklp',
    'p': 'ol',     'q': 'wa',     'r': 'edft',   's': 'awedxz', 't': 'rfgy',
    'u': 'yhji',   'v': 'cfgb',   'w': 'qase',   'x': 'zsdc',  'y': 'tghu',
    'z': 'asx',
}


class ReTypeApp:
    def __init__(self, root):
        self.root = root
        self.text = ""          # snapshot of text being typed
        self.index = 0          # position of the next character to type
        self.job = None         # pending root.after id, so we can cancel it
        self.running = False

        self._build_ui()
        self._bind_icon()

    # ------------------------------------------------------------------ UI ---
    def _build_ui(self):
        self.root.title("ReType 3.0")
        self.root.geometry("520x600")
        self.root.minsize(420, 520)

        outer = ttk.Frame(self.root, padding=12)
        outer.pack(fill="both", expand=True)

        ttk.Label(outer, text="Text to type", font=("Segoe UI", 10, "bold")).pack(anchor="w")

        self.text_entry = tk.Text(outer, width=48, height=10, wrap="word",
                                  font=("Consolas", 10))
        self.text_entry.pack(fill="both", expand=True, pady=(2, 8))

        # --- Speed ----------------------------------------------------------
        speed_row = ttk.Frame(outer)
        speed_row.pack(fill="x")
        ttk.Label(speed_row, text="Typing speed").pack(side="left")
        self.speed_value = ttk.Label(speed_row, text="", width=14, anchor="e")
        self.speed_value.pack(side="right")

        # Slider is in delay-milliseconds-per-character: left = slow, right = fast.
        self.speed = tk.IntVar(value=60)
        self.speed_scale = ttk.Scale(outer, from_=250, to=2, orient="horizontal",
                                     variable=self.speed, command=self._update_speed_label)
        self.speed_scale.pack(fill="x", pady=(0, 8))
        self._update_speed_label()

        # --- Start delay ----------------------------------------------------
        delay_row = ttk.Frame(outer)
        delay_row.pack(fill="x", pady=(0, 8))
        ttk.Label(delay_row, text="Countdown before typing (seconds)").pack(side="left")
        self.start_delay = tk.IntVar(value=3)
        ttk.Spinbox(delay_row, from_=0, to=30, width=5,
                    textvariable=self.start_delay).pack(side="right")

        # --- Toggles --------------------------------------------------------
        self.humanize = tk.BooleanVar(value=True)
        ttk.Checkbutton(outer, text="Humanize rhythm (variable speed + thinking pauses)",
                        variable=self.humanize).pack(anchor="w")

        self.errors = tk.BooleanVar(value=False)
        ttk.Checkbutton(outer, text="Make occasional typos and correct them",
                        variable=self.errors).pack(anchor="w", pady=(0, 8))

        # --- Buttons --------------------------------------------------------
        btn_row = ttk.Frame(outer)
        btn_row.pack(fill="x", pady=(4, 0))
        self.start_btn = ttk.Button(btn_row, text="Start", command=self.start)
        self.start_btn.pack(side="left", expand=True, fill="x", padx=(0, 4))
        self.stop_btn = ttk.Button(btn_row, text="Stop", command=self.stop, state="disabled")
        self.stop_btn.pack(side="left", expand=True, fill="x", padx=4)
        ttk.Button(btn_row, text="Clear", command=self.clear).pack(side="left",
                                                                    expand=True, fill="x", padx=(4, 0))

        # --- Status ---------------------------------------------------------
        self.status = tk.StringVar(value="Ready.")
        ttk.Label(outer, textvariable=self.status, anchor="w",
                  foreground="#555").pack(fill="x", pady=(8, 0))

        ttk.Button(outer, text="Quit", command=self.quit).pack(side="bottom",
                                                               fill="x", pady=(8, 0))

        self.root.protocol("WM_DELETE_WINDOW", self.quit)

    def _bind_icon(self):
        """Load the window icon if it sits next to the script. Never fatal."""
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
        ms = self.speed.get()
        # Rough words-per-minute, assuming ~5 chars/word: chars/sec = 1000/ms.
        wpm = round((1000 / ms) / 5 * 60)
        self.speed_value.config(text=f"{ms} ms  (~{wpm} wpm)")

    # ------------------------------------------------------------- control ---
    def start(self):
        if self.running:
            return
        self.text = self.text_entry.get("1.0", tk.END).rstrip("\n")
        if not self.text:
            messagebox.showinfo("ReType", "There's no text to type.")
            return

        self.index = 0
        self.running = True
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")

        delay = max(0, self.start_delay.get())
        self._countdown(delay)

    def _countdown(self, remaining):
        if not self.running:
            return
        if remaining > 0:
            self.status.set(f"Click into your target window... typing in {remaining}")
            self.job = self.root.after(1000, self._countdown, remaining - 1)
        else:
            self.status.set("Typing... (move mouse to a screen corner to abort)")
            self._type_next()

    def stop(self):
        self._cancel_job()
        self.running = False
        self.start_btn.config(state="normal")
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

    # -------------------------------------------------------------- typing ---
    def _type_next(self):
        """Type exactly one character, then schedule the next. Single chain."""
        if not self.running:
            return

        if self.index >= len(self.text):
            self._finish()
            return

        char = self.text[self.index]

        # Occasionally fumble a letter and correct it, the way a person would.
        if self.errors.get() and char.lower() in ADJACENT_KEYS and random.random() < 0.04:
            self._make_typo(char)

        try:
            pyautogui.write(char)
        except pyautogui.FailSafeException:
            self.status.set("Aborted by failsafe (mouse hit a corner).")
            self.stop()
            return

        self.index += 1
        self.job = self.root.after(self._next_delay(char), self._type_next)

    def _make_typo(self, intended):
        """Type a wrong neighbouring key, pause, then backspace it out."""
        wrong = random.choice(ADJACENT_KEYS[intended.lower()])
        if intended.isupper():
            wrong = wrong.upper()
        try:
            pyautogui.write(wrong)
            # Brief "oops" beat handled by the scheduler-free press calls below;
            # these are short and bounded so they won't visibly freeze the UI.
            pyautogui.press("backspace")
        except pyautogui.FailSafeException:
            self.status.set("Aborted by failsafe (mouse hit a corner).")
            self.stop()

    def _next_delay(self, char):
        """Milliseconds to wait before the next character."""
        base = self.speed.get()
        if not self.humanize.get():
            return base

        # Gaussian jitter around the base delay so the rhythm feels organic.
        delay = random.gauss(base, base * 0.35)

        # A space is a natural micro-rest; punctuation a slightly longer one.
        if char == " ":
            delay *= 1.4
        elif char in ".,!?;:\n":
            delay *= 2.2

        # Rare longer "thinking" pause.
        if random.random() < 0.02:
            delay += random.randint(400, 1200)

        return max(2, int(delay))

    def _finish(self):
        self.running = False
        self.job = None
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        self.status.set(f"Done - typed {len(self.text)} characters.")


def main():
    root = tk.Tk()
    ReTypeApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
