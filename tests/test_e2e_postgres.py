"""End to end through the HTTP routes against a real Postgres (JSONB, ARRAY, pgvector, constraints).

Each run creates and drops its own database on the local container (docker-compose.yml), so the dev
data is untouched. Skipped when Postgres is not reachable. The state model is trained on SYNTHETIC
data and Trends is a fake fetcher: this proves the wiring, not model or search quality.
"""
import uuid
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.adapters.google_trends import TrendsClient
from app.db.base import Base
from app.db.models import Job
from app.db.session import get_db
from app.main import app
from app.ml.features import titles_frame
from app.ml.state_model import StateModel
from app.ml.states import PILOT_STATES
from app.services import worker
from tests.test_ml_pipeline import synthetic

ADMIN = "postgresql+psycopg://kizuna:kizuna@localhost:5432/postgres"
TEST = "postgresql+psycopg://kizuna:kizuna@localhost:5432/{}"


@pytest.fixture(scope="module")
def session_factory():
    name = f"kizuna_test_{uuid.uuid4().hex[:8]}"
    admin = create_engine(ADMIN, isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as conn:
            conn.execute(text(f'CREATE DATABASE "{name}"'))
    except Exception as exc:
        pytest.skip(f"Postgres not reachable: {exc}")
    engine = create_engine(TEST.format(name))
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine, autoflush=False)
    engine.dispose()
    with admin.connect() as conn:
        conn.execute(text(f'DROP DATABASE "{name}" WITH (FORCE)'))
    admin.dispose()


@pytest.fixture(scope="module")
def client(session_factory):
    def override():
        with session_factory() as db:
            yield db

    app.dependency_overrides[get_db] = override
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture(scope="module")
def model():
    records, labels = synthetic(60)
    return StateModel.train(titles_frame(records), labels, PILOT_STATES, min_theme_titles=1)


def fake_fetcher(terms, geo, start, end):
    """Hindi-dub queries beat '<name> anime', which beats the bare name; anchor is flat."""
    level = 40 if "Hindi dubbed" in terms[0] else 25 if "anime" in terms[0] else 10
    rows, day = [], start
    while day <= end:
        rows.append({"date": day.isoformat(), "values": {terms[0]: level, terms[1]: 50}, "partial": False})
        day += timedelta(weeks=1)
    rows[-1]["partial"] = True
    return rows


@pytest.fixture()
def trends(tmp_path):
    return TrendsClient(fetcher=fake_fetcher, raw_dir=tmp_path, sleep=lambda s: None)


def run_worker(session_factory, model, trends):
    with session_factory() as db:
        return worker.process_all(db, model, trends)


@pytest.fixture(scope="module")
def ids(client):
    project = client.post("/api/v1/projects", json={"name": "E2E"}).json()
    title = client.post("/api/v1/titles", json={
        "project_id": project["id"], "name_en": "Test Show Season 2", "name_jp": "テストショー",
        "synopsis": "A sword hero battles a demon war across a ruined kingdom " * 2,
        "genres": ["Action"], "format": "anime_series", "studio": "Studio A"}).json()
    return {"project": project["id"], "title": title["id"]}


def test_analysis_flow_idempotent_create_then_worker_fills_regions(client, session_factory, model, trends, ids):
    t = ids["title"]
    assert client.post(f"/api/v1/titles/{t}/analyse").status_code == 422  # no assumptions yet
    assumption = {"distribution_model": "ott", "localization_mode": "subtitled_and_dubbed", "languages": ["hi", "ta"],
                  "launch_geography": "selected_states", "target_states": ["IN-MH"],
                  "planned_launch_date": "2030-01-01"}
    assert client.put(f"/api/v1/titles/{t}/assumptions", json=assumption).status_code == 200
    assert client.get(f"/api/v1/titles/{t}/assumptions").json()["languages"] == ["hi", "ta"]  # ARRAY round trip

    first = client.post(f"/api/v1/titles/{t}/analyse", headers={"Idempotency-Key": "k1"})
    again = client.post(f"/api/v1/titles/{t}/analyse", headers={"Idempotency-Key": "k1"})
    assert (first.status_code, again.status_code) == (202, 200) and first.json()["id"] == again.json()["id"]
    aid = first.json()["id"]
    assert client.get(f"/api/v1/analyses/{aid}/regions").status_code == 409  # not finished yet

    assert run_worker(session_factory, model, trends)["analysis"] == 1
    analysis = client.get(f"/api/v1/analyses/{aid}").json()
    assert analysis["status"] == "succeeded" and analysis["result_version"] == model.version
    assert analysis["market_potential"] is None and 0 <= analysis["confidence"] <= 100
    assert "small_training_set" in analysis["warning_codes"]  # ARRAY column
    regions = client.get(f"/api/v1/analyses/{aid}/regions").json()
    assert [r["rank"] for r in regions] == list(range(1, len(PILOT_STATES) + 1))
    assert [r["score"] for r in regions] == sorted((r["score"] for r in regions), reverse=True)
    assert {r["region_code"] for r in regions if r["evidence"][0]["in_target"]} == {"IN-MH"}  # JSONB round trip
    job = client.get(f"/api/v1/jobs/{analysis['job_id']}").json()
    assert job["status"] == "succeeded" and job["result"]["analysis_id"] == aid
    assert run_worker(session_factory, model, trends)["analysis"] == 0  # nothing re-processed


