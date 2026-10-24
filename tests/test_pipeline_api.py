from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import String, UniqueConstraint, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from app.api.routes import analyses as analyses_routes
from app.api.routes import reports as reports_routes
from app.db.session import get_db
from app.main import app
from app.schemas.completeness import CompletenessReport, MissingItem
from app.schemas.pipeline import ScenarioOverrides
from app.services import analyses as analysis_service
from app.services import completeness as completeness_service
from app.services import idempotency
from app.services import reports as report_service
from app.services import sources as source_service
from app.services import titles as title_service

client = TestClient(app)
NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def no_database():
    app.dependency_overrides[get_db] = lambda: None
    yield
    app.dependency_overrides.clear()


def analysis_row(status="queued", **kw):
    base = dict(
        id=1, title_id=7, job_id=3, status=status, result_version=None,
        market_potential=None, confidence=None, warning_codes=[], provenance_summary={},
        disabled_sources=[], created_at=NOW, completed_at=None,
    )
    return SimpleNamespace(**{**base, **kw})


# --- scenario overrides ------------------------------------------------------
@pytest.mark.parametrize(
    "overrides",
    [
        {},
        {"budget": 5},  # unknown lever
        {"languages": ["hindi"]},
        {"disabled_sources": ["tiktok"]},
        {"launch_geography": "national", "target_states": ["Kerala"]},
        {"distribution_model": "cable"},
    ],
)
def test_bad_overrides_rejected(overrides):
    with pytest.raises(ValidationError):
        ScenarioOverrides(**overrides)


def test_good_overrides_normalised():
    o = ScenarioOverrides(languages=["HI", "ta"], disabled_sources=["youtube", "youtube"])
    assert o.languages == ["hi", "ta"] and o.disabled_sources == ["youtube"]


def test_scenario_body_validated_at_route():
    r = client.post("/api/v1/analyses/1/scenarios", json={"name": "x", "overrides": {}})
    assert r.status_code == 422


# --- sources -----------------------------------------------------------------
def test_collect_rejects_unknown_source():
    r = client.post("/api/v1/sources/collect", json={"title_id": 1, "sources": ["tiktok"]})
    assert r.status_code == 422


def test_collect_rejects_disabled_source(monkeypatch):
    sources = [SimpleNamespace(name="youtube", enabled=False), SimpleNamespace(name="anilist", enabled=True)]
    monkeypatch.setattr(source_service, "list_all", lambda db: sources)
    with pytest.raises(ValueError, match="youtube"):
        source_service.request_collection(None, 1, ["youtube"])


# --- analyse gating + idempotency -------------------------------------------
def test_analyse_blocked_until_intake_complete(monkeypatch):
    monkeypatch.setattr(title_service, "get", lambda db, i: SimpleNamespace(id=i))
    incomplete = CompletenessReport(
        ready_for_analysis=False, score=0.2,
        missing_required=[MissingItem(field="synopsis", message="Missing synopsis")],
        missing_recommended=[],
    )
    monkeypatch.setattr(completeness_service, "for_title", lambda db, t: incomplete)
    r = client.post("/api/v1/titles/7/analyse")
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "incomplete_title"
    assert r.json()["detail"]["missing_required"][0]["field"] == "synopsis"


@pytest.mark.parametrize("created,expected", [(True, 202), (False, 200)])
def test_analyse_status_reflects_replay(monkeypatch, created, expected):
    monkeypatch.setattr(title_service, "get", lambda db, i: SimpleNamespace(id=i))
    ready = CompletenessReport(ready_for_analysis=True, score=1, missing_required=[], missing_recommended=[])
    monkeypatch.setattr(completeness_service, "for_title", lambda db, t: ready)
    seen = {}

    def fake_request(db, title_id, key):
        seen["key"] = key
        return analysis_row(), created

    monkeypatch.setattr(analysis_service, "request", fake_request)
    r = client.post("/api/v1/titles/7/analyse", headers={"Idempotency-Key": "abc"})
    assert r.status_code == expected and seen["key"] == "abc"
    body = r.json()
    for field in ("result_version", "confidence", "provenance_summary", "warning_codes"):
        assert field in body


