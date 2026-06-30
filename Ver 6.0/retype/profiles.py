"""
Typing personas.

Each persona is a small bundle of knobs over the humanizer's behaviour - top
speed, how error-prone, how bursty, how long the between-word pauses run, and
how much of its own mess it bothers to clean up. The numbers come from the
research pass (grounded in the Aalto 136M-keystroke dataset and digraph-timing
literature) and are tuned to feel like seven genuinely different people.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Profile:
    name: str
    blurb: str
    wpm_low: float            # slow end of this person's range
    wpm_high: float           # fast end
    error_rate: float         # base per-letter chance of a slip (0..~0.15)
    burstiness: float         # 0..1: how much speed swings in flurries/stalls
    pause_scale: float        # multiplier on between-word / boundary pauses
    corrects_errors: float    # 0..1: fraction of its own typos it fixes
    proofreads: bool = False  # type sloppy, then go back and proofread (cursor nav)

    @property
    def wpm_mid(self):
        return (self.wpm_low + self.wpm_high) / 2.0


# Ordered slowest-to-fastest so the gallery reads like a spectrum.
PROFILES = [
    Profile("Hunt & Peck Hank",
            "68, retired plumber, two index fingers, eyes glued to the keys",
            wpm_low=12, wpm_high=24, error_rate=0.040, burstiness=0.15,
            pause_scale=2.60, corrects_errors=0.85),
    Profile("Two-Finger Tom",
            "52, middle manager, fast peck-typist who never learned home row",
            wpm_low=28, wpm_high=44, error_rate=0.030, burstiness=0.40,
            pause_scale=1.60, corrects_errors=0.75),
    Profile("Thumbs Tiffany",
            "19, phone texter, autocorrect does half the work, leaves readable typos",
            wpm_low=35, wpm_high=55, error_rate=0.070, burstiness=0.60,
            pause_scale=1.30, corrects_errors=0.35),
    Profile("Graveyard Greg",
            "33, night-shift data entry at 3am, decent but exhausted, micro-sleeps mid-word",
            wpm_low=38, wpm_high=58, error_rate=0.055, burstiness=0.70,
            pause_scale=1.90, corrects_errors=0.45),
    Profile("Cubicle Carol",
            "41, accounts payable, solid home-row touch typist, steady all-day rhythm",
            wpm_low=55, wpm_high=72, error_rate=0.018, burstiness=0.30,
            pause_scale=1.00, corrects_errors=0.70),
    Profile("Caffeine Cody",
            "27, full-stack dev on his fourth cold brew, machine-gun bursts then dead stops",
            wpm_low=85, wpm_high=130, error_rate=0.045, burstiness=0.85,
            pause_scale=0.85, corrects_errors=0.55),
    Profile("Record-Holder Reyna",
            "24, competitive speed-typist, 99th percentile, near-flawless and metronome-smooth",
            wpm_low=120, wpm_high=165, error_rate=0.008, burstiness=0.20,
            pause_scale=0.60, corrects_errors=0.95),
    Profile("Baron",
            "fast typist who leaves the odd slip as he goes - then stops, reads, "
            "and proofreads from the top, jumping the cursor back to fix each one",
            wpm_low=80, wpm_high=120, error_rate=0.022, burstiness=0.85,
            pause_scale=0.90, corrects_errors=1.0, proofreads=True),
]

PROFILES_BY_NAME = {p.name: p for p in PROFILES}

DEFAULT_PROFILE = "Cubicle Carol"


def get(name):
    return PROFILES_BY_NAME.get(name, PROFILES_BY_NAME[DEFAULT_PROFILE])


def custom(wpm, error_rate, burstiness, pause_scale, corrects_errors, name="Custom"):
    """Build a one-off profile from UI sliders (a band of +/-20% around `wpm`)."""
    return Profile(name, "your own settings",
                   wpm_low=wpm * 0.8, wpm_high=wpm * 1.2,
                   error_rate=error_rate, burstiness=burstiness,
                   pause_scale=pause_scale, corrects_errors=corrects_errors)