def test_seo_route_ranks_terms_and_links_to_state_analysis(client, session_factory, model, trends, ids):
    t = ids["title"]
    assert client.get(f"/api/v1/titles/{t}/seo").status_code == 404  # never requested
    assert client.post("/api/v1/titles/99999/seo").status_code == 404
    first = client.post(f"/api/v1/titles/{t}/seo", headers={"Idempotency-Key": "s1"})
    again = client.post(f"/api/v1/titles/{t}/seo", headers={"Idempotency-Key": "s1"})
    other = client.post(f"/api/v1/titles/{t}/seo", headers={"Idempotency-Key": "s2"})
    assert (first.status_code, again.status_code) == (202, 200)
    assert first.json()["id"] == again.json()["id"] != other.json()["id"]
    assert first.json()["job_type"] == "seo"
    assert client.get(f"/api/v1/titles/{t}/seo").status_code == 409  # latest job (s2) not run yet

    assert run_worker(session_factory, model, trends)["seo"] == 2
    seo = client.get(f"/api/v1/titles/{t}/seo").json()
    assert seo["best_term"] == "Test Show Hindi dubbed"  # from the languages/localization assumptions
    assert seo["best_by_variant"]["dub"] == "Test Show Hindi dubbed"
    terms = [c["term"] for c in seo["candidates"] if c["status"] == "ok"]
    assert terms[0] == "Test Show Hindi dubbed" and "Test Show Tamil dubbed" in terms and "Test Show" in terms
    assert any(c["variant"] == "japanese" for c in seo["candidates"])
    assert len(seo["state_focus"]) == 3 and all(f["term_ratio"] is not None for f in seo["state_focus"])
    assert "no_completed_state_analysis" not in seo["warnings"]
    assert "search volume" in seo["not_available"]


def test_collection_job_records_provenance_and_unavailable_sources(client, session_factory, model, trends, ids):
    t = ids["title"]
    job = client.post("/api/v1/sources/collect", json={"title_id": t, "sources": ["google_trends", "anilist"]})
    assert job.status_code == 202 and job.json()["job_type"] == "collection"
    assert run_worker(session_factory, model, trends)["collection"] == 1
    runs = {r["source_id"]: r for r in client.get(f"/api/v1/sources/runs?title_id={t}").json()}
    health = {s["name"]: s for s in client.get("/api/v1/sources/health").json()}
    assert health["google_trends"]["health"] == "ok" and health["anilist"]["health"] == "unavailable"
    assert health["anilist"]["last_error"] == "no_adapter_for_database_titles"
    trends_run = next(r for r in runs.values() if r["raw_checksum"])
    assert trends_run["record_count"] > 0 and trends_run["health"] == "ok"
    assert client.get(f"/api/v1/jobs/{job.json()['id']}").json()["result"] == {
        "google_trends": "ok", "anilist": "no_adapter"}
    assert client.post("/api/v1/sources/collect", json={"title_id": t, "sources": ["tiktok"]}).status_code == 422


def test_blocked_trends_marks_seo_job_with_partial_warning(client, session_factory, model, ids, tmp_path):
    from app.adapters.google_trends import RateLimited

    def blocked(*a):
        raise RateLimited("429")

    t = ids["title"]
    job = client.post(f"/api/v1/titles/{t}/seo", headers={"Idempotency-Key": "blocked"}).json()
    run_worker(session_factory, model, TrendsClient(fetcher=blocked, raw_dir=tmp_path, sleep=lambda s: None))
    seo = client.get(f"/api/v1/titles/{t}/seo").json()
    assert seo["job_id"] == job["id"] and seo["best_term"] is None
    assert {"no_signal_any_term", "trends_blocked_partial_results"} <= set(seo["warnings"])


def test_a_crash_inside_a_job_is_recorded_not_raised(client, session_factory, model, ids, tmp_path):
    def boom(*a):
        raise RuntimeError("fetcher exploded")

    t = ids["title"]
    job = client.post(f"/api/v1/titles/{t}/seo", headers={"Idempotency-Key": "crash"}).json()
    # score_term only catches Trends errors; a programming error must still end in a failed job.
    run_worker(session_factory, model, TrendsClient(fetcher=boom, raw_dir=tmp_path, sleep=lambda s: None))
    stored = client.get(f"/api/v1/jobs/{job['id']}").json()
    assert stored["status"] == "failed" and stored["error_code"] == "RuntimeError"
    assert client.get(f"/api/v1/titles/{t}/seo").status_code == 409
