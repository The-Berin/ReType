"""
ReType 6.0 - a realistic human-typing simulator.

Package layout:
    layout.py     QWERTY keyboard physics (finger/hand/row per key, digraph cost)
    words.py      word familiarity + whitespace-preserving tokeniser
    profiles.py   typing personas (speed/error/burst parameter sets)
    humanizer.py  the brain: text -> stream of timed low-level ops
    engine.py     the runner: drives ops via Tk's after scheduler, non-blocking
    hotkey.py     global-hotkey watcher (start/stop a run from any window)
    ui.py         the Tkinter app (controls, personas, live speed cardiogram)
"""

__version__ = "6.0"
