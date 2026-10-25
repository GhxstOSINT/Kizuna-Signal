from __future__ import annotations

import pytest

from app.services.levenshtein import (
    GENRE_VOCABULARY,
    PLATFORM_VOCABULARY,
    compare_records,
    levenshtein_distance,
    name_similarity,
    similarity,
    vocabulary_confidence,
)

pytestmark = pytest.mark.unit


def test_distance_known_values():
    assert levenshtein_distance("kitten", "sitting") == 3
    assert levenshtein_distance("", "abc") == 3
    assert levenshtein_distance("same", "same") == 0


def test_similarity_is_normalised_and_case_insensitive():
    assert similarity("Spy x Family", "spy x family") == 1.0
    assert 0 <= similarity("abc", "xyz") <= 1
    assert similarity("", "") == 1.0


def test_similarity_keeps_non_ascii_titles():
    assert similarity("呪術廻戦", "呪術廻戦") == 1.0
    assert similarity("呪術廻戦", "鬼滅の刃") < 0.5


def test_name_similarity_prefix_rule_is_strong_but_never_perfect():
    score = name_similarity("Demon Slayer", "Demon Slayer: Kimetsu no Yaiba")
    assert 0.85 <= score < 1.0
    assert name_similarity("Naruto", "Boruto") < 0.75


def test_vocabulary_confidence_penalises_unknown_values():
    assert vocabulary_confidence(["Fantasy"], GENRE_VOCABULARY) == 1.0
    assert vocabulary_confidence(["Sci-Fi"], GENRE_VOCABULARY) == 1.0
    assert vocabulary_confidence(["Zzzzzz"], GENRE_VOCABULARY) < 0.5
    assert vocabulary_confidence(["OTT"], PLATFORM_VOCABULARY) == 1.0
    assert vocabulary_confidence([], GENRE_VOCABULARY) == 0.0


def test_compare_records_ignores_missing_fields_and_renormalises():
    a = {"title": "A Show", "genres": ["action"], "platform": "OTT"}
    b = {"title": "A Show", "genres": ["action"]}
    result = compare_records(a, b)
    assert result["composite"] == 100.0
    assert result["fields"]["platform"] is None
    assert result["fields_used"] == ["genre", "title"]
    assert compare_records({}, {})["composite"] == 0.0
