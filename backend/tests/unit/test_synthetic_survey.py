from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

import app.services.sources  # noqa: F401  # initialise the registry before SurveyData
from app.services import census
from app.services.sources.regional_context import RegionalContextAdapter
from app.services.survey import SurveyData

pytestmark = pytest.mark.unit

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "data" / "generate_synthetic_survey.py"
spec = importlib.util.spec_from_file_location("generate_synthetic_survey", SCRIPT)
gen = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = gen  # dataclasses resolve annotations through sys.modules
spec.loader.exec_module(gen)

SMALL = {"total_respondents": 6_000, "min_per_state": 30}


@pytest.fixture(scope="module")
def result():
    return gen.generate(seed=1, **SMALL)


def test_output_loads_through_the_survey_loader_without_errors(result, tmp_path):
    gen.write(result, tmp_path)

    data = SurveyData.from_dir(tmp_path)

    assert data.errors == []
    assert len(data.rows) == len(result.rows)
    states = {row.state for row in data.rows}
    assert states == {*census.all_states(), None}  # every state plus the national rows
    assert {row.genre for row in data.rows} == {g.lower().replace("-", " ") for g in gen.GENRES}
    assert {row.year for row in data.rows} == set(gen.WAVES)


def test_respondent_file_stays_out_of_the_loader_folder(result, tmp_path):
    gen.write(result, tmp_path)

    assert not list(tmp_path.glob("*respondents*.csv"))
    assert (tmp_path / "microdata" / "synthetic_survey_respondents.csv").exists()


def test_same_seed_gives_identical_rows_and_different_seed_does_not(result):
    assert gen.generate(seed=1, **SMALL).rows == result.rows
    assert gen.generate(seed=2, **SMALL).rows != result.rows


def test_indices_are_bounded_and_rows_are_flagged_as_proxy(result):
    for row in result.rows:
        assert gen.INDEX_FLOOR <= row["index"] <= gen.INDEX_CEIL or row["state"] == "India"
        assert row["index"] > 0
        assert "PROXY" in row["source"]
        assert row["content_type"] == "anime"


def test_injected_bad_respondents_are_removed_and_genuine_ones_mostly_kept(result):
    for wave in result.audit["waves"]:
        injected = wave["straight_liners_injected"] + wave["all_no_injected"]
        assert wave["removed_injected"] == injected
        assert wave["injected_missed"] == 0
        assert wave["removed_genuine"] < 0.03 * wave["generated"]
    counts = result.respondent_flags.sum(axis=1)
    assert counts.min() >= 1
    assert counts.max() < gen.STRAIGHTLINE_MIN


def test_synthetic_rows_are_flagged_as_a_proxy_by_the_app(result, tmp_path):
    gen.write(result, tmp_path)
    title = SimpleNamespace(
        name="Shadow Bloom",
        english_title="Shadow Bloom",
        primary_genre="fantasy",
        genres=["fantasy", "action"],
        themes=[],
        target_languages=["Tamil"],
        target_states=["Kerala"],
        content_format="anime_series",
    )

    evidence = RegionalContextAdapter(SurveyData.from_dir(tmp_path)).collect(title)

    assert evidence.quality_score == 0.75
    assert evidence.regional
    assert any("exploratory proxies" in warning for warning in evidence.warnings)
