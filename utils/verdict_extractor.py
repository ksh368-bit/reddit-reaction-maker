"""Extracts AITA verdict from post comments."""
from __future__ import annotations
import re

_VERDICT_RE = re.compile(r'\b(NTA|YTA|ESH|NAH|INFO)\b', re.IGNORECASE)

# Public — imported by card_renderer.py
VERDICT_TEXT: dict[str, str] = {
    "NTA":  "Not the asshole.",
    "YTA":  "You are the asshole.",
    "ESH":  "Everyone sucks here.",
    "NAH":  "No assholes here.",
    "INFO": "More information needed.",
}


def extract_verdict(comments) -> str | None:
    """
    Return majority verdict (NTA/YTA/ESH/NAH/INFO) from top 5 comments, or None.

    Top comment (index 0, most upvoted) is weighted ×3 since it represents
    the strongest community consensus signal.
    """
    tally: dict[str, int] = {}
    for i, c in enumerate(comments[:5]):
        m = _VERDICT_RE.search(c.body[:80])  # verdict almost always in first 80 chars
        if m:
            v = m.group(1).upper()
            weight = 3 if i == 0 else 1
            tally[v] = tally.get(v, 0) + weight
    if not tally:
        return None
    return max(tally, key=tally.get)
