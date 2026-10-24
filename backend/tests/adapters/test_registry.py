from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.core.config import Settings
from app.services.sources.registry import SourceRegistry

pytestmark = pytest.mark.adapters


def test_demo_mode_keeps_every_source_on_demo():
    registry = SourceRegistry(Settings(demo_mode=True, youtube_api_key="k"))

    assert {registry.mode_for(name) for name in registry.SOURCE_NAMES} == {"demo"}


def test_live_mode_runs_every_source_live_when_configured():
    registry = SourceRegistry(Settings(demo_mode=False, youtube_api_key="k"))

    assert {registry.mode_for(name) for name in registry.SOURCE_NAMES} == {"live"}


def test_unconfigured_source_is_unavailable_never_demo_data():
    registry = SourceRegistry(Settings(demo_mode=False, youtube_api_key=""))
    title = SimpleNamespace(name="Frieren")

    assert registry.mode_for("youtube") == "unconfigured"
    evidence = registry._collect_one("youtube", title, client=None, disabled_sources=set())

    assert evidence.status == "unavailable"
    assert evidence.metrics == {}
    assert "not configured" in evidence.warnings[0]
    assert evidence.provenance["mode"] == "unavailable"


def test_a_crashing_adapter_degrades_instead_of_failing_the_analysis(monkeypatch):
    class Boom:
        def collect(self, title):
            raise RuntimeError("kaboom")

    monkeypatch.setitem(
        __import__("app.services.sources.registry", fromlist=["x"]).LIVE_ADAPTERS,
        "wikimedia",
        lambda client, settings: Boom(),
    )
    registry = SourceRegistry(Settings(demo_mode=False, youtube_api_key="k"))

    evidence = registry._collect_one(
        "wikimedia", SimpleNamespace(name="x"), client=None, disabled_sources=set()
    )

    assert evidence.status == "unavailable"
    assert "failed unexpectedly" in evidence.warnings[0]
    assert "kaboom" not in evidence.warnings[0]  # exception text stays in the server log


def regional_title():
    return SimpleNamespace(
        name="Shadow Bloom",
        english_title="Shadow Bloom",
        primary_genre="fantasy",
        genres=["fantasy", "action"],
        themes=[],
        target_languages=["Tamil"],
        target_states=["Kerala"],
        content_format="anime_series",
    )


def collect_regional(settings):
    return SourceRegistry(settings)._collect_one(
        "regional_context", regional_title(), client=None, disabled_sources=set()
    )


@pytest.mark.parametrize("demo_mode", [True, False])
def test_default_survey_is_the_synthetic_data_in_both_modes_and_flagged_as_proxy(demo_mode):
    evidence = collect_regional(Settings(demo_mode=demo_mode))

    assert int(evidence.provenance["survey_rows"]) > 0
    assert "genre_affinity" in evidence.metrics
    assert evidence.regional
    assert "PROXY synthetic" in evidence.provenance["survey_sources"]
    assert evidence.quality_score == 0.75
    assert any("exploratory proxies" in warning for warning in evidence.warnings)


@pytest.mark.parametrize("demo_mode", [True, False])
def test_pointing_survey_dir_elsewhere_excludes_the_synthetic_data(demo_mode, tmp_path):
    evidence = collect_regional(Settings(demo_mode=demo_mode, survey_dir=str(tmp_path)))

    assert evidence.status == "available"
    assert evidence.provenance["survey_rows"] == "0"
    assert "genre_affinity" not in evidence.metrics
    assert not evidence.regional
    assert any("No survey data loaded" in warning for warning in evidence.warnings)


def test_missing_survey_folder_degrades_without_failing():
    evidence = collect_regional(Settings(demo_mode=True, survey_dir="data/does-not-exist"))

    assert evidence.status == "available"
    assert evidence.provenance["survey_rows"] == "0"
