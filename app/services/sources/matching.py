from __future__ import annotations

import re
from difflib import SequenceMatcher


def normalise(text: str) -> str:
    return re.sub(r"[\W_]+", " ", text.casefold()).strip()


def match_score(query: str, candidate: str) -> float:
    """0-1 similarity between a title and a candidate name; prefix matches count as strong."""
    q, c = normalise(query), normalise(candidate)
    if not q or not c:
        return 0.0
    ratio = SequenceMatcher(None, q, c).ratio()
    if len(q) >= 4 and (c.startswith(q) or q.startswith(c)):
        ratio = max(ratio, 0.9)
    return ratio
