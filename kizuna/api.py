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
from functools import cache

import httpx

from . import engine, intake
from .config import API_URL, FRONTEND_MODE, MOCK_DIR, STAGE_SECONDS

FAIL_STAGE = 3  # stage index that fails when the simulated outcome is "failure"


@cache
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
            "stages": [{"name": n, "state": s} for n, s in zip(stages, states, strict=False)],
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


class BackendApi:
    """HTTP adapter that translates the versioned FastAPI contract for the Streamlit views."""

    def __init__(self, base_url=API_URL, timeout=8.0, transport=None):
        self.base_url = base_url.rstrip("/")
        self.client = httpx.Client(base_url=self.base_url, timeout=timeout, transport=transport)
        self._titles = {}
        self._analysis_ids = {}
        self._job_aliases = {}
        self._project_id = None

    def close(self):
        self.client.close()

    def is_available(self):
        try:
            return self.client.get("/health/ready").status_code == 200
        except httpx.HTTPError:
            return False

    def _request(self, method, path, **kwargs):
        response = self.client.request(method, path, **kwargs)
        if response.is_error:
            try:
                error = response.json().get("error", {})
                message = error.get("message") or response.text
            except ValueError:
                message = response.text
            raise RuntimeError(f"Backend request failed ({response.status_code}): {message}")
        return response.json()

    def get_config(self):
        return _fresh("config.json")

    def list_projects(self):
        rows = []
        for project in self._request("GET", "/projects"):
            for title in self._request("GET", f"/projects/{project['id']}/titles"):
                self._titles[title["id"]] = title
                analyses = self._request("GET", f"/titles/{title['id']}/analyses")
                usable = [item for item in analyses if item["result"] is not None]
                if not usable:
                    continue
                latest = usable[0]
                self._analysis_ids[title["id"]] = latest["id"]
                rows.append(
                    {
                        "title_id": title["id"],
                        "status": self._ui_status(latest["status"]),
                        "last_analysis": latest["created_at"][:10],
                        "title": title["name"],
                        "format": title["content_format"],
                        "custom": True,
                    }
                )
        return rows

    def _find_title(self, title_id):
        if title_id not in self._titles:
            self.list_projects()
        if title_id not in self._titles:
            raise KeyError(f"Unknown title: {title_id}")
        return self._titles[title_id]

    def get_title(self, title_id):
        title = self._find_title(title_id)
        return {
            "title_id": title["id"],
            "title": title["name"],
            "title_jp": title["name"] if any(ord(ch) > 127 for ch in title["name"]) else "",
            "english_title": title.get("english_title") or "",
            "synopsis": title["synopsis"],
            "format": title["content_format"],
            "genres": [title["primary_genre"], *title.get("genres", [])],
            "themes": title.get("themes", []),
            "source_material": title["source_material"],
            "release_period": title["expected_release_period"],
            "target_platform": title["target_platform"],
            "target_languages": title.get("target_languages", []),
            "target_states": title.get("target_states", []),
            "budget_band": title.get("marketing_budget", "medium").title(),
            "studio": title.get("studio") or "",
            "franchise_status": title.get("franchise_status") or "",
            "age_rating": "",
            "accent": "#5A4FCF",
            "completeness": 100,
        }

    def _analysis(self, title_id):
        if title_id not in self._analysis_ids:
            analyses = self._request("GET", f"/titles/{title_id}/analyses")
            usable = [item for item in analyses if item["result"] is not None]
            if not usable:
                raise RuntimeError("No completed analysis exists for this title.")
            self._analysis_ids[title_id] = usable[0]["id"]
        return self._request("GET", f"/analyses/{self._analysis_ids[title_id]}")

    def _result(self, title_id):
        return self._analysis(title_id)["result"]

    def get_analysis(self, title_id):
        record = self._analysis(title_id)
        result = record["result"]
        title = self._find_title(title_id)
        confidence = result["confidence_score"]
        similarities = [item["similarity"] * 100 for item in result["comparable_titles"]]
        regional_conf = [item["confidence"] for item in result["regional_scores"]]
        freshness = [item["freshness_score"] * 100 for item in result["source_status"]]
        factors = {
            "data_completeness": confidence,
            "source_agreement": confidence,
            "comparable_quality": sum(similarities) / len(similarities) if similarities else confidence,
            "regional_evidence": sum(regional_conf) / len(regional_conf) if regional_conf else confidence,
            "data_freshness": sum(freshness) / len(freshness) if freshness else confidence,
        }
        source_ids = [item["source"] for item in result["source_status"]]
        drivers = []
        for index, item in enumerate(
            [*result["positive_drivers"], *result["negative_drivers"]], 1
        ):
            sign = 1 if item["direction"] == "positive" else -1
            drivers.append(
                {
                    "id": f"backend_driver_{index}",
                    "label": item["name"],
                    "points": sign * item["contribution"],
                    "component": self._driver_component(item["name"]),
                    "source_ids": source_ids,
                    "why": item["evidence"],
                }
            )
        label = result["decision_classification"].replace("_", " ").title()
        return {
            "analysis_id": result["analysis_id"],
            "title_id": title_id,
            "status": self._ui_status(record["status"]),
            "result_version": result["feature_version"],
            "scoring_config_version": result["scoring_version"],
            "model_version": result["model_version"],
            "model_used": "primary",
            "feature_snapshot_id": result["feature_version"],
            "created_at": record["created_at"],
            "components": {**result["component_scores"], "localization_readiness": 50},
            "confidence_factors": factors,
            "content_dna": self._content_dna(title),
            "drivers": drivers,
            "warnings": [
                {"code": "data_quality", "severity": "warning", "message": message}
                for message in result["data_quality_warnings"]
            ],
            "limitations": [
                "Public demand proxies only; no guaranteed revenue or viewership outcomes."
            ],
            "_authoritative": {
                "score": round(result["market_potential_score"]),
                "confidence": round(confidence),
                "interval": [round(value) for value in result["confidence_interval"]],
                "label": label,
            },
        }

    def get_regions(self, title_id):
        rows = []
        for item in self._result(title_id)["regional_scores"]:
            rows.append(
                {
                    **item,
                    "evidence_strength": item["confidence"],
                    "demand_momentum": self._strength(item["score"]),
                    "secondary_language": "English",
                    "audience_segment": "Young urban Japanese-content viewers",
                    "market_index": round(item["score"]),
                }
            )
        by_language = {}
        for row in rows:
            by_language.setdefault(row["recommended_language"], []).append(row)
        affinity = [
            {
                "language": language,
                "affinity": round(sum(row["score"] for row in language_rows) / len(language_rows)),
                "confidence": round(
                    sum(row["confidence"] for row in language_rows) / len(language_rows)
                ),
            }
            for language, language_rows in by_language.items()
        ]
        return {"regions": rows, "language_affinity": affinity}

    def get_comparables(self, title_id):
        title_format = self._find_title(title_id)["content_format"]
        rows = []
        for index, item in enumerate(self._result(title_id)["comparable_titles"]):
            rows.append(
                {
                    "id": f"backend_comparable_{index}",
                    "title": item["title"],
                    "year": "-",
                    "format": title_format,
                    "similarity": item["similarity"],
                    "indian_demand": self._strength(item["market_signal"]),
                    "genre_match": self._match(item["similarity"]),
                    "audience_match": self._match(item["similarity"]),
                    "format_match": "Exact",
                    "india_performance": item["market_signal"],
                    "reason": "; ".join(item["reasons"]),
                }
            )
        ids = [item["id"] for item in rows]
        return {
            "comparables": rows,
            "sets": {"expected": ids, "optimistic": ids, "conservative": ids},
        }

    def get_sources(self, title_id):
        rows = []
        for item in self._result(title_id)["source_status"]:
            cached = item["status"] == "cached"
            rows.append(
                {
                    "id": item["source"],
                    "name": item["source"].replace("_", " ").title(),
                    "status": "available" if cached else item["status"],
                    "mode": "cached" if cached else "live" if item["status"] == "available" else "none",
                    "last_collected": item["provenance"].get("collected_at"),
                    "note": " ".join(item["warnings"]),
                    "caveat": "Evidence supplied by the backend analysis snapshot.",
                    "toggleable": False,
                    "effect_if_disabled": {},
                }
            )
        return rows

    def get_recommendation(self, title_id):
        recommendation = self._result(title_id)["recommendation"]
        return {
            "headline": recommendation["decision"],
            "platform": recommendation["platform"],
            "priority_markets": recommendation["priority_markets"],
            "localization": recommendation["localization"],
            "target_audience": recommendation["target_audience"],
            "launch_window": recommendation["launch_window"],
            "positioning": recommendation["marketing_positioning"],
            "campaign": recommendation["campaign_actions"],
            "risks": [
                {"risk": risk, "mitigation": "Validate this risk during the controlled regional pilot."}
                for risk in recommendation["risks"]
            ],
            "items": [],
        }

    def get_scenarios(self, title_id):
        # Static strategy presets still drive the local comparison charts.
        return _fresh("shadow_bloom/scenarios.json")

    def list_backend_scenarios(self, title_id):
        analysis_id = self._analysis(title_id)["id"]
        return self._request("GET", f"/analyses/{analysis_id}/scenarios")

    def create_scenario(self, title_id, payload):
        """Evaluate and persist a what-if scenario against the selected frozen analysis."""
        analysis_id = self._analysis(title_id)["id"]
        return self._request("POST", f"/analyses/{analysis_id}/scenarios", json=payload)

    def start_analysis(self, payload, outcome="normal"):
        del outcome  # Failure simulation belongs to MockApi only.
        errors = intake.validate(payload)
        if errors:
            raise ValueError("; ".join(errors))
        if self._project_id is None:
            project = self._request(
                "POST",
                "/projects",
                json={
                    "name": "Streamlit Analysis Workspace",
                    "description": "Titles submitted from the integrated Streamlit interface.",
                },
            )
            self._project_id = project["id"]
        title = self._request(
            "POST",
            f"/projects/{self._project_id}/titles",
            json=self._title_payload(payload),
        )
        self._titles[title["id"]] = title
        started = self._request("POST", f"/titles/{title['id']}/analyses", json={})
        self._analysis_ids[title["id"]] = started["analysis_id"]
        return started["job_id"]

    def get_job(self, job_id):
        effective_id = self._job_aliases.get(job_id, job_id)
        job = self._request("GET", f"/jobs/{effective_id}")
        status = self._ui_status(job["status"])
        stages = self.get_config()["pipeline_stages"]
        complete_count = min(len(stages), int(job["progress"] / 100 * len(stages)))
        stage_rows = [
            {
                "name": name,
                "state": "done"
                if index < complete_count
                else "failed"
                if status == "failed" and index == complete_count
                else "running"
                if status == "running" and index == complete_count
                else "pending",
            }
            for index, name in enumerate(stages)
        ]
        return {
            "job_id": job_id,
            "title_id": self._request("GET", f"/analyses/{job['analysis_id']}")["title_id"],
            "status": status,
            "progress": job["progress"],
            "stages": stage_rows,
            "sources": [],
            "error": job.get("error_message"),
        }

    def retry_job(self, job_id):
        job = self._request("GET", f"/jobs/{self._job_aliases.get(job_id, job_id)}")
        analysis = self._request("GET", f"/analyses/{job['analysis_id']}")
        started = self._request("POST", f"/titles/{analysis['title_id']}/analyses", json={})
        self._job_aliases[job_id] = started["job_id"]
        self._analysis_ids[analysis["title_id"]] = started["analysis_id"]

    def use_cached_data(self, job_id):
        self.retry_job(job_id)

    @staticmethod
    def _ui_status(status):
        return {
            "completed": "complete",
            "partially_completed": "partial",
            "queued": "running",
        }.get(status, status)

    @staticmethod
    def _strength(value):
        return "High" if value >= 75 else "Medium" if value >= 55 else "Low"

    @staticmethod
    def _match(value):
        return "Strong" if value >= 0.75 else "Moderate" if value >= 0.55 else "Weak"

    @staticmethod
    def _driver_component(name):
        lowered = name.lower()
        return next(
            (
                key
                for key in (
                    "content_fit",
                    "demand_momentum",
                    "regional_opportunity",
                    "engagement_quality",
                    "comparable_performance",
                )
                if key.replace("_", " ") in lowered
            ),
            "content_fit",
        )

    @staticmethod
    def _content_dna(title):
        genres = [title["primary_genre"], *title.get("genres", [])]
        themes = title.get("themes", [])
        return {
            "genres": [
                {"name": value, "weight": max(0.5, 0.9 - index * 0.1)}
                for index, value in enumerate(dict.fromkeys(genres))
            ],
            "themes": [
                {"name": value, "weight": max(0.5, 0.85 - index * 0.1)}
                for index, value in enumerate(themes)
            ],
            "archetypes": [],
            "audience_fit": {"Target-market alignment": 70},
            "sensitivity_flags": [],
        }

    @staticmethod
    def _title_payload(payload):
        trailer = (payload.get("trailer_url") or "").strip() or None
        return {
            "name": payload["title"].strip(),
            "english_title": (payload.get("english_title") or "").strip() or None,
            "synopsis": payload["synopsis"].strip(),
            "content_format": payload["format"],
            "primary_genre": payload["primary_genre"],
            "genres": payload.get("secondary_genres") or [],
            "themes": payload.get("themes") or [],
            "source_material": payload["source_material"],
            "expected_release_period": payload["release_period"],
            "target_platform": payload["target_platform"],
            "target_languages": payload.get("target_languages") or [],
            "target_states": payload.get("target_states") or [],
            "marketing_budget": (payload.get("budget_band") or "medium").lower(),
            "studio": (payload.get("studio") or "").strip() or None,
            "franchise_status": payload.get("franchise_status") or None,
            "trailer_url": trailer,
            "metadata_extra": {
                "director": payload.get("director"),
                "cast": payload.get("cast") or [],
                "age_rating": payload.get("age_rating"),
                "intended_audience": payload.get("intended_audience"),
            },
        }


def build_api(mode=None):
    """Choose live integration when configured/healthy, with a deterministic mock fallback."""
    selected = (mode or FRONTEND_MODE or "auto").lower()
    if selected == "mock":
        return MockApi()
    backend = BackendApi()
    if selected == "live":
        return backend
    if backend.is_available():
        return backend
    backend.close()
    return MockApi()
