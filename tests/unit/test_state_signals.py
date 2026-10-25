from __future__ import annotations

from datetime import date, timedelta

import httpx
import pytest

from app.core.config import Settings
from app.db.models import StateSignal
from app.db.session import SessionLocal
from app.ml.census import CENSUS, STATES
from app.services import state_signals as svc
from app.services.scoring import calculate_regional_scores, partner_tilt
from app.services.sources import live
from app.services.sources.live import (
    TrendsLive,
    combine_state_interest,
    vernacular_terms,
)
from tests.unit.test_live_sources import client as http_client
from tests.unit.test_live_sources import make_title

CSV = "state,metric,value,as_of,source\nUttar Pradesh,views,2000000,2026-10-01,Crunchyroll\n"


def test_parse_csv_accepts_aliases_and_rejects_bad_rows():
    text = (
        "state,metric,value,as_of\n"
        "Delhi,views,100,2026-10-01\n"
        "Telengana,watch hours,50,2026-10-01\n"
        "Atlantis,views,10,2026-10-01\n"
        "Kerala,likes,10,2026-10-01\n"
        "Kerala,views,-5,2026-10-01\n"
        "Kerala,views,abc,2026-10-01\n"
        f"Kerala,views,5,{date.today() + timedelta(days=3)}\n"
    )
    rows, rejected = svc.parse_csv(text, "partner_import")
    assert [(r.state, r.metric) for r in rows] == [("Delhi NCR", "views"), ("Telangana", "watch_hours")]
    reasons = " ".join(r["reason"] for r in rejected)
    assert len(rejected) == 5 and "unknown state" in reasons and "unknown metric" in reasons
    assert "future" in reasons and ">= 0" in reasons


def test_parse_csv_requires_columns():
    with pytest.raises(ValueError, match="missing required"):
        svc.parse_csv("state,value\nKerala,1\n", "x")


def test_volume_metrics_are_normalised_per_capita():
    """Views proportional to population mean equal interest everywhere, not 'UP wins'."""
    lines = ["state,metric,value"] + [f"{s},views,{CENSUS[s]['population_m'] * 1000}" for s in STATES]
    rows, _ = svc.parse_csv("\n".join(lines), "partner_import")
    models = [
        StateSignal(title_id="t", state=r.state, source=r.source, metric=r.metric, value=r.value, as_of=r.as_of)
        for r in rows
    ]
    index = svc._series_index(models)
    assert all(abs(v - 100) < 1e-6 for v in index.values())


def test_partner_tilt_is_centred_and_capped():
    tilt = partner_tilt({"Kerala": 100.0, "Tamil Nadu": 50.0, "Maharashtra": 0.0})
    assert tilt["Kerala"] > 0 > tilt["Maharashtra"] and max(abs(v) for v in tilt.values()) <= 8
    assert partner_tilt({"Kerala": 100.0}) is None


