from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.services import census
from app.services.sources.regional_context import RegionalContextAdapter
from app.services.survey import SurveyData

pytestmark = pytest.mark.unit
FIXTURE_DIR = Path(__file__).resolve().parent.parent / "fixtures"


def test_census_totals_match_published_2011_india_population():
    assert census.total_population() == 1_210_854_977
    assert len(census.all_states()) == 36


@pytest.mark.parametrize(
    "alias,canonical",
    [("Delhi NCR", "Delhi"), ("orissa", "Odisha"), ("Jammu and Kashmir", "Jammu & Kashmir"),
     ("Pondicherry", "Puducherry"), ("  tamil   nadu ", "Tamil Nadu")],
)  # fmt: skip
def test_state_aliases_resolve_to_trends_names(alias, canonical):
    assert census.resolve_state(alias).name == canonical


def test_unknown_state_is_none():
    assert census.resolve_state("Atlantis") is None


def test_population_share_and_language_groups():
    hindi = census.states_for_languages(["hindi"])
    assert 0.44 < census.population_share(hindi) < 0.50
    assert census.population_share(hindi, urban_weighted=True) < census.population_share(hindi)
    assert census.population_share(census.all_states().values()) == pytest.approx(1.0)


def test_survey_loader_validates_rows_and_reports_problems():
    data = SurveyData.from_dir(FIXTURE_DIR)

    assert {row.state for row in data.rows} == {"Maharashtra", "Tamil Nadu", None}
    assert any("unknown state 'Atlantis'" in e for e in data.errors)
    assert any("must be numeric" in e for e in data.errors)


def test_survey_affinity_is_sample_weighted_and_scored_around_100():
    data = SurveyData.from_dir(FIXTURE_DIR)

    over = data.affinity("Maharashtra", {"Fantasy"}, "anime_series")
    under = data.affinity("Tamil Nadu", {"fantasy"}, "anime_series")
    national = data.affinity(None, {"fantasy"}, "anime_series")

    assert over.index == 140 and over.score == 70.0
    assert under.index == 60 and under.score == 30.0
    assert national.score == 55.0
    assert data.affinity("Maharashtra", {"horror"}, "anime") is None
    assert data.affinity("Maharashtra", {"fantasy"}, "live_action_drama") is None


def test_missing_survey_folder_is_empty_not_an_error(tmp_path):
    data = SurveyData.from_dir(tmp_path / "nope")

    assert data.empty and data.errors == []


def test_stale_survey_is_flagged():
    data = SurveyData.from_dir(FIXTURE_DIR)

    assert data.stale_warning(datetime(2026, 1, 1, tzinfo=UTC)) is None
    assert "2025 or earlier" in data.stale_warning(datetime(2030, 1, 1, tzinfo=UTC))


def make_title(languages=("Hindi", "Tamil"), states=("Maharashtra",)):
    return SimpleNamespace(
        name="X", primary_genre="fantasy", genres=["fantasy"], content_format="anime_series",
        target_languages=list(languages), target_states=list(states),
    )  # fmt: skip


def test_regional_context_without_survey_is_census_only_and_says_so():
    evidence = RegionalContextAdapter().collect(make_title())

    assert evidence.status == "available"
    assert evidence.provenance["mode"] == "static-census"
    assert 0 < evidence.metrics["language_fit"] <= 100
    assert 0 < evidence.metrics["addressable_market"] <= 100
    assert "genre_affinity" not in evidence.metrics
    assert any("No survey data loaded" in w for w in evidence.warnings)


def test_regional_context_uses_survey_rows_when_present():
    evidence = RegionalContextAdapter(SurveyData.from_dir(FIXTURE_DIR)).collect(make_title())

    assert evidence.metrics["genre_affinity"] == 55.0
    assert evidence.regional["Maharashtra"]["survey_affinity"] == 70.0
    assert evidence.regional["Tamil Nadu"]["survey_index"] == 60.0


def test_wider_localization_plan_means_larger_addressable_market():
    narrow = RegionalContextAdapter().collect(make_title(["Tamil"], []))
    wide = RegionalContextAdapter().collect(make_title(["Hindi", "Tamil", "Telugu"], []))

    assert wide.metrics["addressable_market"] > narrow.metrics["addressable_market"]
    assert wide.metrics["language_fit"] > narrow.metrics["language_fit"]


def test_no_targets_means_not_measured_rather_than_guessed():
    evidence = RegionalContextAdapter().collect(make_title([], []))

    assert "addressable_market" not in evidence.metrics
    assert "language_fit" not in evidence.metrics
