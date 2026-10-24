"""Mock backend client.

Method names mirror the REST routes in the architecture PDF (section 04) so a
real HTTP client with the same methods can replace MockApi later. Views must
only talk to the backend through this module. No Streamlit imports here.
"""
import itertools
import json
import time
from copy import deepcopy
from datetime import datetime
from functools import lru_cache

from . import engine, intake
from .config import MOCK_DIR, STAGE_SECONDS

FAIL_STAGE = 3  # stage index that fails when the simulated outcome is "failure"


@lru_cache(maxsize=None)
def _load(rel_path):
    with open(MOCK_DIR / rel_path, encoding="utf-8") as fh:
        return json.load(fh)


def _fresh(rel_path):
    """Return a private copy so callers cannot mutate the cached snapshot."""
    return deepcopy(_load(rel_path))


class MockApi:
    """Per-session mock client. Created projects live on the instance only."""

    def __init__(self, stage_seconds=STAGE_SECONDS):
        self.stage_seconds = stage_seconds
        self._custom = {}      # title_id -> {"meta", "template", "outcome", "status"}
        self._jobs = {}        # job_id -> job dict
        self._ids = itertools.count(1)

    # ------------------------------------------------------------ config
    def get_config(self):
        return _fresh("config.json")

    # ---------------------------------------------------------- projects
    def list_projects(self):
        """GET /projects"""
        rows = []
        for p in _load("projects.json")["projects"]:
            meta = _load(f"{p['title_id']}/title.json")
            rows.append({"title_id": p["title_id"], "status": p["status"],
                         "last_analysis": p["last_analysis"], "title": meta["title"],
                         "format": meta["format"], "custom": False})
        for tid, c in self._custom.items():
            if c["status"] in ("complete", "partial"):
                rows.append({"title_id": tid, "status": c["status"], "last_analysis": c["date"],
                             "title": c["meta"]["title"], "format": c["meta"]["format"], "custom": True})
        return rows

    def get_title(self, title_id):
        """GET /titles/{id}"""
        if title_id in self._custom:
            return deepcopy(self._custom[title_id]["meta"])
        return _fresh(f"{title_id}/title.json")

    # ----------------------------------------------------------- analysis
    def get_analysis(self, title_id):
        """GET /analyses/{id}"""
        if title_id in self._custom:
            return self._custom_analysis(title_id)
        return _fresh(f"{title_id}/analysis.json")

    def get_regions(self, title_id):
        """GET /analyses/{id}/regions"""
        return _fresh(f"{self._template(title_id)}/regions.json")

    def get_comparables(self, title_id):
        return _fresh(f"{self._template(title_id)}/comparables.json")

    def get_sources(self, title_id):
        """GET /sources/health"""
        if title_id in self._custom:
            return self._custom_sources(title_id)
        return _fresh(f"{title_id}/sources.json")["sources"]

    def get_scenarios(self, title_id):
        """POST /analyses/{id}/scenarios (presets; custom ones go through the engine)"""
        return _fresh(f"{self._template(title_id)}/scenarios.json")

    def get_recommendation(self, title_id):
        """GET /analyses/{id}/recommendation"""
        return _fresh(f"{self._template(title_id)}/recommendation.json")

    # ----------------------------------------------------------- new jobs
    def start_analysis(self, payload, outcome="normal"):
        """POST /titles + POST /titles/{id}/analyse -> job id.

        outcome (prototype only): "normal", "partial" or "failure".
        """
        errors = intake.validate(payload)
        if errors:
            raise ValueError("; ".join(errors))
        n = next(self._ids)
        title_id = f"custom_{n}"
        template = self._pick_template(payload)
        pct, _ = intake.completeness(payload)
        meta = self._meta_from_payload(payload, title_id, pct)
        self._custom[title_id] = {"meta": meta, "template": template, "outcome": outcome,
                                  "status": "running", "date": datetime.now().strftime("%Y-%m-%d"),
                                  "cached_fallback": False}
        job_id = f"job_{n}"
        self._jobs[job_id] = {"title_id": title_id, "started": time.monotonic(), "outcome": outcome}
        return job_id

    def get_job(self, job_id):
        """GET /jobs/{id}"""
        job = self._jobs[job_id]
        cfg = _load("config.json")
        stages = cfg["pipeline_stages"]
        elapsed = time.monotonic() - job["started"]
        done = len(stages) if self.stage_seconds <= 0 else int(elapsed / self.stage_seconds)
        custom = self._custom[job["title_id"]]
        outcome = job["outcome"]
        failed = outcome == "failure" and done > FAIL_STAGE
        if failed:
            states = ["done"] * FAIL_STAGE + ["failed"] + ["pending"] * (len(stages) - FAIL_STAGE - 1)
            status = "failed"
        else:
            done = min(done, len(stages))
            states = ["done"] * done + (["running"] if done < len(stages) else []) + \
                     ["pending"] * max(0, len(stages) - done - 1)
            status = "running" if done < len(stages) else ("partial" if outcome in ("partial", "cached") else "complete")
        custom["status"] = status if status in ("complete", "partial") else custom["status"]
        if status == "failed":
            custom["status"] = "failed"
        progress = 100 if status in ("complete", "partial") else round(100 * min(done, len(stages)) / len(stages))
        return {
            "job_id": job_id, "title_id": job["title_id"], "status": status, "progress": progress,
            "stages": [{"name": n, "state": s} for n, s in zip(stages, states)],
            "sources": self._job_sources(job["title_id"], outcome, status),
            "error": "Comparable-title retrieval failed: AniList request timed out." if failed else None,
        }

    def retry_job(self, job_id):
        """Restart a failed job with a normal outcome."""
        job = self._jobs[job_id]
        job.update(started=time.monotonic(), outcome="normal")
        self._custom[job["title_id"]].update(outcome="normal", status="running")

    def use_cached_data(self, job_id):
        """Continue a failed job with cached metadata (partial result)."""
        job = self._jobs[job_id]
        job.update(started=time.monotonic() - self.stage_seconds * (FAIL_STAGE + 1), outcome="cached")
        self._custom[job["title_id"]].update(outcome="cached", status="running", cached_fallback=True)

    # ------------------------------------------------------------ helpers
    def _template(self, title_id):
        return self._custom[title_id]["template"] if title_id in self._custom else title_id

    @staticmethod
    def _pick_template(payload):
        genres = {payload.get("primary_genre", "")} | set(payload.get("secondary_genres") or [])
        best, best_score = "shadow_bloom", -1
        for p in _load("projects.json")["projects"]:
            meta = _load(f"{p['title_id']}/title.json")
            score = len(genres & set(meta["genres"])) * 2 + (1 if payload.get("format") == meta["format"] else 0)
            if score > best_score:
                best, best_score = p["title_id"], score
        return best

    @staticmethod
    def _meta_from_payload(p, title_id, pct):
        genres = [p["primary_genre"]] + [g for g in (p.get("secondary_genres") or []) if g != p["primary_genre"]]
        return {
            "title_id": title_id, "title": p["title"].strip(),
            "title_jp": "", "english_title": (p.get("english_title") or "").strip(),
            "synopsis": p["synopsis"].strip(), "format": p["format"], "genres": genres,
            "age_rating": p.get("age_rating") or "", "release_period": p["release_period"],
            "source_material": p["source_material"], "episodes": p.get("episodes"),
            "studio": (p.get("studio") or "").strip(), "franchise_status": p.get("franchise_status") or "",
            "themes": p.get("themes") or [], "intended_audience": p.get("intended_audience") or "",
            "target_platform": p["target_platform"], "target_languages": p.get("target_languages") or [],
            "target_states": p.get("target_states") or [], "budget_band": p.get("budget_band") or "",
            "director": (p.get("director") or "").strip(), "cast": p.get("cast") or [],
            "accent": "#5A4FCF", "trailer_url": (p.get("trailer_url") or "").strip(),
            "poster_name": p.get("poster_name") or "", "completeness": pct,
        }

    def _custom_sources(self, title_id):
        c = self._custom[title_id]
        sources = _fresh(f"{c['template']}/sources.json")["sources"]
        for s in sources:
            if c["outcome"] == "partial" and s["id"] == "youtube":
                s.update(status="unavailable", mode="none", note="Quota reached; refresh deferred.",
                         last_collected=None, toggleable=False)
            if c["cached_fallback"] and s["id"] == "anilist":
                s.update(mode="cached", note="Cached metadata used after a failed live call.")
        return sources

    def _custom_analysis(self, title_id):
        c = self._custom[title_id]
        a = _fresh(f"{c['template']}/analysis.json")
        a.update(title_id=title_id, analysis_id=f"an_{title_id}_001", created_at=datetime.now().isoformat(timespec="seconds"),
                 status="partial" if c["outcome"] in ("partial", "cached") else "complete",
                 mock_notice=f"Prototype result derived from the mock template '{c['template']}'.")
        tmpl_completeness = _load(f"{c['template']}/title.json")["completeness"]
        facs = a["confidence_factors"]
        facs["data_completeness"] = max(0, min(100, facs["data_completeness"] +
                                               0.5 * (c["meta"]["completeness"] - tmpl_completeness)))
        if c["outcome"] == "partial":
            yt = next(s for s in _fresh(f"{c['template']}/sources.json")["sources"] if s["id"] == "youtube")
            a["components"], a["confidence_factors"] = engine.apply_effects(
                a["components"], facs, yt["effect_if_disabled"])
            a["warnings"].append({"code": "youtube_unavailable", "severity": "warning",
                                  "message": "YouTube data is temporarily unavailable. The analysis continued with the remaining sources."})
        if c["cached_fallback"]:
            facs["data_freshness"] = max(0, facs["data_freshness"] - 5)
            a["warnings"].append({"code": "cached_metadata", "severity": "warning",
                                  "message": "Cached AniList metadata was used. Freshness confidence is reduced."})
        return a

    def _job_sources(self, title_id, outcome, status):
        out = []
        for s in _load("shadow_bloom/sources.json")["sources"]:
            if s["id"] in ("datameet", "partner_csv"):
                continue
            st, note = "Available", ""
            if s["id"] == "google_trends":
                st, note = "Cached data used", ""
            if s["id"] == "youtube" and outcome == "partial":
                st, note = "Unavailable", "Analysis continues without it"
            if s["id"] == "anilist" and outcome == "failure" and status == "failed":
                st, note = "Failed (timeout)", "Retry or use cached data"
            if s["id"] == "anilist" and outcome == "cached":
                st, note = "Cached data used", ""
            out.append({"name": s["name"], "status": st, "note": note})
        return out
