from __future__ import annotations

import json

import pytest

from app.core.paths import OPENAPI_SNAPSHOT
from app.main import app


@pytest.mark.contract
def test_openapi_is_valid_and_matches_committed_snapshot():
    schema = app.openapi()
    assert schema["openapi"].startswith("3.")
    assert schema["paths"]
    assert json.loads(OPENAPI_SNAPSHOT.read_text(encoding="utf-8")) == schema


@pytest.mark.contract
def test_all_business_endpoints_are_versioned():
    paths = app.openapi()["paths"]
    assert all(path.startswith("/api/v1") for path in paths)


@pytest.mark.contract
def test_public_operations_declare_json_responses():
    verbs = {"get", "post", "put", "patch", "delete"}
    for path, path_item in app.openapi()["paths"].items():
        for verb, operation in path_item.items():
            if verb not in verbs:
                continue
            assert operation.get("responses"), f"{verb.upper()} {path} has no response contract"


@pytest.mark.contract
def test_contract_enums_are_stable():
    schemas = app.openapi()["components"]["schemas"]
    confidence = schemas["AnalysisResult"]["properties"]["confidence_level"]
    source_status = schemas["SourceStatus"]["properties"]["status"]
    decision = schemas["AnalysisResult"]["properties"]["decision_classification"]
    assert set(confidence["enum"]) == {"low", "medium", "high"}
    assert set(source_status["enum"]) == {"available", "cached", "unavailable"}
    assert set(decision["enum"]) == {
        "strong_opportunity",
        "promising_opportunity",
        "test_before_investing",
        "limited_opportunity",
        "insufficient_evidence",
    }