def test_import_endpoint_end_to_end(client, created_title):
    url = f"/api/v1/titles/{created_title['id']}/state-signals/import"
    lines = ["state,metric,value,as_of"] + [
        f"{s},views,{CENSUS[s]['population_m'] * (5000 if s == 'Kerala' else 1000)},2026-10-01" for s in STATES
    ]
    response = client.post(
        url, files={"file": ("signals.csv", "\n".join(lines), "text/csv")}, data={"source": "Crunchyroll"}
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["imported"] == 8 and body["state_index"]["Kerala"] == 100.0
    assert body["state_index"]["Maharashtra"] == pytest.approx(20.0)

    listed = client.get(f"/api/v1/titles/{created_title['id']}/state-signals").json()
    assert len(listed) == 8 and {r["source"] for r in listed} == {"Crunchyroll"}

    started = client.post(f"/api/v1/titles/{created_title['id']}/analyses").json()
    result = client.get(f"/api/v1/analyses/{started['analysis_id']}/result").json()
    kerala = next(r for r in result["regional_scores"] if r["state"] == "Kerala")
    assert any("Imported viewing data" in reason for reason in kerala["reasons"])


def test_import_endpoint_rejects_bad_input(client, created_title):
    url = f"/api/v1/titles/{created_title['id']}/state-signals/import"
    bad = client.post(url, files={"file": ("x.csv", "state,metric,value\nNowhere,views,1\n", "text/csv")})
    assert bad.status_code == 422
    no_cols = client.post(url, files={"file": ("x.csv", "a,b\n1,2\n", "text/csv")})
    assert no_cols.status_code == 422
    assert client.post("/api/v1/titles/missing/state-signals/import",
                       files={"file": ("x.csv", CSV, "text/csv")}).status_code == 404


def test_regional_scores_without_partner_data_have_no_partner_reason():
    scores = calculate_regional_scores(make_title(), 70.0, 80.0, [], None)
    assert not any("Imported viewing data" in r for s in scores for r in s.reasons)


def test_combine_state_interest_weights_local_language_double_and_skips_zero_terms():
    base = {s: 50.0 for s in STATES}
    tamil = {**base, "Tamil Nadu": 100.0}
    out = combine_state_interest([("en", base), ("ta", tamil), ("hi", {s: 0.0 for s in STATES})])
    # Tamil Nadu: (1*50 + 2*100) / 3; other states: (50 + 50) / 2
    assert out["Tamil Nadu"] == pytest.approx(83.33, abs=0.01) and out["Kerala"] == 50.0
    assert combine_state_interest([("en", {s: 0.0 for s in STATES})]) == {}


def test_vernacular_terms_from_wikipedia_langlinks():
    payload = {"query": {"pages": {"1": {"langlinks": [
        {"lang": "ta", "*": "ஜுஜுட்சு கைசென்"}, {"lang": "fr", "*": "Jujutsu Kaisen"},
        {"lang": "hi", "*": "जुजुत्सु कैसेन"}]}}}}
    terms = vernacular_terms(http_client(lambda r: httpx.Response(200, json=payload)), {}, "Jujutsu Kaisen")
    assert terms == {"hi": "जुजुत्सु कैसेन", "ta": "ஜுஜுட்சு கைசென்"}


def test_trends_uses_multiple_terms_and_reports_them():
    pd = pytest.importorskip("pandas")
    google = {**{s: s for s in STATES}, "Delhi NCR": "Delhi"}

    class FakeTrend:
        def __init__(self, *args, **kwargs):
            self.term = None

        def build_payload(self, kw_list, geo, timeframe):
            self.term = kw_list[0]

        def interest_over_time(self):
            return pd.DataFrame({self.term: [40.0] * 12 + [60.0]})

        def interest_by_region(self, **kwargs):
            local = 100.0 if self.term == "தமிழ்" else 40.0
            return pd.DataFrame(
                {self.term: [local if name == "Tamil Nadu" else 40.0 for name in google.values()]},
                index=list(google.values()),
            )

    def handler(request: httpx.Request) -> httpx.Response:
        if "opensearch" in str(request.url):
            return httpx.Response(200, json=["q", ["Jujutsu Kaisen"], [], []])
        return httpx.Response(200, json={"query": {"pages": {"1": {"langlinks": [
            {"lang": "ta", "*": "தமிழ்"}]}}}})

    adapter = TrendsLive(http_client(handler), Settings(), factory=FakeTrend)
    adapter.PAUSE_SECONDS = 0
    live._trends_blocked_until = 0.0
    evidence = adapter.collect(make_title())
    assert evidence.status == "available"
    assert evidence.metrics["state_terms_used"] == 2.0
    assert evidence.provenance["terms"] == "en:Jujutsu Kaisen | ta:தமிழ்"
    # Tamil term counts double in Tamil Nadu: (40 + 2*100) / 3
    assert evidence.metrics["state_interest_Tamil Nadu"] == pytest.approx(80.0)
    assert evidence.metrics["state_interest_Kerala"] == 40.0


def test_trends_state_history_is_stored_once_per_day(created_title):
    from app.services.analysis import _record_trends_by_state
    from app.services.sources.base import SourceEvidence

    metrics = {f"state_interest_{s}": float(i * 10) for i, s in enumerate(STATES)}
    ev = [SourceEvidence("google_trends", "available", 0.9, 0.7, metrics, [], {"terms": "en:x"})]
    with SessionLocal() as db:
        _record_trends_by_state(db, created_title["id"], ev)
        _record_trends_by_state(db, created_title["id"], ev)  # idempotent for the same day
        rows = db.query(StateSignal).filter_by(title_id=created_title["id"]).all()
    assert len(rows) == len(STATES) and {r.source for r in rows} == {"google_trends"}
    assert rows[0].as_of == date.today() and rows[0].detail == {"terms": "en:x"}
