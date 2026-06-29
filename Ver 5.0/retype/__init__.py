"""
ReType 5.0 - a realistic human-typing simulator.

Package layout:
    layout.py     QWERTY keyboard physics (finger/hand/row per key, digraph cost)
    words.py      word familiarity + whitespace-preserving tokeniser
    profiles.py   typing personas (speed/error/burst parameter sets)
    humanizer.py  the brain: text -> stream of timed low-level ops
    engine.py     the runner: drives ops via Tk's after scheduler, non-blocking
    ui.py         the Tkinter app (controls, personas, live speed cardiogram)
"""

__version__ = "5.0"
