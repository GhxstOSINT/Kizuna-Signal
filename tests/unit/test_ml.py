import random

from app.ml import model
from app.ml.corpus import load_existing_titles, load_labeled_corpus
from app.ml.levenshtein import (
    GENRE_VOCABULARY,
    compare_records,
    levenshtein_distance,
    similarity,
    vocabulary_confidence,
)


def test_levenshtein_known_values():
    assert levenshtein_distance("kitten", "sitting") == 3
    assert levenshtein_distance("", "abc") == 3
    assert similarity("Spy x Family", "spy x family") == 1.0
    assert 0 <= similarity("abc", "xyz") <= 1


def test_vocabulary_confidence_penalises_unknown_genre():
    assert vocabulary_confidence(["Fantasy"], GENRE_VOCABULARY) == 1.0
    assert vocabulary_confidence(["Sci-Fi"], GENRE_VOCABULARY) == 1.0
    assert vocabulary_confidence(["Zzzzzz"], GENRE_VOCABULARY) < 0.5


def test_compare_records_ignores_missing_fields():
    a = {"title": "A Show", "genres": ["action"], "platform": "OTT"}
    b = {"title": "A Show", "genres": ["action"]}
    result = compare_records(a, b)
    assert result["composite"] == 100.0
    assert result["fields"]["platform"] is None


def test_corpus_deduplicates_by_edit_distance():
    titles = [r["title"] for r in load_labeled_corpus()]
    assert len(titles) == len(set(titles))
    assert sum("jujutsu" in t.lower() for t in titles) == 1
    assert len(load_existing_titles()) == 3


def test_ridge_recovers_linear_signal():
    rng = random.Random(1)
    x = [[rng.random(), rng.random()] for _ in range(200)]
    y = [3 * a - 2 * b + 5 for a, b in x]
    b0, coef = model.fit_ridge(x, y, [1.0] * 200, 1e-6)
    assert abs(b0 - 5) < 0.01 and abs(coef[0] - 3) < 0.01 and abs(coef[1] + 2) < 0.01


def test_synthetic_rows_are_flagged_and_in_range():
    rows = load_labeled_corpus()
    synth = model.GaussianGenerator(rows, 10.0, random.Random(3)).sample(100)
    assert all(r["synthetic"] and 0 <= r["performance"] <= 100 for r in synth)


def test_trained_artifact_reports_honest_metrics():
    artifact = model.load()
    assert artifact is not None
    assert artifact["metrics"]["evaluation"].startswith("leave-one-out on real rows only")
    result = model.predict(["action", "fantasy"], False, 2027)
    assert 0 <= result["prediction"] <= 100
