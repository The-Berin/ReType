"""
The ReType 5.0 window - native Windows look (default ttk theme).

Pick a typist persona, drop in text, and either:
  * Start   - types into whatever window you click into next (after a countdown)
  * Demo    - types into the in-app preview so you can watch the human rhythm,
              typos and corrections happen without leaving the app

A live "cardiogram" strip shows instantaneous speed so you can see the rhythm
breathe. Pause / Stop work mid-type; the mouse-to-a-corner failsafe aborts a
real run instantly.
"""

import os
import sys
import collections
import dataclasses
import tkinter as tk
from tkinter import ttk, messagebox

from . import profiles
from .humanizer import HumanTyper
from .engine import TypeEngine, KeyboardSink, TextWidgetSink

ACCENT = "#0067C0"        # Windows accent blue, for the cardiogram trace


class App:
    def __init__(self, root):
        self.root = root
        self.cardio = collections.deque(maxlen=140)
        self.mode = None            # 'real' or 'demo' while running
        self._cd_job = None         # pending countdown after() id
        self._pending = None        # (ops, total) waiting out the countdown

        self.engine = TypeEngine(
            root,
            on_op=self._on_op,
            on_progress=self._on_progress,
            on_done=self._on_done,
            on_abort=self._on_abort,
        )

        self._build_ui()
        self._bind_icon()
        self._on_persona()

    # ------------------------------------------------------------------ UI ---
    def _build_ui(self):
        self.root.title("ReType 5.0")
        self.root.geometry("600x820")
        self.root.minsize(520, 720)

        outer = ttk.Frame(self.root, padding=10)
        outer.pack(fill="both", expand=True)

        ttk.Label(outer, text="Text to type",
                  font=("Segoe UI", 10, "bold")).pack(anchor="w")
        self.text = tk.Text(outer, height=7, wrap="word", font=("Consolas", 10),
                            undo=True)
        self.text.pack(fill="both", expand=True, pady=(2, 8))

        # --- Typist persona -------------------------------------------------
        prow = ttk.Frame(outer)
        prow.pack(fill="x")
        ttk.Label(prow, text="Typist").pack(side="left")
        self.persona = tk.StringVar(value=profiles.DEFAULT_PROFILE)
        self.persona_box = ttk.Combobox(
            prow, textvariable=self.persona, state="readonly",
            values=[p.name for p in profiles.PROFILES], width=24)
        self.persona_box.pack(side="left", padx=8)
        self.persona_box.bind("<<ComboboxSelected>>", lambda e: self._on_persona())
        self.blurb = ttk.Label(outer, text="", foreground="#555",
                               font=("Segoe UI", 8, "italic"))
        self.blurb.pack(anchor="w", pady=(2, 6))

        # --- Speed trim + countdown ----------------------------------------
        srow = ttk.Frame(outer)
        srow.pack(fill="x")
        ttk.Label(srow, text="Overall speed").pack(side="left")
        self.trim = tk.DoubleVar(value=1.0)
        ttk.Scale(srow, from_=0.5, to=2.0, orient="horizontal", variable=self.trim,
                  command=self._on_trim, length=200).pack(side="left", padx=8)
        self.trim_lbl = ttk.Label(srow, text="x1.0", width=6)
        self.trim_lbl.pack(side="left")
        ttk.Label(srow, text="Countdown").pack(side="left", padx=(12, 2))
        self.countdown = tk.IntVar(value=3)
        ttk.Spinbox(srow, from_=0, to=30, width=4,
                    textvariable=self.countdown).pack(side="left")

        # --- Max realism toggle --------------------------------------------
        self.leave = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            outer, variable=self.leave,
            text="Leave some mistakes in (max realism - final text won't be exact)"
        ).pack(anchor="w", pady=(6, 6))

        # --- Live cardiogram ------------------------------------------------
        cardio_frame = ttk.LabelFrame(outer, text="Live speed", padding=6)
        cardio_frame.pack(fill="x", pady=(0, 6))
        self.canvas = tk.Canvas(cardio_frame, height=70, highlightthickness=1,
                                highlightbackground="#cccccc", background="white")
        self.canvas.pack(fill="x", side="left", expand=True)
        self.wpm_lbl = ttk.Label(cardio_frame, text="0\nwpm", width=6,
                                 anchor="center", font=("Segoe UI", 11, "bold"))
        self.wpm_lbl.pack(side="left", padx=(8, 0))
        self.canvas.bind("<Configure>", lambda e: self._draw_cardio())

        # --- Progress -------------------------------------------------------
        self.progress = ttk.Progressbar(outer, maximum=100)
        self.progress.pack(fill="x", pady=(0, 6))

        # --- Buttons --------------------------------------------------------
        brow = ttk.Frame(outer)
        brow.pack(fill="x")
        self.start_btn = ttk.Button(brow, text="Start", command=self.start_real)
        self.start_btn.pack(side="left", expand=True, fill="x", padx=(0, 3))
        self.demo_btn = ttk.Button(brow, text="Demo", command=self.start_demo)
        self.demo_btn.pack(side="left", expand=True, fill="x", padx=3)
        self.pause_btn = ttk.Button(brow, text="Pause", command=self.toggle_pause,
                                    state="disabled")
        self.pause_btn.pack(side="left", expand=True, fill="x", padx=3)
        self.stop_btn = ttk.Button(brow, text="Stop", command=self.stop,
                                   state="disabled")
        self.stop_btn.pack(side="left", expand=True, fill="x", padx=3)
        ttk.Button(brow, text="Clear", command=self.clear_text).pack(
            side="left", expand=True, fill="x", padx=(3, 0))

        # --- Demo preview ---------------------------------------------------
        demo_frame = ttk.LabelFrame(outer, text="Demo preview (watch it type here)",
                                    padding=6)
        demo_frame.pack(fill="both", expand=True, pady=(8, 4))
        self.preview = tk.Text(demo_frame, height=5, wrap="word",
                               font=("Consolas", 10), background="#f7f7f7")
        self.preview.pack(fill="both", expand=True)

        # --- Status + quit --------------------------------------------------
        self.status = tk.StringVar(value="Ready.")
        ttk.Label(outer, textvariable=self.status, anchor="w",
                  foreground="#555").pack(fill="x", pady=(6, 0))
        ttk.Button(outer, text="Quit", command=self.quit).pack(
            side="bottom", fill="x", pady=(6, 0))

        self.root.protocol("WM_DELETE_WINDOW", self.quit)

    def _bind_icon(self):
        if not sys.platform.startswith("win"):
            return
        base = os.path.dirname(os.path.abspath(__file__))
        for path in (os.path.join(base, "ReType.ico"),
                     os.path.join(base, "..", "ReType.ico")):
            if os.path.exists(path):
                try:
                    self.root.iconbitmap(path)
                except tk.TclError:
                    pass
                return

    # -------------------------------------------------------------- helpers ---
    def _on_persona(self):
        p = profiles.get(self.persona.get())
        self.blurb.config(text=f"{p.blurb}   ({p.wpm_low:.0f}-{p.wpm_high:.0f} wpm)")

    def _on_trim(self, *_):
        self.trim_lbl.config(text=f"x{self.trim.get():.1f}")

    def _active_profile(self):
        p = profiles.get(self.persona.get())
        t = self.trim.get()
        if abs(t - 1.0) > 0.01:
            p = dataclasses.replace(p, wpm_low=p.wpm_low * t, wpm_high=p.wpm_high * t)
        return p

    def _make_ops(self):
        content = self.text.get("1.0", "end").rstrip("\n")
        if not content:
            messagebox.showinfo("ReType", "There's no text to type.")
            return None, 0
        typer = HumanTyper(self._active_profile(), make_errors=True,
                           leave_uncorrected=self.leave.get())
        return typer.generate(content), len(content)

    # -------------------------------------------------------------- control ---
    def _busy(self):
        return self.engine.running or self.mode is not None or self._cd_job is not None

    def start_real(self):
        if self._busy():
            return
        ops, total = self._make_ops()
        if ops is None:
            return
        self.mode = "real"
        self._set_running(True)
        self.pause_btn.config(state="disabled")   # nothing to pause during the countdown
        self.cardio.clear()
        self._draw_cardio()
        self._pending = (ops, total)
        self._countdown(max(0, self.countdown.get()))

    def _countdown(self, remaining):
        if self.mode != "real":
            return
        if remaining > 0:
            self.status.set(f"Click into your target window... typing in {remaining}")
            self._cd_job = self.root.after(1000, self._countdown, remaining - 1)
        else:
            self._cd_job = None
            self.pause_btn.config(state="normal")
            self.status.set("Typing...  (move mouse to a screen corner to abort)")
            ops, total = self._pending
            self._pending = None
            self.engine.start(ops, total, KeyboardSink(self.root))

    def start_demo(self):
        if self._busy():
            return
        ops, total = self._make_ops()
        if ops is None:
            return
        self.mode = "demo"
        self._set_running(True)
        self.cardio.clear()
        self._draw_cardio()
        self.preview.delete("1.0", "end")
        self.preview.focus_set()              # show the caret so you can watch it move
        self.status.set("Demo: watch the typing happen below.")
        self.engine.start(ops, total, TextWidgetSink(self.preview))

    def toggle_pause(self):
        if not self.engine.running:
            return
        if self.engine.paused:
            self.engine.resume()
            self.pause_btn.config(text="Pause")
            self.status.set("Typing...")
        else:
            self.engine.pause()
            self.pause_btn.config(text="Resume")
            self.status.set("Paused.")

    def _cancel_countdown(self):
        if self._cd_job is not None:
            self.root.after_cancel(self._cd_job)
            self._cd_job = None
        self._pending = None

    def stop(self):
        self._cancel_countdown()
        self.engine.stop()
        self.mode = None
        self._set_running(False)
        self.status.set("Stopped.")

    def clear_text(self):
        self.text.delete("1.0", "end")

    def quit(self):
        self._cancel_countdown()
        self.engine.stop(force=True)
        self.root.destroy()

    def _set_running(self, running):
        state = "disabled" if running else "normal"
        self.start_btn.config(state=state)
        self.demo_btn.config(state=state)
        self.pause_btn.config(state="normal" if running else "disabled", text="Pause")
        self.stop_btn.config(state="normal" if running else "disabled")

    # ------------------------------------------------------------- callbacks ---
    def _on_op(self, kind, value, delay):
        if kind in ("type", "back"):
            wpm = min(220, 12000.0 / max(1, delay))
            self.cardio.append(wpm)
            self._draw_cardio()
            self.wpm_lbl.config(text=f"{wpm:.0f}\nwpm")

    def _on_progress(self, net, total):
        self.progress["value"] = max(0, min(100, net * 100 // total))

    def _on_done(self):
        self.mode = None
        self._set_running(False)
        self.progress["value"] = 100
        self.status.set("Done.")

    def _on_abort(self, reason):
        self.mode = None
        self._set_running(False)
        self.status.set("Aborted by failsafe (mouse hit a corner).")

    # ----------------------------------------------------------- cardiogram ---
    def _draw_cardio(self):
        c = self.canvas
        c.delete("all")
        w = c.winfo_width() or 400
        h = c.winfo_height() or 70
        # baseline grid
        for frac in (0.25, 0.5, 0.75):
            y = h * frac
            c.create_line(0, y, w, y, fill="#eeeeee")
        if len(self.cardio) < 2:
            return
        top = max(80.0, max(self.cardio) * 1.1)
        n = len(self.cardio)
        step = w / max(1, self.cardio.maxlen - 1)
        pts = []
        start = self.cardio.maxlen - n
        for i, v in enumerate(self.cardio):
            x = (start + i) * step
            y = h - (v / top) * (h - 6) - 3
            pts.extend((x, y))
        if len(pts) >= 4:
            c.create_line(*pts, fill=ACCENT, width=2, smooth=True)


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
