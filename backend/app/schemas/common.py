from typing import Annotated

from pydantic import AfterValidator


def _clean_unique(values: list[str]) -> list[str]:
    """Strip whitespace, drop blanks, and de-duplicate case-insensitively (order kept)."""
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        value = value.strip()
        if value and value.lower() not in seen:
            seen.add(value.lower())
            out.append(value)
    return out


CleanList = Annotated[list[str], AfterValidator(_clean_unique)]


def iso_language_codes(values: list[str]) -> list[str]:
    """Lower-case ISO 639-1 codes; at least one is required."""
    values = [v.lower() for v in values]
    if not values:
        raise ValueError("at least one language is required")
    bad = [v for v in values if not (len(v) == 2 and v.isalpha())]
    if bad:
        raise ValueError(f"not ISO 639-1 codes: {', '.join(bad)}")
    return values
