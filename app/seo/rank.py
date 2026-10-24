"""Rank candidate terms by measured Google Trends interest in India (v0, not a trained model).

There is no labelled SEO outcome in the data, so nothing is learned here. Each candidate is scored by its
interest relative to the Trends anchor term over the trailing window. That is relative search interest,
not search volume, keyword difficulty or rankings.
"""
from datetime import date, timedelta

from app.adapters.google_trends import GeoUnsupported, QuotaExceeded, TrendsClient, TrendsError
from app.seo.terms import Candidate

WINDOW_WEEKS = 52
MIN_SIGNAL_SUM = 5  # Trends rounds small values to 0; below this a term has no usable signal
METHOD = ("seo-v0: relative Google Trends interest in India vs the anchor term over the trailing "
          f"{WINDOW_WEEKS} weeks; not search volume")


def score_term(client: TrendsClient, term: str, geo: str, today: date) -> dict:
    """Interest ratio of `term` to the anchor for one geo. Never raises for Trends problems."""
    start = today - timedelta(weeks=WINDOW_WEEKS)
    try:
        env = client.fetch(term, geo, start, today)
    except QuotaExceeded as exc:
        return {"status": "blocked", "error": str(exc)}
    except GeoUnsupported:
        return {"status": "unsupported_geo"}
    except TrendsError as exc:
        return {"status": "error", "error": str(exc)}
    t, a = env["terms"]
    rows = [r for r in env["rows"] if not r["partial"]]
    total, anchor = sum(r["values"][t] for r in rows), sum(r["values"][a] for r in rows)
    return {"status": "ok" if total >= MIN_SIGNAL_SUM else "no_signal", "from_cache": env["from_cache"],
            "checksum": env["checksum"], "records": len(rows),
            "ratio": total / max(anchor, 1), "peak": max((r["values"][t] for r in rows), default=0),
            "weeks_with_signal": sum(1 for r in rows if r["values"][t] > 0)}


def rank(client: TrendsClient, cands: list[Candidate], today: date) -> list[dict]:
    """Candidates scored nationally, best first. Blocked/errored ones keep their place at the end."""
    scored = [{"term": c.term, "variant": c.variant, **score_term(client, c.term, "IN", today)} for c in cands]
    scored.sort(key=lambda r: (r["status"] != "ok", -r.get("ratio", 0.0)))
    return scored


def best_by_variant(ranked: list[dict]) -> dict[str, str]:
    out: dict[str, str] = {}
    for r in ranked:
        if r["status"] == "ok":
            out.setdefault(r["variant"].split(":")[0], r["term"])
    return out
