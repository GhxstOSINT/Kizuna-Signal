"""Live-mode analysis with fake adapters: nothing synthetic may reach a live result."""

from __future__ import annotations

import pytest

from app.core.config import get_settings
from app.services.sources import registry as registry_module
from app.services.sources.base import SourceEvidence

pytestmark = pytest.mark.e2e


class FakeLive:
    def __init__(self, source, metrics, **kwargs):
        self.source, self.metrics, self.kwargs = source, metrics, kwargs

    def collect(self, title):
        return SourceEvidence(
            self.source,
            "available",
            1.0,
            0.9,
            self.metrics,
            provenance={"mode": "live", **self.kwargs.pop("provenance", {})},
            **self.kwargs,
        )


COMPARABLES = [
    {"title": f"Real Show {i}", "similarity": 0.7, "market_signal": 70.0, "reasons": ["Genre"]}
    for i in range(5)
]


@pytest.fixture
def live_mode(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "demo_mode", False)
    monkeypatch.setattr(settings, "youtube_api_key", "")  # unconfigured => unavailable
    adapters = {
        "google_trends": lambda c, s: FakeLive(
            "google_trends",
            {"relative_interest": 55, "momentum": 60},
            regional={"Maharashtra": {"interest": 70.0}, "Tamil Nadu": {"interest": 50.0}},
        ),
        "wikimedia": lambda c, s: FakeLive("wikimedia", {"curiosity": 65}),
        "anilist": lambda c, s: FakeLive(
            "anilist", {"community_strength": 75}, comparables=COMPARABLES
        ),
        "regional_context": lambda c, s: FakeLive(
            "regional_context",
            {"language_fit": 80, "addressable_market": 80},
            provenance={"mode": "static-census"},
        ),
    }
    monkeypatch.setattr(
        registry_module, "LIVE_ADAPTERS", {**registry_module.LIVE_ADAPTERS, **adapters}
    )


def run(client, title_id, payload=None):
    started = client.post(f"/api/v1/titles/{title_id}/analyses", json=payload or {})
    assert started.status_code == 202, started.text
    analysis = client.get(f"/api/v1/analyses/{started.json()['analysis_id']}")
    assert analysis.status_code == 200
    return analysis.json()


def test_live_analysis_has_no_demo_evidence_and_uses_real_comparables_and_states(
    client, created_title, live_mode
):
    analysis = run(client, created_title["id"])
    result = analysis["result"]
    status = {s["source"]: s for s in result["source_status"]}

    assert not any("offline-demo" in s["provenance"].get("mode", "") for s in status.values())
    assert status["youtube"]["status"] == "unavailable"
    assert status["youtube"]["provenance"]["mode"] == "unavailable"
    assert analysis["status"] == "partially_completed"

    assert [c["title"] for c in result["comparable_titles"]] == [c["title"] for c in COMPARABLES]
    assert len(result["regional_scores"]) == 36
    reasons = {r["state"]: r["reasons"] for r in result["regional_scores"]}
    assert any("Google Trends interest 70/100" in r for r in reasons["Maharashtra"])
    assert any("Analysis completed without: youtube" in w for w in result["data_quality_warnings"])
    assert result["recommendation"]["priority_markets"]
    assert result["component_scores"]["engagement_quality"] == 75.0  # AniList alone; no YouTube


def test_live_mode_without_any_demand_evidence_is_flagged_insufficient(
    client, created_title, monkeypatch, live_mode
):
    adapters = dict(registry_module.LIVE_ADAPTERS)
    for name in ("google_trends", "wikimedia"):
        adapters[name] = lambda c, s, name=name: type(
            "Down", (), {"collect": lambda self, t: SourceEvidence(name, "unavailable", 0, 0, {})}
        )()
    # Title not listed on AniList: comparables only, no community-strength signal.
    adapters["anilist"] = lambda c, s: FakeLive(
        "anilist", {"comparable_pool": 5}, comparables=COMPARABLES
    )
    monkeypatch.setattr(registry_module, "LIVE_ADAPTERS", adapters)

    result = run(client, created_title["id"])["result"]

    assert result["decision_classification"] == "insufficient_evidence"
    assert result["confidence_level"] == "low"
    assert any(
        "No title-specific demand or engagement" in w for w in result["data_quality_warnings"]
    )
