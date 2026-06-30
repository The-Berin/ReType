"""
Word familiarity.

People rip through words their fingers know by heart ("the", "and", "you") and
slow down on long or unfamiliar ones, often hesitating partway through. This
module scores how "familiar" a word is so the humanizer can speed up bursts on
common words and add mid-word hesitation to rare or long ones.

A small embedded frequency list keeps it dependency-free.
"""

# ~250 of the most common English words. Membership = instantly familiar.
_COMMON = frozenset("""
the be to of and a in that have i it for not on with he as you do at this but his
by from they we say her she or an will my one all would there their what so up out
if about who get which go me when make can like time no just him know take people
into year your good some could them see other than then now look only come its over
think also back after use two how our work first well way even new want because any
these give day most us is are was were been has had did said make made find here thing
many where much through before great little world own under last right too old why same
woman man life child eg place week case point government company number group problem fact
be being am does going got really something nothing everything thanks please hello yes
""".split())


def is_common(word):
    """True if the bare word (case-folded, stripped) is in the common set."""
    return word.strip().lower() in _COMMON


def familiarity(word):
    """
    A 0..1 score: 1.0 = your fingers know it cold, 0.0 = laborious.

    Common short words score near 1; long uncommon words score low, which the
    humanizer uses to slow them down and add mid-word hesitation.
    """
    bare = word.strip().lower()
    if not bare:
        return 1.0
    score = 0.45
    if bare in _COMMON:
        score += 0.45
    # Short words are easy; every char past ~6 chips away at familiarity.
    score += max(-0.4, (6 - len(bare)) * 0.05)
    return max(0.0, min(1.0, score))


def split_words(text):
    """
    Split text into runs, preserving whitespace so it can be re-typed verbatim.

    Returns a list of (token, is_word) where is_word is True for a run of
    non-space characters and False for a run of spaces/newlines. Concatenating
    every token reproduces the original text exactly.
    """
    tokens = []
    if not text:
        return tokens
    buf = text[0]
    cur_space = text[0].isspace()
    for ch in text[1:]:
        if ch.isspace() == cur_space:
            buf += ch
        else:
            tokens.append((buf, not cur_space))
            buf = ch
            cur_space = ch.isspace()
    tokens.append((buf, not cur_space))
    return tokens
