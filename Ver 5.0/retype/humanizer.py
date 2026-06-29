"""
The brain: turn text into a stream of realistically-timed keystrokes.

`HumanTyper.generate(text)` yields low-level ops - ('type', char, ms),
('back', None, ms), ('pause', None, ms) - that the engine plays back. All the
realism lives here:

  * per-keystroke digraph timing (alternating hands fast, same finger slow)
  * word bursts: a familiar word fires as a quick flurry, then a planning pause
    before the next - rare/long words cost more up front and hesitate mid-word
  * macro speed swings: the target WPM random-walks inside the persona's band,
    with burst words and heavy-tailed "thinking" stalls (coefficient of
    variation ~0.55, matching real sessions)
  * a stamina arc: energy decays as it types, so gaps widen, pauses lengthen
    and mistakes creep up - plus a cold-start warm-up at the very beginning
  * seven human error types, each either corrected or (optionally) left in

Calibration anchors: Dhakal et al. 2018 (136M keystrokes, ~240 ms mean IKI),
Gentner digraph timings, Ostry inter-key models. Base IKI = 12000 / WPM ms.
"""

import math
import random

from . import layout
from . import words

# ----------------------------------------------------------------- constants ---
INTRA_WORD_SPEEDUP = 0.6      # within a familiar word, keystrokes run ~60% of base
INTER_WORD_MEAN = 290.0       # ms, mean between-word pause
INTER_WORD_MIN = 130.0
INTER_WORD_MAX = 1000.0
CORRECTION_LATENCY = (260, 620)   # ms before noticing+fixing a slip
ENERGY_FLOOR = 0.6            # never drops below 60% stamina
ENERGY_DECAY_CHARS = 3500.0   # chars over which energy slides to the floor

# Physically adjacent QWERTY keys - a slip lands on a neighbour.
ADJACENT_KEYS = {
    'a': 'qwsz',   'b': 'vghn',   'c': 'xdfv',   'd': 'serfcx', 'e': 'wsdr',
    'f': 'drtgvc', 'g': 'ftyhbv', 'h': 'gyujnb', 'i': 'ujko',   'j': 'huikmn',
    'k': 'jiolm',  'l': 'kop',    'm': 'njk',    'n': 'bhjm',   'o': 'iklp',
    'p': 'ol',     'q': 'wa',     'r': 'edft',   's': 'awedxz', 't': 'rfgy',
    'u': 'yhji',   'v': 'cfgb',   'w': 'qase',   'x': 'zsdc',   'y': 'tghu',
    'z': 'asx',
}

# The original hand-picked fat-finger combos from ReType 1.0/2.0 - kept on purpose.
CUSTOM_ERRORS = ['jj', 'gh', 'ik', 'il', 'l;']

SENTENCE_END = ".!?"
CLAUSE_END = ",;:"


