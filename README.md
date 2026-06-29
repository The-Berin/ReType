# ReType

**A human-like automated typing assistant.**

You paste in some text, pick a speed, and hit **Start**. After a short countdown,
ReType types the text out wherever your cursor is focused — one character at a
time, with optional human imperfections like a variable rhythm, thinking pauses,
and realistic typos that get corrected.

It's handy for repetitive text entry, demos, filling forms that don't accept
paste, or anywhere you want typing that looks like a person did it instead of a
clipboard dump.

---

## Features

- **Types into any focused window** — documents, chat boxes, forms, terminals.
- **Adjustable speed** shown in both milliseconds-per-character and approximate WPM.
- **Countdown** before typing so you have time to click into your target window.
- **Humanize rhythm** — gaussian timing jitter, longer rests after spaces and
  punctuation, and the occasional "thinking" pause.
- **Realistic mistakes** — five human error patterns, each corrected the way a
  person would: adjacent-key slips, transpositions (`teh` → `the`), doubled
  letters, case slips, and *delayed* corrections where it types a few more
  characters before noticing and backing up to fix the error.
- **WPM-based speed that drifts** — the rhythm bursts and tires over time instead
  of sitting at a robotic constant.
- **Pause / Resume / Stop** that work instantly mid-type (the engine is a single
  event-driven op-stream, so the window never freezes).
- **Live progress bar** and **corner failsafe** — slam your mouse into any screen
  corner to abort instantly.

---

## Install

Requires **Python 3.8+**.

```bash
pip install -r requirements.txt
```

## Run

```bash
python "Ver 4.0/ReType Ver 4.0.py"
```

1. Paste or type your text into the box.
2. Set the typing speed and countdown.
3. Optionally tick **Humanize rhythm** and/or **typos**.
4. Click **Start**, then click into the window you want the text typed into
   before the countdown ends.

To abort at any time, click **Stop** or move your mouse to a screen corner.

---

## Versions

The repo keeps the project's history:

| Version | Notes |
|---------|-------|
| `Ver 0.0` | First prototype — single-line entry, blocking `time.sleep`, types all at once. |
| `Ver 1.0` | Multi-line text box, character-by-character typing, first pass at random pauses/typos. |
| `Ver 2.0` | Speed slider and error toggle added; timing logic still had a scheduling race. |
| `Ver 3.0` | Rewritten as a single event-driven app: working Stop button, countdown, gaussian timing, QWERTY-adjacent typos, corner failsafe, and no hardcoded paths. |
| `Ver 4.0` | **Current.** Full realistic typing engine — WPM-based drifting speed, five human error patterns with delayed corrections, Pause/Resume/Stop, live progress bar. |

## Notes

- ReType drives your real keyboard via [PyAutoGUI](https://pyautogui.readthedocs.io/),
  so the active window genuinely receives the keystrokes — make sure the right
  window is focused before the countdown runs out.
- An optional `ReType.ico` placed next to the script (or in the repo root) is used
  as the window icon. It's entirely optional; the app runs fine without it.