def test_empty_idempotency_key_rejected():
    assert client.post("/api/v1/titles/7/analyse", headers={"Idempotency-Key": ""}).status_code == 422


def test_unknown_title_is_404(monkeypatch):
    monkeypatch.setattr(title_service, "get", lambda db, i: None)
    assert client.post("/api/v1/titles/7/analyse").status_code == 404


# --- results only after completion ------------------------------------------
@pytest.mark.parametrize("path", ["regions", "recommendation"])
def test_results_conflict_until_analysis_succeeds(monkeypatch, path):
    monkeypatch.setattr(analysis_service, "get", lambda db, i: analysis_row("running"))
    assert client.get(f"/api/v1/analyses/1/{path}").status_code == 409


def test_scenario_conflict_until_analysis_succeeds(monkeypatch):
    monkeypatch.setattr(analysis_service, "get", lambda db, i: analysis_row("queued"))
    body = {"name": "dub", "overrides": {"localization_mode": "dubbed"}}
    assert client.post("/api/v1/analyses/1/scenarios", json=body).status_code == 409


def test_report_requires_succeeded_analysis(monkeypatch):
    monkeypatch.setattr(reports_routes.analysis_service, "get", lambda db, i: analysis_row("failed"))
    assert client.post("/api/v1/reports", json={"analysis_id": 1}).status_code == 409


def test_report_replay_returns_200(monkeypatch):
    monkeypatch.setattr(reports_routes.analysis_service, "get", lambda db, i: analysis_row("succeeded"))
    report = SimpleNamespace(
        id=1, analysis_id=1, job_id=2, format="pdf", status="queued", file_uri=None, created_at=NOW
    )
    monkeypatch.setattr(report_service, "request", lambda db, body, key: (report, False))
    assert client.post("/api/v1/reports", json={"analysis_id": 1}).status_code == 200


def test_report_format_validated():
    assert client.post("/api/v1/reports", json={"analysis_id": 1, "format": "docx"}).status_code == 422


# --- recommendations ---------------------------------------------------------
@pytest.mark.parametrize(
    "body",
    [{"status": "draft", "decided_by": "a"}, {"status": "accepted"}, {"status": "accepted", "decided_by": ""}],
)
def test_decision_needs_explicit_human_approval(body):
    assert client.post("/api/v1/recommendations/1/decision", json=body).status_code == 422


# --- idempotency helper against a real (SQLite) table -----------------------
class _Base(DeclarativeBase):
    pass


class _Thing(_Base):
    __tablename__ = "things"
    __table_args__ = (UniqueConstraint("scope_id", "idempotency_key"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    scope_id: Mapped[int]
    idempotency_key: Mapped[str | None] = mapped_column(String(128))


def test_create_once_replays_same_key():
    engine = create_engine("sqlite://")
    _Base.metadata.create_all(engine)
    with Session(engine) as db:
        build = lambda: _Thing(scope_id=1, idempotency_key="k")  # noqa: E731
        first, created1 = idempotency.create_once(db, _Thing, {"scope_id": 1}, "k", build)
        again, created2 = idempotency.create_once(db, _Thing, {"scope_id": 1}, "k", build)
        other, created3 = idempotency.create_once(
            db, _Thing, {"scope_id": 2}, "k", lambda: _Thing(scope_id=2, idempotency_key="k")
        )
        ids = (first.id, again.id, other.id)
    assert (created1, created2, created3) == (True, False, True)
    assert ids[0] == ids[1] and ids[2] != ids[0]


def test_create_once_without_key_always_creates():
    engine = create_engine("sqlite://")
    _Base.metadata.create_all(engine)
    with Session(engine) as db:
        build = lambda: _Thing(scope_id=1)  # noqa: E731
        a, _ = idempotency.create_once(db, _Thing, {"scope_id": 1}, None, build)
        b, _ = idempotency.create_once(db, _Thing, {"scope_id": 1}, None, build)
        assert a.id != b.id
