from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.schemas.analysis import ComparableTitle
from app.services.confidence import calculate_confidence
from app.services.regional import calculate_regional_scores_live, has_regional_evidence
from app.services.scoring import (
    WEIGHTS,
    build_drivers,
    calculate_component_scores,
    calculate_market_score,
    unmeasured_components,
)
from app.services.sources.base import SourceEvidence

pytestmark = pytest.mark.unit


def title(**overrides):
    base = dict(
        name="T", synopsis="s", content_format="anime_series", primary_genre="fantasy",
        source_material="manga", expected_release_period="2027", genres=["fantasy"],
        themes=["a", "b"], target_languages=["Hindi"], target_states=[], target_platform="OTT",
    )  # fmt: skip
    return SimpleNamespace(**{**base, **overrides})


def ev(source, metrics, status="available", **kwargs):
    return SourceEvidence(source, status, 1.0, 0.9, metrics, **kwargs)


FULL = [
    ev("google_trends", {"relative_interest": 60, "momentum": 60}),
    ev("wikimedia", {"curiosity": 60}),
    ev("youtube", {"attention": 70, "engagement_quality": 70, "velocity": 70}),
    ev("regional_context", {"language_fit": 80, "addressable_market": 80}),
]
COMPARABLES = [ComparableTitle(title="C", similarity=0.8, market_signal=70, reasons=["r"])]


def test_unavailable_source_is_unmeasured_not_a_neutral_fifty():
    evidence = [e for e in FULL if e.source != "youtube"]

    assert unmeasured_components(title(), evidence, COMPARABLES) == {"engagement_quality"}
    assert unmeasured_components(title(), FULL, COMPARABLES) == set()
    assert unmeasured_components(title(), FULL, []) == {"comparable_performance"}


def test_score_regresses_toward_neutral_as_evidence_disappears():
    components = {key: 90.0 for key in WEIGHTS}

    full = calculate_market_score(components)
    thin = calculate_market_score(components, {"demand_momentum", "engagement_quality"})
    none = calculate_market_score(components, set(WEIGHTS))

    assert full == 90.0
    assert 50 < thin < full
    assert none == 50.0


def test_a_missing_component_does_not_act_like_a_fifty():
    components = {key: 90.0 for key in WEIGHTS}
    old_style = sum(w * (50 if k == "engagement_quality" else 90) for k, w in WEIGHTS.items())

    assert calculate_market_score(components, {"engagement_quality"}) > old_style


def test_unmeasured_components_are_not_reported_as_drivers():
    components = calculate_component_scores(title(), FULL[:2], COMPARABLES)
    unmeasured = unmeasured_components(title(), FULL[:2], COMPARABLES)

    positives, negatives = build_drivers(components, title(), FULL[:2], unmeasured)
    names = {d.name for d in positives + negatives}

    assert "Engagement quality" not in names and "Regional opportunity" not in names


def test_no_traction_evidence_collapses_confidence_and_warns():
    traction = {"demand_momentum", "engagement_quality"}
    with_traction, _, _ = calculate_confidence(title(), FULL, COMPARABLES, set())
    without, level, warnings = calculate_confidence(title(), FULL[3:], COMPARABLES, traction)

    assert without < 0.6 * with_traction
    assert level == "low"
    assert any("No title-specific demand or engagement evidence" in w for w in warnings)
    assert any("Not measured, so excluded" in w for w in warnings)


def test_survey_genre_affinity_pulls_content_fit():
    plain = calculate_component_scores(title(), FULL, COMPARABLES)["content_fit"]
    others = [e for e in FULL if e.source != "regional_context"]
    liked = [*others, ev("regional_context", {"genre_affinity": 100})]
    disliked = [*others, ev("regional_context", {"genre_affinity": 0})]

    assert calculate_component_scores(title(), liked, COMPARABLES)["content_fit"] > plain
    assert calculate_component_scores(title(), disliked, COMPARABLES)["content_fit"] < plain


TRENDS = ev(
    "google_trends",
    {"relative_interest": 50},
    regional={
        "Maharashtra": {"interest": 40.0},
        "Tamil Nadu": {"interest": 90.0},
        "Sikkim": {"interest": 100.0},  # tiny state: noisy, must be shrunk
        "Kerala": {"interest": 10.0},
    },
)
CONTEXT = ev("regional_context", {}, provenance={"mode": "static-census"})


def regions(**kwargs):
    rows = calculate_regional_scores_live(title(**kwargs), 70.0, 80.0, [TRENDS, CONTEXT])
    return {row.state: row for row in rows}


def test_live_regional_scoring_covers_all_states_sorted_with_valid_ranges():
    rows = calculate_regional_scores_live(title(), 70.0, 80.0, [TRENDS, CONTEXT])

    assert len(rows) == 36
    assert [r.score for r in rows] == sorted((r.score for r in rows), reverse=True)
    assert all(0 <= r.score <= 100 and 0 <= r.confidence <= 100 for r in rows)


def test_small_state_trends_noise_is_shrunk_so_it_cannot_top_the_ranking():
    by_state = regions()

    assert by_state["Sikkim"].score < by_state["Maharashtra"].score
    assert any("shrunk" in reason for reason in by_state["Sikkim"].reasons)


def test_localization_plan_targets_states_by_language_and_by_name():
    by_state = regions(target_languages=["Tamil"], target_states=["Delhi NCR"])
    untargeted = regions(target_languages=["Marathi"], target_states=[])

    assert by_state["Tamil Nadu"].score > untargeted["Tamil Nadu"].score
    assert by_state["Delhi"].score > untargeted["Delhi"].score
    assert by_state["Tamil Nadu"].recommended_language == "Tamil"


def test_state_without_trends_reading_gets_lower_confidence():
    by_state = regions()

    assert by_state["Goa"].confidence < by_state["Maharashtra"].confidence
    assert any("No Google Trends reading" in r for r in by_state["Goa"].reasons)


def test_survey_rows_move_state_scores_and_are_cited():
    survey = ev(
        "regional_context",
        {},
        provenance={"mode": "static-census"},
        regional={"Kerala": {"survey_affinity": 95.0, "survey_index": 190.0, "survey_n": 500.0}},
    )
    base = {
        r.state: r for r in calculate_regional_scores_live(title(), 70.0, 80.0, [TRENDS, CONTEXT])
    }
    boosted = {
        r.state: r for r in calculate_regional_scores_live(title(), 70.0, 80.0, [TRENDS, survey])
    }

    assert boosted["Kerala"].score > base["Kerala"].score
    assert any("Survey affinity index 190" in r for r in boosted["Kerala"].reasons)
    assert boosted["Kerala"].confidence > base["Kerala"].confidence


def test_has_regional_evidence_ignores_demo_data():
    demo = ev(
        "regional_context", {"language_fit": 80}, provenance={"mode": "deterministic-offline-demo"}
    )

    assert not has_regional_evidence([demo])
    assert has_regional_evidence([TRENDS])
    assert has_regional_evidence([CONTEXT])
    assert not has_regional_evidence(
        [ev("google_trends", {}, status="unavailable", regional={"X": {}})]
    )
