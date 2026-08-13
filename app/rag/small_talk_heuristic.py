"""
Cheap, local, zero-LLM-cost check for small-talk/non-football messages,
so `ask_siap()` can short-circuit before spending an embedding call and
a Gemini generation call on questions that have nothing to do with the
player dataset.

Deliberately conservative in the opposite direction from
`extraction_heuristic.py`: here, a false positive (treating a real
football question as small talk) is the costly mistake -- it would
silently swallow a real question. So this only matches a tight,
explicit set of greeting/meta patterns, and requires the ENTIRE
(stripped, lowercased) message to match -- not a substring anywhere
in a longer message. Anything even slightly ambiguous falls through
to the normal pipeline.
"""

import re

_SMALL_TALK_PATTERNS = [
    r"hi+!?",
    r"hello!?",
    r"hey+!?",
    r"(good\s)?(morning|afternoon|evening)!?",
    r"how\s+are\s+you\??",
    r"what'?s\s+up\??",
    r"who\s+are\s+you\??",
    r"what\s+can\s+you\s+do\??",
    r"thanks?!?|thank\s+you!?",
    r"bye!?|goodbye!?|see\s+ya!?",
    r"ok(ay)?!?|cool!?|nice!?",
]

_COMBINED_PATTERN = re.compile(
    r"^(" + "|".join(_SMALL_TALK_PATTERNS) + r")"
    r"([\s,!.?]+(" + "|".join(_SMALL_TALK_PATTERNS) + r"))*"
    r"[\s!.?]*$",
    re.IGNORECASE,
)


def is_small_talk(question: str) -> bool:
    """Returns True only if the entire message is small talk with no
    other content -- e.g. 'hi' or 'hi, how are you?' match, but
    'hi, how many strikers are over 90 pace?' does not, since the
    football question isn't just the small-talk phrase alone."""
    stripped = question.strip()
    # Strip a leading small-talk phrase + separator, then check if
    # anything meaningful remains.
    normalized = re.sub(r"[,.]", " ", stripped).strip()
    return bool(_COMBINED_PATTERN.match(normalized))


SMALL_TALK_RESPONSE = (
    "Hi! I'm Ask SIAP, a football analytics assistant. Ask me about "
    "players, stats, comparisons, or team/league data -- for example, "
    "\"who are the fastest wingers?\" or \"how many left-footed strikers "
    "are there?\""
)