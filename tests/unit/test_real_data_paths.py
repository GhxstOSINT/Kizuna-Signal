import pytest

from app.ml.levenshtein import name_similarity
from app.schemas.analysis import AnalysisResult
from app.schemas.scenario import ScenarioCreate
from app.services.scenarios import run_scenario
from app.services.scoring import (
    calculate_component_scores,
    calculate_market_score,
    state_interest_tilt,
)
from app.services.sources.base import SourceEvidence
from tests.unit.test_live_sources import make_title


def ev(source, **metrics):
    return SourceEvidence(source, "available", 0.9, 0.9, metrics)


def test_unavailable_sources_are_omitted_not_defaulted():
    evidence = [ev("regional_context", language_fit=60, addressable_market=40)]
    unavailable = [SourceEvidence(s, "unavailable", 0, 0) for s in ("google_trends", "youtube", "wikimedia")]
    components = calculate_component_scores(make_title(), evidence + unavailable, [])
    assert set(components) == {"content_fit", "regional_opportunity"}


def test_market_score_renormalises_over_present_factors():
    assert calculate_market_score({"content_fit": 80.0, "regional_opportunity": 60.0}) == pytest.approx(
        (80 * 0.25 + 60 * 0.20) / 0.45, abs=0.01
    )
    assert calculate_market_score({}) == 0.0


def test_name_similarity_prefix_rule():
    assert name_similarity("Demon Slayer", "Demon Slayer: Kimetsu no Yaiba") >= 0.85
    assert name_similarity("Naruto", "Boruto") < 0.75


def test_state_tilt_uses_real_state_interest_and_is_capped():
    metrics = {f"state_interest_{s}": 10.0 for s in
               ("Maharashtra", "Karnataka", "Delhi NCR", "Tamil Nadu", "Telangana", "West Bengal", "Kerala", "Uttar Pradesh")}
    metrics["state_interest_Kerala"] = 100.0
    tilt = state_interest_tilt([ev("google_trends", **metrics)])
    assert tilt["Kerala"] == 5.0 and tilt["Maharashtra"] < 0
    assert state_interest_tilt([ev("google_trends", relative_interest=40)]) is None


def test_scenario_without_overrides_reproduces_the_base_score(client, created_title):
    started = client.post(f"/api/v1/titles/{created_title['id']}/analyses").json()
    result = client.get(f"/api/v1/analyses/{started['analysis_id']}/result").json()
    from app.db.models import Title
    from app.db.session import SessionLocal

    with SessionLocal() as db:
        title = db.get(Title, created_title["id"])
        same = run_scenario(title, AnalysisResult.model_validate(result), ScenarioCreate(name="No change"))
        broader = run_scenario(
            title, AnalysisResult.model_validate(result),
            ScenarioCreate(name="More languages", target_languages=["Hindi", "Tamil", "Telugu", "Bengali", "Kannada"]),
        )
    assert same.score_delta == pytest.approx(0, abs=0.01)
    assert broader.score_delta > 0  # computed from census language coverage, not a fixed bump
