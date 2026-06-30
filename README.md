# ReType

**A realistic human-typing simulator.**

You drop in some text, pick a *typist*, and hit **Start**. After a short
countdown, ReType types the text out wherever your cursor is focused — modelling
the way a real person types: variable rhythm, word bursts, thinking pauses,
fatigue, and mistakes that get noticed and corrected.

It's handy for repetitive text entry, demos, filling forms that don't accept
paste, or anywhere you want typing that looks like a person did it instead of a
clipboard dump.

---

## What makes the typing *realistic* (Ver 5.0)

The 5.0 engine is grounded in real keystroke-dynamics research (the Aalto 136M
keystroke dataset, Gentner digraph timings, Ostry inter-key models):

- **Per-keystroke physics** — every letter-pair is timed by the fingers it uses:
  alternating hands (`th`, `he`) fly, same-finger pairs (`ed`, `fg`) drag. Speed
  genuinely varies key to key, not just word to word.
- **People type in words** — a familiar word fires as a quick burst, then a
  planning pause before the next; rare or long words cost more up front and
  hesitate mid-word.
- **Speed that swings a lot** — the working WPM random-walks inside the typist's
  range, with fast flurries and heavy-tailed "thinking" stalls.
- **A stamina arc** — energy decays as it types, so gaps widen, pauses lengthen,
  and mistakes creep up over a long passage (with a cold-start warm-up).
- **Seven human error types** — adjacent-key slips, transpositions (`teh`→`the`),
  doubled letters, dropped letters, case slips, *delayed* corrections (types a
  few more characters before noticing), and the original hand-picked fat-finger
  combos. Each is either corrected — or, in max-realism mode, left in.

### Typists

Seven personas, each a different real person:

| Typist | Feel |
|--------|------|
| Hunt & Peck Hank | 68, two index fingers, eyes on the keys (~18 wpm) |
| Two-Finger Tom | fast peck-typist who never learned home row (~36 wpm) |
| Thumbs Tiffany | phone texter, leaves readable typos (~45 wpm) |
| Graveyard Greg | exhausted night-shift, micro-sleeps mid-word (~48 wpm) |
| Cubicle Carol | steady home-row office touch typist (~64 wpm) |
| Caffeine Cody | machine-gun bursts then dead stops (~107 wpm) |
| Record-Holder Reyna | competition speed-typist, near-flawless (~140 wpm) |

### Extras

- **Live speed cardiogram** — a heartbeat strip of instantaneous WPM so you can
  *see* the rhythm breathe.
- **Demo mode** — watch the whole performance (typos, corrections, pauses) play
  out inside the app, no second window needed.
- **Pause / Resume / Stop** instant mid-type, **live progress bar**, and the
  **corner failsafe** — slam your mouse into a screen corner to abort a real run.

---

## Install

Requires **Python 3.8+**.

```bash
pip install -r requirements.txt
```

## Run

```bash
python "Ver 5.0/ReType Ver 5.0.py"      # or:  python -m retype   (from Ver 5.0/)
```

1. Drop your text into the box.
2. Pick a **Typist** and an overall speed.
3. Click **Demo** to watch it type inside the app, or **Start** and click into
   the window you want the text typed into before the countdown ends.

To abort at any time click **Stop**, or (for a real run) move your mouse to a
screen corner.

---

## Versions

The repo keeps the project's history:

| Version | Notes |
|---------|-------|
| `Ver 0.0` | First prototype — single-line entry, blocking `time.sleep`, types all at once. |
| `Ver 1.0` | Multi-line text box, character-by-character typing, first pass at random pauses/typos. |
| `Ver 2.0` | Speed slider and error toggle added; timing logic still had a scheduling race. |
| `Ver 3.0` | Rewritten as a single event-driven app: working Stop button, countdown, gaussian timing, QWERTY-adjacent typos, corner failsafe, and no hardcoded paths. |
| `Ver 4.0` | Full realistic typing engine — WPM-based drifting speed, five human error patterns with delayed corrections, Pause/Resume/Stop, live progress bar. |
| `Ver 5.0` | **Current.** Research-grounded rewrite into the `retype` package: per-keystroke digraph timing, word bursts, seven typist personas, a fatigue/stamina arc, seven error types, a live speed cardiogram, and an in-app Demo mode. |

## Notes

- ReType drives your real keyboard via OS-level injection, so the active window
  genuinely receives the keystrokes — make sure the right window is focused
  before the countdown runs out.
- **Proofreading typists (Baron) and real windows:** the proofread pass steers
  the cursor with arrow keys, which assumes one arrow press moves one character
  and that nothing else disturbs the caret. That holds in plain text boxes and
  most forms. In editors that auto-indent, autocorrect, or auto-close brackets
  (IDEs, Google Docs, Word), the cursor can drift — use **Demo** mode (always
  exact) or a plain field for those, and don't click into the target window
  while a run is in progress.
- An optional `ReType.ico` placed next to the script (or in the repo root) is used
  as the window icon. It's entirely optional; the app runs fine without it.
