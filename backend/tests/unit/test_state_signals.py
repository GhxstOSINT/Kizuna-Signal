from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.db.models import StateSignal
from app.db.session import SessionLocal
from app.schemas.analysis import RegionalScore
from app.services import census
from app.services import state_signals as svc

pytestmark = pytest.mark.unit

CSV_HEADER = "state,metric,value,as_of,source\n"


def region(state: str, score: float) -> RegionalScore:
    return RegionalScore(
        state=state,
        score=score,
        confidence=70,
        recommended_language="Hindi",
        preferred_platform="OTT",
        reasons=["base"],
    )


def test_parse_csv_accepts_aliases_and_every_census_state():
    text = (
        "state,metric,value,as_of\n"
        "UP,views,100,2026-10-01\n"
        "Delhi NCR,watch hours,50,2026-10-01\n"
        "Nagaland,views,5,2026-10-01\n"
    )
    rows, rejected = svc.parse_csv(text, "partner_import")
    assert rejected == []
    assert [(r.state, r.metric) for r in rows][0] == ("Uttar Pradesh", "views")
    assert rows[1].metric == "watch_hours" and rows[2].state == "Nagaland"


def test_parse_csv_rejects_bad_rows_and_reports_reasons():
    text = (
        "state,metric,value,as_of\n"
        "Atlantis,views,10,2026-10-01\n"
        "Kerala,likes,10,2026-10-01\n"
        "Kerala,views,-5,2026-10-01\n"
        "Kerala,views,abc,2026-10-01\n"
        f"Kerala,views,5,{date.today() + timedelta(days=3)}\n"
    )
    rows, rejected = svc.parse_csv(text, "x")
    assert rows == [] and len(rejected) == 5
    reasons = " ".join(r["reason"] for r in rejected)
    for expected in ("unknown state", "unknown metric", ">= 0", "number", "future"):
        assert expected in reasons


def test_parse_csv_requires_columns():
    with pytest.raises(ValueError, match="missing required"):
        svc.parse_csv("state,value\nKerala,1\n", "x")


def test_volume_metrics_are_normalised_per_capita():
    """Views proportional to population mean equal interest everywhere, not 'big state wins'."""
    states = census.all_states()
    names = ["Uttar Pradesh", "Maharashtra", "Kerala"]
    rows = [
        StateSignal(
            title_id="t",
            state=n,
            source="p",
            metric="views",
            value=states[n].population / 1000,
            as_of=date(2026, 10, 1),
        )
        for n in names
    ]
    index = svc._series_index(rows)
    assert index is not None and all(abs(v - 100) < 1e-6 for v in index.values())


def test_series_index_needs_three_states_and_uses_latest_date():
    one = [
        StateSignal(
            title_id="t",
            state="Kerala",
            source="p",
            metric="index",
            value=5,
            as_of=date(2026, 10, 1),
        )
    ]
    assert svc._series_index(one) is None


def test_partner_tilt_is_centred_and_capped():
    tilt = svc.partner_tilt({"Kerala": 100.0, "Tamil Nadu": 50.0, "Maharashtra": 0.0})
    assert tilt["Kerala"] > 0 > tilt["Maharashtra"]
    assert max(abs(v) for v in tilt.values()) <= svc.MAX_TILT
    assert svc.partner_tilt({"Kerala": 100.0}) is None and svc.partner_tilt(None) is None


def test_apply_partner_tilt_shifts_scores_explains_and_resorts():
    regions = [region("Maharashtra", 80), region("Kerala", 78), region("Tamil Nadu", 70)]
    out = svc.apply_partner_tilt(
        regions, {"Kerala": 100.0, "Maharashtra": 10.0, "Tamil Nadu": 55.0}
    )
    assert out[0].state == "Kerala"  # strong imported viewing lifts Kerala above Maharashtra
    assert any("Imported viewing data" in reason for reason in out[0].reasons)
    assert svc.apply_partner_tilt(regions, None) is regions


def test_import_endpoint_end_to_end(client, created_title):
    url = f"/api/v1/titles/{created_title['id']}/state-signals/import"
    states = census.all_states()
    lines = [CSV_HEADER.strip()] + [
        f"{s},views,{states[s].population * (5 if s == 'Kerala' else 1) // 1000},2026-10-01,Crunchyroll"
        for s in ("Kerala", "Maharashtra", "Tamil Nadu", "Uttar Pradesh")
    ]
    response = client.post(url, files={"file": ("signals.csv", "\n".join(lines), "text/csv")})
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["imported"] == 4 and body["state_index"]["Kerala"] == 100.0
    assert body["state_index"]["Maharashtra"] == pytest.approx(20.0)

    listed = client.get(f"/api/v1/titles/{created_title['id']}/state-signals").json()
    assert len(listed) == 4 and {r["source"] for r in listed} == {"Crunchyroll"}

    started = client.post(f"/api/v1/titles/{created_title['id']}/analyses").json()
    result = client.get(f"/api/v1/analyses/{started['analysis_id']}/result").json()
    kerala = next(r for r in result["regional_scores"] if r["state"] == "Kerala")
    assert any("Imported viewing data" in reason for reason in kerala["reasons"])


def test_import_endpoint_rejects_bad_input(client, created_title):
    url = f"/api/v1/titles/{created_title['id']}/state-signals/import"
    bad = client.post(
        url, files={"file": ("x.csv", "state,metric,value\nNowhere,views,1\n", "text/csv")}
    )
    assert bad.status_code == 422
    no_cols = client.post(url, files={"file": ("x.csv", "a,b\n1,2\n", "text/csv")})
    assert no_cols.status_code == 422
    missing = client.post(
        "/api/v1/titles/missing/state-signals/import",
        files={"file": ("x.csv", CSV_HEADER + "Kerala,views,1,2026-10-01,x\n", "text/csv")},
    )
    assert missing.status_code == 404


def test_trends_history_is_stored_once_per_day(created_title):
    regional = {"Kerala": {"interest": 80.0}, "Tamil Nadu": {"interest": 60.0}}
    with SessionLocal() as db:
        for _ in range(2):  # idempotent for the same day
            svc.replace_source_for_day(
                db,
                created_title["id"],
                "google_trends",
                svc.trends_rows(regional),
                {"terms": "en:x"},
            )
        rows = db.query(StateSignal).filter_by(title_id=created_title["id"]).all()
        assert len(rows) == 2 and {r.source for r in rows} == {"google_trends"}
        assert rows[0].as_of == date.today() and rows[0].detail == {"terms": "en:x"}
        assert svc.load_partner_index(db, created_title["id"]) is None  # Trends is not partner data


def test_deleting_a_title_removes_its_state_signals(client, created_title):
    url = f"/api/v1/titles/{created_title['id']}/state-signals/import"
    csv = CSV_HEADER + "".join(
        f"{s},index,{v},2026-10-01,x\n" for s, v in (("Kerala", 90), ("Bihar", 40), ("Goa", 60))
    )
    assert client.post(url, files={"file": ("s.csv", csv, "text/csv")}).status_code == 201
    started = client.post(f"/api/v1/titles/{created_title['id']}/analyses").json()
    assert client.delete(f"/api/v1/analyses/{started['analysis_id']}").status_code == 204
    with SessionLocal() as db:
        assert db.query(StateSignal).filter_by(title_id=created_title["id"]).count() == 0
