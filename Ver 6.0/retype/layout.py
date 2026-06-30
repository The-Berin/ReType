"""
QWERTY keyboard physics.

Every key maps to the hand, finger and row a touch-typist uses for it, plus an
approximate x-position so we can reason about distance. The humanizer turns this
geometry into realistic per-digraph timing: two keys hit by the *same finger*
are slow, *alternating hands* are fast, and jumping rows costs extra.

This module is pure data - no timing constants live here, so the realism model
can be recalibrated without touching the geometry.
"""

# Finger ids: 0 = index, 1 = middle, 2 = ring, 3 = pinky, 4 = thumb.
INDEX, MIDDLE, RING, PINKY, THUMB = 0, 1, 2, 3, 4

# row 0 = number row, 1 = top (qwerty), 2 = home (asdf), 3 = bottom (zxcv).
# col is an approximate horizontal position (in key-widths) for the standard
# row-staggered layout, used only for rough distance.
#
# key -> (hand, finger, row, col)
_KEYS = {
    # number row
    '`': ('L', PINKY, 0, 0.0), '1': ('L', PINKY, 0, 1.0), '2': ('L', RING, 0, 2.0),
    '3': ('L', MIDDLE, 0, 3.0), '4': ('L', INDEX, 0, 4.0), '5': ('L', INDEX, 0, 5.0),
    '6': ('R', INDEX, 0, 6.0), '7': ('R', INDEX, 0, 7.0), '8': ('R', MIDDLE, 0, 8.0),
    '9': ('R', RING, 0, 9.0), '0': ('R', PINKY, 0, 10.0), '-': ('R', PINKY, 0, 11.0),
    '=': ('R', PINKY, 0, 12.0),
    # top row
    'q': ('L', PINKY, 1, 0.5), 'w': ('L', RING, 1, 1.5), 'e': ('L', MIDDLE, 1, 2.5),
    'r': ('L', INDEX, 1, 3.5), 't': ('L', INDEX, 1, 4.5), 'y': ('R', INDEX, 1, 5.5),
    'u': ('R', INDEX, 1, 6.5), 'i': ('R', MIDDLE, 1, 7.5), 'o': ('R', RING, 1, 8.5),
    'p': ('R', PINKY, 1, 9.5), '[': ('R', PINKY, 1, 10.5), ']': ('R', PINKY, 1, 11.5),
    '\\': ('R', PINKY, 1, 12.5),
    # home row
    'a': ('L', PINKY, 2, 0.75), 's': ('L', RING, 2, 1.75), 'd': ('L', MIDDLE, 2, 2.75),
    'f': ('L', INDEX, 2, 3.75), 'g': ('L', INDEX, 2, 4.75), 'h': ('R', INDEX, 2, 5.75),
    'j': ('R', INDEX, 2, 6.75), 'k': ('R', MIDDLE, 2, 7.75), 'l': ('R', RING, 2, 8.75),
    ';': ('R', PINKY, 2, 9.75), "'": ('R', PINKY, 2, 10.75),
    # bottom row
    'z': ('L', PINKY, 3, 1.0), 'x': ('L', RING, 3, 2.0), 'c': ('L', MIDDLE, 3, 3.0),
    'v': ('L', INDEX, 3, 4.0), 'b': ('L', INDEX, 3, 5.0), 'n': ('R', INDEX, 3, 6.0),
    'm': ('R', INDEX, 3, 7.0), ',': ('R', MIDDLE, 3, 8.0), '.': ('R', RING, 3, 9.0),
    '/': ('R', PINKY, 3, 10.0),
    # space
    ' ': ('T', THUMB, 4, 5.0),
}

# Characters reached with Shift map to their base key (plus a shift penalty the
# humanizer adds separately).
_SHIFTED = {
    '~': '`', '!': '1', '@': '2', '#': '3', '$': '4', '%': '5', '^': '6',
    '&': '7', '*': '8', '(': '9', ')': '0', '_': '-', '+': '=', '{': '[',
    '}': ']', '|': '\\', ':': ';', '"': "'", '<': ',', '>': '.', '?': '/',
}


def key_info(ch):
    """(hand, finger, row, col) for `ch`, or None if it isn't on the keyboard."""
    if not ch:
        return None
    low = ch.lower()
    if low in _KEYS:
        return _KEYS[low]
    if ch in _SHIFTED:
        return _KEYS[_SHIFTED[ch]]
    return None


def needs_shift(ch):
    """True if producing `ch` requires holding Shift."""
    return ch.isupper() or ch in _SHIFTED


def digraph_factor(a, b):
    """
    A multiplier (~0.7 fast .. ~1.7 slow) on the base keystroke interval for
    typing `b` right after `a`, from pure keyboard mechanics.

      * same finger, different key  -> slowest (one finger must travel)
      * same finger, same key       -> a touch quicker than a finger-move
      * alternating hands           -> fastest (the next finger is already poised)
      * same hand, different finger  -> in between
    Row jumps add a little on top. Returns 1.0 if either key is unknown.
    """
    ia, ib = key_info(a), key_info(b)
    if ia is None or ib is None:
        return 1.0

    hand_a, finger_a, row_a, col_a = ia
    hand_b, finger_b, row_b, col_b = ib

    # The thumb (space bar) is effectively "free" - either hand is ready.
    if finger_a == THUMB or finger_b == THUMB:
        base = 0.95
    elif hand_a != hand_b:
        base = 0.78                      # hands alternate: quickest
    elif finger_a == finger_b:
        base = 1.7 if a.lower() != b.lower() else 1.45   # same finger: slowest
    else:
        # same hand, different fingers: outward rolls slightly easier than inward
        base = 1.12 if finger_b > finger_a else 1.0

    base += 0.06 * abs(row_a - row_b)    # row jump penalty
    base += 0.015 * min(abs(col_a - col_b), 6)
    return base