class HumanTyper:
    def __init__(self, profile, *, make_errors=True, leave_uncorrected=False,
                 digraph_override=None, seed=None):
        self.profile = profile
        self.make_errors = make_errors
        self.leave_uncorrected = leave_uncorrected
        # Optional {(prev_low, ch_low): ms} table from Record-and-Mimic.
        self.digraph_override = digraph_override or {}
        self.rng = random.Random(seed)
        self._reset()

    # --------------------------------------------------------------- state ---
    def _reset(self):
        self.committed = 0                 # net chars typed (for energy + warm-up)
        self.cur_wpm = self.profile.wpm_low * 0.92   # start cold, below the band

    def _energy(self):
        e = 1.0 - self.committed / ENERGY_DECAY_CHARS
        return max(ENERGY_FLOOR, e)

    def _warmup(self):
        # Fingers wake up over the first ~40 characters.
        return 1.0 + 0.18 * math.exp(-self.committed / 40.0)

    def _retune_speed(self):
        """Random-walk the working WPM inside the persona's band (macro drift)."""
        lo, hi = self.profile.wpm_low, self.profile.wpm_high
        span = hi - lo
        step = self.rng.gauss(0, span * (0.10 + 0.25 * self.profile.burstiness))
        # gentle pull back toward the middle so it doesn't stick at an edge
        center_pull = (self.profile.wpm_mid - self.cur_wpm) * 0.08
        self.cur_wpm = min(hi, max(lo, self.cur_wpm + step + center_pull))

    def _err_rate(self):
        # Tired typists make more mistakes (energy < 1 -> rate climbs).
        return min(0.30, self.profile.error_rate / self._energy())

    def _corrects(self):
        return 1.0 if not self.leave_uncorrected else self.profile.corrects_errors

    # --------------------------------------------------------------- timing ---
    def _key_ms(self, prev, ch, *, in_word, in_burst, fam, pos, n):
        iki = 12000.0 / max(1.0, self.cur_wpm)

        key = (prev.lower(), ch.lower()) if prev else None
        if key in self.digraph_override:
            iki = self.digraph_override[key]        # measured from a real person
            factor = 1.0
        else:
            factor = layout.digraph_factor(prev, ch) if prev else 1.0

        mult = 1.0
        if in_word:
            mult *= INTRA_WORD_SPEEDUP
        if in_burst:
            mult *= 0.7
        if layout.needs_shift(ch):
            mult *= 1.18
        if not ch.isalnum() and ch != ' ':
            mult *= 1.25

        # A single mid-word hesitation on long / unfamiliar words.
        if in_word and n >= 6 and 0 < pos < n - 1 and self.rng.random() < (1 - fam) * 0.18:
            mult *= self.rng.uniform(1.8, 3.0)

        sigma = (0.12 if in_burst else 0.30) + 0.25 * self.profile.burstiness
        jitter = max(0.45, self.rng.gauss(1.0, sigma))

        ms = iki * factor * mult * jitter * (2.0 - self._energy()) * self._warmup()
        return int(max(8, ms))

    def _planning_ms(self, word, fam):
        """Lexical onset cost paid before a word's first key (length + rarity)."""
        plan = self.rng.uniform(20, 90)
        plan += (1 - fam) * self.rng.uniform(180, 600)
        plan += max(0, len(word) - 5) * self.rng.uniform(8, 26)
        plan *= self.profile.pause_scale * (2.0 - self._energy())
        return int(plan)

    def _boundary_ms(self, *, newline, after_sentence, after_clause):
        if newline:
            base = self.rng.uniform(480, 1150)
        else:
            base = min(INTER_WORD_MAX, max(INTER_WORD_MIN,
                                           self.rng.gauss(INTER_WORD_MEAN, 120)))
            if after_sentence:
                base *= self.rng.uniform(1.6, 2.6)
            elif after_clause:
                base *= self.rng.uniform(1.2, 1.7)
        base *= self.profile.pause_scale
        # Heavy-tailed cognitive stall: a rare multi-second freeze.
        if self.rng.random() < 0.03 * (1 + self.profile.burstiness):
            base += self.rng.uniform(700, 2800)
        base *= (2.0 - self._energy())
        return int(base)

    # ---------------------------------------------------------------- errors ---
    def _adj(self, ch):
        low = ch.lower()
        if low not in ADJACENT_KEYS:
            return None
        wrong = self.rng.choice(ADJACENT_KEYS[low])
        return wrong.upper() if ch.isupper() else wrong

    def _inject_error(self, prev, ch, rest, in_burst, fam):
        """
        Return (ops, consumed, last_char) for a slip starting at `ch`, or None
        if no usable error applies. `rest` is the remainder of the current word
        (rest[0] is the next char). Honours correct-vs-leave-in behaviour.
        """
        correct = self.rng.random() < self._corrects()
        nxt = rest[0] if rest else ''

        def t(p, c, **kw):
            return ('type', c, self._key_ms(p, c, in_word=True, in_burst=in_burst,
                                            fam=fam, pos=kw.get('pos', 1),
                                            n=kw.get('n', 8)))

        if correct:
            kinds = ['adjacent', 'double', 'case', 'custom']
            if rest:
                kinds.append('delayed')
            if nxt.isalpha():
                kinds.append('transpose')
            kind = self.rng.choice(kinds)

            if kind == 'adjacent':
                w = self._adj(ch)
                if not w:
                    return None
                return ([t(prev, w),
                         ('pause', None, self.rng.randint(*CORRECTION_LATENCY)),
                         ('back', None, self.rng.randint(80, 170)),
                         t(w, ch)], 1, ch)

            if kind == 'case':
                w = ch.upper() if ch.islower() else ch.lower()
                if len(w) != 1:          # e.g. 'ß'->'SS'; a single backspace can't undo it
                    return None
                return ([t(prev, w),
                         ('pause', None, self.rng.randint(*CORRECTION_LATENCY)),
                         ('back', None, self.rng.randint(80, 170)),
                         t(w, ch)], 1, ch)

            if kind == 'double':
                return ([t(prev, ch),
                         ('type', ch, int(self._key_ms(ch, ch, in_word=True,
                                                       in_burst=in_burst, fam=fam,
                                                       pos=1, n=8) * 0.5)),
                         ('pause', None, self.rng.randint(*CORRECTION_LATENCY)),
                         ('back', None, self.rng.randint(80, 170))], 1, ch)

            if kind == 'custom':
                blob = self.rng.choice(CUSTOM_ERRORS)
                ops = []
                p = prev
                for c in blob:
                    ops.append(t(p, c))
                    p = c
                ops.append(('pause', None, self.rng.randint(*CORRECTION_LATENCY)))
                ops += [('back', None, self.rng.randint(70, 150)) for _ in blob]
                ops.append(t(prev, ch))
                return (ops, 1, ch)

            if kind == 'transpose':
                a, b = ch, nxt
                return ([t(prev, b), t(b, a),
                         ('pause', None, self.rng.randint(*CORRECTION_LATENCY)),
                         ('back', None, self.rng.randint(80, 160)),
                         ('back', None, self.rng.randint(70, 140)),
                         t(prev, a), t(a, b)], 2, b)

            if kind == 'delayed':
                w = self._adj(ch)
                if not w:
                    return None
                k = self.rng.randint(1, min(3, len(rest)))
                extra = rest[:k]
                ops = [t(prev, w)]
                p = w
                for c in extra:
                    ops.append(t(p, c)); p = c
                ops.append(('pause', None, self.rng.randint(300, 750)))
                ops += [('back', None, self.rng.randint(70, 150)) for _ in range(len(extra) + 1)]
                ops.append(t(prev, ch)); p = ch
                for c in extra:
                    ops.append(t(p, c)); p = c
                return (ops, 1 + len(extra), p)

        # ---- left-in (uncorrected) slips: final text deliberately differs ----
        kinds = ['adjacent', 'double', 'drop', 'case']
        if nxt.isalpha():
            kinds.append('transpose')
        kind = self.rng.choice(kinds)

        if kind == 'adjacent':
            w = self._adj(ch)
            if not w:
                return None
            return ([t(prev, w)], 1, w)            # ch replaced by neighbour
        if kind == 'case':
            w = ch.upper() if ch.islower() else ch.lower()
            if len(w) != 1:
                return None
            return ([t(prev, w)], 1, w)
        if kind == 'double':
            return ([t(prev, ch),
                     ('type', ch, int(self._key_ms(ch, ch, in_word=True,
                                                   in_burst=in_burst, fam=fam,
                                                   pos=1, n=8) * 0.5))], 1, ch)
        if kind == 'drop':
            return ([], 1, prev)                   # letter simply omitted
        if kind == 'transpose':
            a, b = ch, nxt
            return ([t(prev, b), t(b, a)], 2, a)   # left swapped
        return None

    # ------------------------------------------------------------- generate ---
    def generate(self, text):
        """Dispatch: most personas type linearly; proofreaders go two-phase."""
        if self.profile.proofreads:
            yield from self._generate_proofread(text)
        else:
            yield from self._generate_linear(text)

    def _generate_linear(self, text):
        self._reset()
        tokens = words.split_words(text)
        prev = ''
        last_visible = ''   # last non-space char, for sentence/clause pauses

        for tok, is_word in tokens:
            if is_word:
                self._retune_speed()
                fam = words.familiarity(tok)
                plan = self._planning_ms(tok, fam)
                if plan:
                    yield ('pause', None, plan)
                in_burst = self.rng.random() < (0.30 + 0.45 * self.profile.burstiness) * fam

                i, n = 0, len(tok)
                while i < n:
                    ch = tok[i]
                    rest = tok[i + 1:]
                    if (self.make_errors and ch.isalpha()
                            and self.rng.random() < self._err_rate()):
                        res = self._inject_error(prev, ch, rest, in_burst, fam)
                        if res is not None:
                            ops, consumed, last = res
                            for op in ops:
                                yield op
                                if op[0] == 'type':
                                    self.committed += 1
                                elif op[0] == 'back':
                                    self.committed -= 1
                            prev = last or prev
                            if last and not last.isspace():
                                last_visible = last
                            i += consumed
                            continue
                    yield ('type', ch, self._key_ms(prev, ch, in_word=True,
                                                    in_burst=in_burst, fam=fam,
                                                    pos=i, n=n))
                    self.committed += 1
                    prev = ch
                    if not ch.isspace():
                        last_visible = ch
                    i += 1
            else:
                for ch in tok:
                    newline = (ch == '\n')
                    after_sentence = last_visible in SENTENCE_END
                    after_clause = last_visible in CLAUSE_END
                    yield ('type', ch, self._boundary_ms(newline=newline,
                                                         after_sentence=after_sentence,
                                                         after_clause=after_clause))
                    self.committed += 1
                    prev = ch

    # ----------------------------------------------------------- proofreading ---
    # The "Baron" path: type fast and sloppy, leaving simple mistakes IN and
    # remembering where they are; occasionally glance back a few lines to fix a
    # recent one; then stop, read, and sweep the whole thing top-to-bottom,
    # moving the cursor (arrow keys / Ctrl+Home/End) to each remaining error and
    # fixing it. Every recorded error is stored as (start, wrong_len, correct):
    # in the live buffer, the wrong_len chars at `start` should become `correct`.

    def _nav_ms(self):
        """A quick cursor-movement keystroke (Ctrl+Home/End travel)."""
        return int(max(8, self.rng.gauss(46, 16)))

    def _scan_ms(self):
        """Cursor stepping while reading along the line, looking for slips."""
        return int(max(12, self.rng.gauss(80, 26)))

    def _reading_ms(self, length):
        """The 'stop and read it over' pause before proofreading."""
        base = self.rng.uniform(900, 2200) + length * self.rng.uniform(2, 6)
        return int(base * self.profile.pause_scale)

    def _fix_segment(self, cur, start, wlen, correct):
        """
        Yield ops that read across to the wrong segment, pause to *register* the
        mistake, delete it, hesitate, retype `correct`, and re-read to confirm.
        The caller tracks the resulting cursor position = start + len(correct).
        """
        target = start + wlen                  # right edge of the wrong run
        if cur <= target:
            # reading forward along the text, eyes scanning for errors
            moved = 0
            while cur < target:
                yield ('right', None, self._scan_ms())
                cur += 1
                moved += 1
                if moved % self.rng.randint(5, 11) == 0:
                    yield ('pause', None, self.rng.randint(140, 460))   # reading a few words
        else:
            # "...hang on, something back there" - glance back to it
            yield ('pause', None, self.rng.randint(260, 720))
            while cur > target:
                yield ('left', None, self._scan_ms())
                cur -= 1

        # spotted it: a beat to actually register the mistake before fixing
        yield ('pause', None, self.rng.randint(450, 1500))
        for _ in range(wlen):
            yield ('back', None, self._key_ms('', 'x', in_word=True, in_burst=False,
                                              fam=0.5, pos=1, n=8))
            self.committed -= 1
        if correct:
            yield ('pause', None, self.rng.randint(150, 480))   # what was it meant to be
        prev = ''
        for c in correct:
            yield ('type', c, self._key_ms(prev, c, in_word=True, in_burst=False,
                                           fam=0.7, pos=1, n=8))
            self.committed += 1
            prev = c
        yield ('pause', None, self.rng.randint(220, 680))       # re-read to confirm the fix

    def _generate_proofread(self, text):
        self._reset()
        tokens = words.split_words(text)
        prev = ''
        last_visible = ''
        length = 0                              # live buffer length = cursor at end
        errors = []                             # (start, wrong_len, correct)

        # ---- Phase 1: type it out, leaving simple mistakes in -------------
        for tok, is_word in tokens:
            if is_word:
                self._retune_speed()
                fam = words.familiarity(tok)
                plan = self._planning_ms(tok, fam)
                if plan:
                    yield ('pause', None, plan)
                in_burst = self.rng.random() < (0.30 + 0.45 * self.profile.burstiness) * fam

                i, n = 0, len(tok)
                while i < n:
                    ch = tok[i]
                    nxt = tok[i + 1] if i + 1 < n else ''
                    made = False
                    if ch.isalpha() and self.rng.random() < self._err_rate():
                        kinds = ['sub', 'double', 'drop']
                        if nxt.isalpha():
                            kinds.append('transpose')
                        kind = self.rng.choice(kinds)

                        if kind == 'sub':
                            w = self._adj(ch)
                            if w:
                                yield ('type', w, self._key_ms(prev, w, in_word=True,
                                       in_burst=in_burst, fam=fam, pos=i, n=n))
                                errors.append((length, 1, ch))
                                length += 1; self.committed += 1
                                prev = w; last_visible = w; i += 1; made = True
                        elif kind == 'double':
                            yield ('type', ch, self._key_ms(prev, ch, in_word=True,
                                   in_burst=in_burst, fam=fam, pos=i, n=n))
                            yield ('type', ch, int(self._key_ms(ch, ch, in_word=True,
                                   in_burst=in_burst, fam=fam, pos=i, n=n) * 0.5))
                            errors.append((length + 1, 1, ''))
                            length += 2; self.committed += 2
                            prev = ch; last_visible = ch; i += 1; made = True
                        elif kind == 'drop':
                            errors.append((length, 0, ch))   # typed nothing
                            i += 1; made = True
                        elif kind == 'transpose':
                            c2 = nxt
                            yield ('type', c2, self._key_ms(prev, c2, in_word=True,
                                   in_burst=in_burst, fam=fam, pos=i, n=n))
                            yield ('type', ch, int(self._key_ms(c2, ch, in_word=True,
                                   in_burst=in_burst, fam=fam, pos=i, n=n) * 0.8))
                            errors.append((length, 2, ch + c2))
                            length += 2; self.committed += 2
                            prev = ch; last_visible = ch; i += 2; made = True

                    if not made:
                        yield ('type', ch, self._key_ms(prev, ch, in_word=True,
                               in_burst=in_burst, fam=fam, pos=i, n=n))
                        length += 1; self.committed += 1
                        prev = ch
                        if not ch.isspace():
                            last_visible = ch
                        i += 1

                # Occasionally glance back a few lines and fix the most recent slip.
                recent = [e for e in errors if e[0] >= length - 90]
                if recent and self.rng.random() < 0.22:
                    err = max(recent, key=lambda e: e[0])
                    start, wlen, correct = err
                    yield from self._fix_segment(length, start, wlen, correct)
                    yield ('cursor_end', None, self._nav_ms() * 2)
                    errors.remove(err)
                    delta = len(correct) - wlen
                    # editing here shifts every still-pending error after this point
                    errors[:] = [(s + delta, wl, c) if s >= start + wlen else (s, wl, c)
                                 for (s, wl, c) in errors]
                    length += delta                    # buffer length changed
                    prev = ''
            else:
                for ch in tok:
                    yield ('type', ch, self._boundary_ms(
                        newline=(ch == '\n'),
                        after_sentence=last_visible in SENTENCE_END,
                        after_clause=last_visible in CLAUSE_END))
                    length += 1; self.committed += 1
                    prev = ch

        # ---- Phase 2: stop and read it over -------------------------------
        yield ('pause', None, self._reading_ms(length))

        # ---- Phase 3: proofread top-to-bottom, fixing each remaining slip --
        if not errors:
            return
        yield ('cursor_home', None, self._nav_ms() * 3)
        cur = 0
        delta = 0
        # keep one decides-to-leave-it chance per error only in max-realism mode
        for start, wlen, correct in sorted(errors, key=lambda e: e[0]):
            if self.leave_uncorrected and self.rng.random() > self.profile.corrects_errors:
                continue                          # missed one on the proofread too
            astart = start + delta
            for op in self._fix_segment(cur, astart, wlen, correct):
                yield op
            cur = astart + len(correct)
            delta += len(correct) - wlen
        yield ('cursor_end', None, self._nav_ms() * 3)
