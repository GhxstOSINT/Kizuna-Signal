from __future__ import annotations

import pytest

from app.db.models import Title
from app.db.session import SessionLocal
from app.services.analysis import create_analysis, update_job


@pytest.mark.integration
def test_result_before_completion_returns_structured_409(client, created_title):
    with SessionLocal() as db:
        title = db.get(Title, created_title["id"])
        analysis, _ = create_analysis(db, title)

    response = client.get(f"/api/v1/analyses/{analysis.id}/result")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"


@pytest.mark.integration
def test_job_progress_is_monotonic_and_bounded(created_title):
    with SessionLocal() as db:
        title = db.get(Title, created_title["id"])
        _, job = create_analysis(db, title)
        update_job(db, job, 50, "halfway")
        update_job(db, job, 20, "late stale update")
        db.refresh(job)
        assert job.progress == 50
        update_job(db, job, 150, "complete")
        db.refresh(job)
        assert job.progress == 100


@pytest.mark.integration
def test_scenario_is_persisted_and_does_not_mutate_base(client, created_title):
    started = client.post(f"/api/v1/titles/{created_title['id']}/analyses").json()
    analysis_id = started["analysis_id"]
    before = client.get(f"/api/v1/analyses/{analysis_id}/result").json()

    scenario = client.post(
        f"/api/v1/analyses/{analysis_id}/scenarios",
        json={
            "name": "Dub expansion",
            "target_platform": "theatrical",
            "localization_mode": "multilingual_dub",
            "target_languages": ["Hindi", "Tamil", "Telugu", "Bengali"],
        },
    )
    assert scenario.status_code == 201

    after = client.get(f"/api/v1/analyses/{analysis_id}/result").json()
    listed = client.get(f"/api/v1/analyses/{analysis_id}/scenarios").json()
    assert after == before
    assert len(listed) == 1
    assert listed[0]["id"] == scenario.json()["id"]
