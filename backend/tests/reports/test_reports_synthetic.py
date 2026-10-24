"""Report and model-card endpoints on a SYNTHETIC state model.

test_reports.py covers the same routes against a real trained model but is skipped when
models/state is absent (always, in CI). This file keeps the report renderers covered without one.
"""

import csv
import io
import json
import xml.etree.ElementTree as ET
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app.adapters.google_trends import TrendsClient
from app.api.routes import predict as predict_routes
from app.api.routes.predict import get_state_model, get_trends_client
from app.main import app
from app.ml.features import titles_frame
from app.ml.state_model import StateModel
from app.ml.states import PILOT_STATES
from tests.support.ml_data import synthetic

BODY = {
    "name_en": "Blue Amber",
    "name_jp": "ブルーアンバー",
    "genres": ["Comedy", "Fantasy"],
    "tags": ["Magic"],
    "synopsis": "A gang of misfit young mages stumbles through comic misadventures while guarding "
    "a blue amber.",
    "format": "anime_series",
    "release_date": "2030-04-01",
    "episodes": 12,
}


@pytest.fixture(scope="module")
def model():
    records, labels = synthetic(60)
    return StateModel.train(titles_frame(records), labels, PILOT_STATES, min_theme_titles=1)


def fetcher(terms, geo, start, end):
    rows, day = [], start
    while day <= end:
        rows.append(
            {"date": day.isoformat(), "values": {terms[0]: 12, terms[1]: 50}, "partial": False}
        )
        day += timedelta(weeks=1)
    return rows


@pytest.fixture()
def client(model, tmp_path, monkeypatch):
    monkeypatch.setattr(predict_routes.settings, "models_dir", str(tmp_path / "models"))
    app.dependency_overrides[get_state_model] = lambda: model
    app.dependency_overrides[get_trends_client] = lambda: TrendsClient(
        fetcher=fetcher, raw_dir=tmp_path, sleep=lambda s: None
    )
    yield TestClient(app)
    app.dependency_overrides.clear()


def report(client, fmt):
    response = client.post(f"/api/v1/predict/report?format={fmt}", json=BODY)
    assert response.status_code == 200, response.text
    return response


def test_json_and_csv_reports_agree(client):
    rep = json.loads(report(client, "json").content)
    rows = list(csv.DictReader(io.StringIO(report(client, "csv").content.decode("utf-8-sig"))))

    assert len(rows) == len(rep["states"]) == len(PILOT_STATES)
    assert float(rows[0]["success_score"]) == pytest.approx(rep["success"]["score"], abs=1e-6)
    assert rep["formulas"] and rep["limitations"]


def test_xml_report_parses_and_lists_every_state(client):
    root = ET.fromstring(report(client, "xml").content)

    assert root.tag == "kizunaReport"
    assert len(root.findall("./states/state")) == len(PILOT_STATES)


def test_pdf_report_is_a_pdf_with_a_download_name(client):
    pdf = report(client, "pdf")

    assert pdf.content[:5] == b"%PDF-"
    assert pdf.headers["content-disposition"] == 'attachment; filename="kizuna_Blue_Amber.pdf"'


def test_unknown_report_format_is_rejected(client):
    assert client.post("/api/v1/predict/report?format=docx", json=BODY).status_code == 422


def test_model_card_describes_the_loaded_model(client, model):
    card = client.get("/api/v1/model").json()

    assert card["n_states"] == len(card["states"]) == len(PILOT_STATES)
    assert card["limitations"]
    assert all(state["sparse"] == (state["real_titles"] < 20) for state in card["states"])
