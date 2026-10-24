import csv
import io
import json
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app

pytestmark = pytest.mark.skipif(
    not Path("models/state/LATEST.json").exists(), reason="no trained state model"
)

BODY = {
    "name_en": "Blue Amber",
    "name_jp": "ブルーアンバー",
    "genres": ["Comedy", "Fantasy"],
    "tags": ["Magic"],
    "synopsis": "A gang of misfit young mages stumbles through comic misadventures while guarding a blue amber.",
    "format": "anime_series",
    "release_date": "2026-10-24",
    "episodes": 12,
}


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def _get(client, fmt):
    r = client.post(f"/api/v1/predict/report?format={fmt}", json=BODY)
    assert r.status_code == 200, r.text
    return r


def test_success_score_bounds_and_gating(client):
    s = client.post("/api/v1/predict", json=BODY).json()["success"]
    assert 0 <= s["low"] <= s["score"] <= s["high"] <= 100
    counted = [c for c in s["components"] if c["status"] == "ok"]
    assert s["coverage"] == pytest.approx(sum(c["weight"] for c in counted))
    assert all(c["value"] is None for c in s["components"] if c["status"] == "unavailable")
    assert all(
        c["validation_spearman"] < 0.1 for c in s["components"] if c["status"] == "unvalidated"
    )


def test_json_and_csv_agree(client):
    rep = json.loads(_get(client, "json").content)
    rows = list(csv.DictReader(io.StringIO(_get(client, "csv").content.decode("utf-8-sig"))))
    assert len(rows) == len(rep["states"])
    assert float(rows[0]["success_score"]) == pytest.approx(rep["success"]["score"], abs=1e-6)
    assert rep["formulas"] and rep["limitations"]


def test_xml_parses_and_pdf_is_a_pdf(client):
    root = ET.fromstring(_get(client, "xml").content)
    assert root.tag == "kizunaReport"
    assert len(root.findall("./states/state")) == len(
        json.loads(_get(client, "json").content)["states"]
    )
    pdf = _get(client, "pdf")
    assert pdf.content[:5] == b"%PDF-" and pdf.headers["content-disposition"].endswith('.pdf"')


def test_model_card_lists_every_state_and_the_synthetic_comparison(client):
    card = client.get("/api/v1/model").json()
    assert card["n_states"] == len(card["states"]) and card["limitations"]
    td = card["training_data"]
    if td["synthetic_used"]:
        assert td["synthetic_rows"] == sum(s["synthetic_rows"] for s in card["states"])
        assert set(td["comparison"]) == {"real_only", "augmented"}
    assert all(s["sparse"] == (s["real_titles"] < 20) for s in card["states"])


def test_predict_exposes_synthetic_rows_and_warning(client):
    out = client.post("/api/v1/predict", json=BODY).json()
    card = client.get("/api/v1/model").json()
    used = card["training_data"]["synthetic_used"]
    assert ("synthetic_augmented" in out["india"]["warnings"]) == used
    assert all("synthetic_rows" in s for s in out["states"])
