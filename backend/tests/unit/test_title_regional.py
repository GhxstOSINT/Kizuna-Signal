from types import SimpleNamespace

import pytest

from app.services.survey import SurveyData, SurveyRow
from app.services.title_regional import calculate_title_regional_scores, name_score


def title(**overrides):
    base = {
        "name": "架空の物語",
        "english_title": "Crimson Lantern",
        "primary_genre": "Fantasy",
        "genres": ["Fantasy"],
        "target_platform": "undecided",
    }
    return SimpleNamespace(**{**base, **overrides})


def survey(*rows: tuple[str | None, str, float]) -> SurveyData:
    return SurveyData(
        [
            SurveyRow(state, genre, "", index, 1000, 2025, "PROXY synthetic")
            for state, genre, index in rows
        ]
    )


@pytest.mark.parametrize(
    ("english", "name", "expected"),
    [
        ("Crimson Lantern", "架空の物語", 95),  # short, compact, Latin, separate English title
        (None, "進撃の巨人", 65),  # one word (+20), compact (+10), but no Latin-script title (-15)
        (
            "The Chronicles of a Very Long Winded Wandering Lantern Maker",
            "x",
            45,  # 10 words (-10), over 40 characters (-10), Latin (+10), separate English (+5)
        ),
    ],
)
def test_name_score_rules(english, name, expected):
    score, notes = name_score(title(english_title=english, name=name))
    assert score == expected
    assert notes


def test_scores_are_bounded_and_ordered_by_genre_affinity():
    data = survey(("Maharashtra", "fantasy", 180), ("Kerala", "fantasy", 60))
    regions = calculate_title_regional_scores(title(), data)
    by_state = {region.state: region for region in regions}
    assert all(0 <= region.score <= 100 for region in regions)
    assert regions == sorted(regions, key=lambda region: region.score, reverse=True)
    assert by_state["Maharashtra"].score > by_state["Kerala"].score


def test_name_shifts_every_state_equally():
    data = survey(("Maharashtra", "fantasy", 150), ("Kerala", "fantasy", 90))
    good = {r.state: r.score for r in calculate_title_regional_scores(title(), data)}
    bad = {
        r.state: r.score
        for r in calculate_title_regional_scores(title(english_title=None, name="進撃の巨人"), data)
    }
    gaps = {round(good[state] - bad[state], 2) for state in ("Maharashtra", "Kerala")}
    assert len(gaps) == 1 and gaps.pop() > 0


def test_state_without_rows_uses_the_national_viewer_with_lower_confidence():
    data = survey((None, "fantasy", 150), ("Maharashtra", "fantasy", 150))
    by_state = {r.state: r for r in calculate_title_regional_scores(title(), data)}
    assert "India-wide" in by_state["Kerala"].reasons[0]
    assert by_state["Kerala"].confidence <= 45
    assert "India-wide" not in by_state["Maharashtra"].reasons[0]


def test_merged_territory_and_renamed_state_use_dashboard_names():
    data = survey((None, "fantasy", 120))
    states = {r.state for r in calculate_title_regional_scores(title(), data)}
    assert "Dadra and Nagar Haveli and Daman and Diu" in states
    assert "Jammu and Kashmir" in states
    assert not states & {"Dadra and Nagar Haveli", "Daman and Diu", "Jammu & Kashmir"}


def test_no_survey_data_returns_nothing_so_the_caller_can_fall_back():
    assert calculate_title_regional_scores(title(), SurveyData()) == []
    assert calculate_title_regional_scores(title(), survey((None, "horror", 120))) == []
