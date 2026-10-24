from __future__ import annotations

import json

import httpx
import pytest

from kizuna import engine
from kizuna.api import BackendApi, MockApi, build_api


def response(payload, status=200):
    return httpx.Response(status, json=payload)


@pytest.fixture
def frontend_payload():
    return {
        "title": "Integrated Title",
        "english_title": "Integrated Title",
        "synopsis": "A sufficiently detailed synopsis used to verify the frontend backend boundary.",
        "format": "Film",
        "primary_genre": "Fantasy",
        "secondary_genres": ["Drama"],
        "themes": ["Friendship"],
        "source_material": "Original",
        "release_period": "2027-Q1",
        "target_platform": "OTT",
        "target_languages": ["Hindi"],
        "target_states": ["Maharashtra"],
        "budget_band": "Medium",
        "studio": "Studio",
        "franchise_status": "New IP",
        "trailer_url": "",
    }


@pytest.mark.integration
def test_frontend_submission_uses_versioned_backend_contract(frontend_payload):
    seen = []

    def handler(request):
        seen.append((request.method, request.url.path, json.loads(request.content or b"{}")))
        if request.url.path.endswith("/projects"):
            return response({"id": "p1"}, 201)
        if request.url.path.endswith("/projects/p1/titles"):
            body = json.loads(request.content)
            return response({"id": "t1", **body}, 201)
        if request.url.path.endswith("/titles/t1/analyses"):
            return response({"analysis_id": "a1", "job_id": "j1", "status": "queued"}, 202)
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    api = BackendApi(
        base_url="https://backend.test/api/v1",
        transport=httpx.MockTransport(handler),
    )
    assert api.start_analysis(frontend_payload) == "j1"
    title_request = next(item for item in seen if item[1].endswith("/projects/p1/titles"))
    assert title_request[2]["name"] == frontend_payload["title"]
    assert title_request[2]["content_format"] == frontend_payload["format"]
    assert title_request[2]["marketing_budget"] == "medium"


@pytest.mark.integration
def test_frontend_job_status_is_translated():
    def handler(request):
        if request.url.path.endswith("/jobs/j1"):
            return response(
                {
                    "analysis_id": "a1",
                    "status": "partially_completed",
                    "progress": 100,
                    "error_message": None,
                }
            )
        if request.url.path.endswith("/analyses/a1"):
            return response({"title_id": "t1"})
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    api = BackendApi(
        base_url="https://backend.test/api/v1",
        transport=httpx.MockTransport(handler),
    )
    job = api.get_job("j1")
    assert job["status"] == "partial"
    assert job["title_id"] == "t1"
    assert job["progress"] == 100


@pytest.mark.integration
def test_explicit_mock_mode_remains_available():
    assert isinstance(build_api("mock"), MockApi)


@pytest.mark.integration
def test_real_backend_result_maps_to_dashboard_contract(client, frontend_payload):
    def bridge(request):
        forwarded = client.request(
            request.method,
            request.url.raw_path.decode(),
            content=request.content,
            headers={"content-type": request.headers.get("content-type", "application/json")},
        )
        return httpx.Response(
            forwarded.status_code,
            content=forwarded.content,
            headers=dict(forwarded.headers),
        )

    api = BackendApi(
        base_url="https://backend.test/api/v1",
        transport=httpx.MockTransport(bridge),
    )
    job_id = api.start_analysis(frontend_payload)
    job = api.get_job(job_id)
    assert job["status"] == "complete"

    title_id = job["title_id"]
    analysis = api.get_analysis(title_id)
    sources = api.get_sources(title_id)
    comparables = api.get_comparables(title_id)
    regions = api.get_regions(title_id)
    recommendation = api.get_recommendation(title_id)
    view = engine.compute_view(analysis, sources, comparables, api.get_config())

    assert view["overall"] == analysis["_authoritative"]["score"]
    assert view["confidence"] == analysis["_authoritative"]["confidence"]
    assert len(comparables["comparables"]) == 5
    assert regions["regions"]
    assert sources
    assert recommendation["priority_markets"]
