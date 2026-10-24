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
