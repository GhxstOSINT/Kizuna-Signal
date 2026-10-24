"""Pipeline tests on SYNTHETIC labels: they prove the plumbing and leakage guards, not model quality."""

import numpy as np
import pytest

from app.ml.features import assert_no_leakage, titles_frame
from app.ml.schema import TitleRecord
from app.ml.states import PILOT_STATES
from app.ml.titles import to_title_records
from app.ml.train import run
from tests.support.ml_data import synthetic


def test_training_runs_and_xgboost_beats_state_mean_on_synthetic_signal():
    records, labels = synthetic()
    report, _, _ = run(titles_frame(records), labels, PILOT_STATES)
    assert report["n_test_titles"] == 12 and report["n_train_titles"] == 48
    m = report["metrics"]
    assert m["xgboost"]["top3_hit"]["mean"] > m["state_mean"]["top3_hit"]["mean"]
    assert report["beats_baselines"] in (True, False)


def test_test_titles_are_released_after_training_titles():
    records, labels = synthetic()
    report, _, _ = run(titles_frame(records), labels, PILOT_STATES)
    assert report["test_release_from"] > "2016-01-01"


def test_label_column_never_in_features():
    records, labels = synthetic(20)
    report, fitted, _ = run(titles_frame(records), labels, PILOT_STATES)
    assert report["n_features"] > 0
    with pytest.raises(ValueError):
        assert_no_leakage(["genre_Action", "popularity"])
    with pytest.raises(ValueError):
        assert_no_leakage(["share"])


def test_shuffled_labels_score_near_chance():
    records, labels = synthetic(80)
    rng = np.random.default_rng(1)
    shuffled = labels.copy()
    # break the title->pattern link by permuting each title's shares across states
    shuffled["share"] = shuffled.groupby("title_id")["share"].transform(
        lambda s: rng.permutation(s.values)
    )
    report, _, _ = run(titles_frame(records), shuffled, PILOT_STATES)
    # chance for top-3 of 10 is 0.3; allow a generous margin for a 16-title test set
    assert report["metrics"]["xgboost"]["top3_hit"]["mean"] < 0.5


def test_title_record_anchor_prefers_evidenced_india_date():
    from datetime import date

    t = TitleRecord(
        title_id="a",
        franchise_id="a",
        original_release_date=date(2020, 1, 1),
        india_release_date=date(2021, 1, 1),
    )
    assert t.anchor_date() == date(2020, 1, 1)  # no evidence, so the original date is used
    t.india_release_date_evidence = "https://example.com/release"
    assert t.anchor_date() == date(2021, 1, 1)


def test_franchise_grouping_and_schema_mapping():
    def rec(i, related):
        return {
            "anilist_id": i,
            "name_en": f"T{i}",
            "name_jp": "旅",
            "name_romaji": f"Tabi{i}",
            "features": {
                "synopsis": "x" * 50,
                "genres": ["Action"],
                "tags": ["Swordplay"],
                "format": "TV",
                "studio": None,
                "season": None,
                "release_year": 2020,
                "has_prequel": False,
            },
            "outcome": {},
            "status": "FINISHED",
            "extra": {
                "mal_id": 5,
                "synonyms": [],
                "episodes": 12,
                "duration": 24,
                "streaming": ["Crunchyroll"],
                "start": [2020, 4, 1],
                "related_ids": related,
            },
            "provenance": {},
        }

    out = to_title_records([rec(5, [9]), rec(9, [5]), rec(20, [])])
    by_id = {t.title_id: t for t in out}
    assert by_id["anilist:5"].franchise_id == by_id["anilist:9"].franchise_id == "anilist:5"
    assert by_id["anilist:20"].franchise_id == "anilist:20"
    t = by_id["anilist:5"]
    assert t.source_ids == {"anilist": 5, "mal": 5} and t.original_release_date.year == 2020
    assert t.platform_or_distributor == ["Crunchyroll"] and t.themes == ["Swordplay"]
