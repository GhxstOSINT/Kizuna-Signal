"""Candidate search terms for a title.

Built from the names and the localization assumptions already on the title, so every candidate
can be traced to something the user entered. Nothing here knows search volume: that is measured
(app/seo/rank.py), never guessed.
"""

import re
from dataclasses import dataclass

LANGUAGES = {
    "hi": "Hindi",
    "ta": "Tamil",
    "te": "Telugu",
    "bn": "Bengali",
    "mr": "Marathi",
    "ml": "Malayalam",
    "kn": "Kannada",
    "gu": "Gujarati",
    "pa": "Punjabi",
}
_SEQUEL_SUFFIX = re.compile(r"\s+(\d+(st|nd|rd|th)\s+)?(season|part|cour)(\s.*)?$", re.I)
MAX_CANDIDATES = 6


@dataclass(frozen=True)
class Candidate:
    term: str
    variant: str  # which name or modifier produced it


def base_name(name: str) -> str:
    """Name without sequel suffix or subtitle (the form people actually type)."""
    return _SEQUEL_SUFFIX.sub("", name.split(":")[0].strip())[:60].strip()


def candidates(
    name_en: str, name_jp: str | None, languages: list[str], localization_mode: str | None
) -> list[Candidate]:
    out: list[Candidate] = []

    def add(term: str, variant: str) -> None:
        term = " ".join(term.split())
        if term and term.lower() not in {c.term.lower() for c in out}:
            out.append(Candidate(term, variant))

    base = base_name(name_en)
    add(base, "english")
    add(f"{base} anime", "english+anime")
    if name_jp:
        add(base_name(name_jp), "japanese")
    if localization_mode and "dubbed" in localization_mode:
        for code in languages:
            if code in LANGUAGES:
                add(f"{base} {LANGUAGES[code]} dubbed", f"dub:{code}")
    return out[:MAX_CANDIDATES]
