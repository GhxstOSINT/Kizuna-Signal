from __future__ import annotations

import pytest

from app.services.scoring import WEIGHTS, calculate_market_score, decision_classification


@pytest.mark.unit
def test_scoring_weights_sum_to_one():
    assert sum(WEIGHTS.values()) == pytest.approx(1.0)


@pytest.mark.unit
def test_weighted_formula_and_bounds():
    components = {key: 80.0 for key in WEIGHTS}
    assert calculate_market_score(components) == 80.0
    assert calculate_market_score({key: 200.0 for key in WEIGHTS}) == 100
    assert calculate_market_score({key: -10.0 for key in WEIGHTS}) == 0


@pytest.mark.unit
@pytest.mark.parametrize(
    "score,confidence,expected",
    [
        (90, 40, "insufficient_evidence"),
        (85, 80, "strong_opportunity"),
        (70, 80, "promising_opportunity"),
        (60, 80, "test_before_investing"),
        (40, 80, "limited_opportunity"),
    ],
)
def test_classification_thresholds(score, confidence, expected):
    assert decision_classification(score, confidence) == expected
