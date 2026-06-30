"""
ReType 6.0 launcher.

A realistic human-typing simulator. The real code lives in the `retype` package
next to this file; this is just the double-clickable entry point.

    python "ReType Ver 6.0.py"      or      python -m retype

When started with python.exe (which carries a console window), it relaunches
itself with the windowless pythonw.exe so no black cmd window hangs around.
"""

import os
import sys

# Make sure the package next to this script is importable when double-clicked.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _relaunch_without_console():
    """If we're under python.exe (console), re-run under pythonw.exe and exit."""
    if getattr(sys, "frozen", False):
        return                                   # built exe: no console anyway
    exe = (sys.executable or "")
    if not exe.lower().endswith("python.exe"):
        return                                   # already pythonw, or embedded
    pyw = os.path.join(os.path.dirname(exe), "pythonw.exe")
    if not os.path.exists(pyw):
        return
    import subprocess
    CREATE_NO_WINDOW = 0x08000000
    subprocess.Popen([pyw, os.path.abspath(__file__), *sys.argv[1:]],
                     creationflags=CREATE_NO_WINDOW, close_fds=True)
    sys.exit(0)


if sys.platform.startswith("win"):
    _relaunch_without_console()

from retype.ui import main

if __name__ == "__main__":
    main()
