import pytest

from kizuna import engine
from kizuna.api import MockApi

TITLES = ["shadow_bloom", "hollow_tide", "kitsune_circuit"]


@pytest.fixture(scope="module")
def api():
    return MockApi(stage_seconds=0)


@pytest.fixture(scope="module")
def cfg(api):
    return api.get_config()


def view(api, cfg, tid, overrides=None, optional=False):
    return engine.compute_view(
        api.get_analysis(tid),
        api.get_sources(tid),
        api.get_comparables(tid),
        cfg,
        overrides,
        include_optional=optional,
    )


def test_reference_titles_hit_target_numbers(api, cfg):
    expected = {"shadow_bloom": (78, 82), "hollow_tide": (81, 43), "kitsune_circuit": (66, 64)}
    for tid, (score, conf) in expected.items():
        v = view(api, cfg, tid)
        assert (v["overall"], v["confidence"]) == (score, conf)


def test_overall_equals_weighted_sum_of_primary_components(api, cfg):
    for tid in TITLES:
        v = view(api, cfg, tid)
        raw = sum(
            c["weight"] / 100 * v["components"][c["id"]] for c in cfg["components"] if c["primary"]
        )
        assert v["overall"] == int(raw + 0.5)


def test_primary_weights_sum_to_100(cfg):
    assert sum(c["weight"] for c in cfg["components"] if c["primary"]) == 100


def test_optional_component_has_zero_weight_and_is_hidden_by_default(api, cfg):
    optional = [c for c in cfg["components"] if not c["primary"]]
    assert optional and all(c["weight"] == 0 for c in optional)
    ids = [c["id"] for c in view(api, cfg, "shadow_bloom")["visible_components"]]
    assert "localization_readiness" not in ids
    ids = [c["id"] for c in view(api, cfg, "shadow_bloom", optional=True)["visible_components"]]
    assert "localization_readiness" in ids


def test_interval_is_around_score_and_widens_when_confidence_drops(api, cfg):
    hi = view(api, cfg, "shadow_bloom")
    lo = view(api, cfg, "hollow_tide")
    assert hi["interval"] == (72, 84)
    assert lo["interval"][1] - lo["interval"][0] > hi["interval"][1] - hi["interval"][0]
    assert 0 <= lo["interval"][0] <= lo["overall"] <= lo["interval"][1] <= 100


def test_decision_labels(cfg):
    assert engine.decision_label(81, 43, cfg) == "Insufficient evidence"
    assert engine.decision_label(78, 82, cfg) == "Strong opportunity"
    assert engine.decision_label(66, 64, cfg) == "Promising opportunity"
    assert engine.decision_label(55, 70, cfg) == "Test before investing"
    assert engine.decision_label(30, 70, cfg) == "Limited opportunity"


def test_low_confidence_flag(api, cfg):
    assert view(api, cfg, "hollow_tide")["low_confidence"]
    assert not view(api, cfg, "shadow_bloom")["low_confidence"]


def test_disabling_a_source_changes_confidence_and_round_trips(api, cfg):
    base = view(api, cfg, "shadow_bloom")
    off = view(api, cfg, "shadow_bloom", {"disabled_sources": ["google_trends"]})
    assert off["delta_confidence"] < 0 and off["delta_score"] < 0
    assert off["confidence"] < base["confidence"]
    back = view(api, cfg, "shadow_bloom", {"disabled_sources": []})
    assert (back["overall"], back["confidence"]) == (base["overall"], base["confidence"])
    assert back["components"] == base["components"] and back["factors"] == base["factors"]


def test_unavailable_source_override_is_ignored(api, cfg):
    base = view(api, cfg, "kitsune_circuit")
    again = view(api, cfg, "kitsune_circuit", {"disabled_sources": ["youtube"]})
    assert (again["overall"], again["confidence"]) == (base["overall"], base["confidence"])


def test_driver_inactive_only_when_all_its_sources_disabled(api, cfg):
    v = view(api, cfg, "shadow_bloom", {"disabled_sources": ["google_trends", "census"]})
    by_label = {d["label"]: d["active"] for d in v["drivers"]}
    assert by_label["Limited awareness outside major cities"] is False  # trends + census
    assert by_label["Growing Indian search momentum"] is True  # trends + wikimedia


def test_base_analysis_is_not_mutated(api, cfg):
    before = api.get_analysis("shadow_bloom")
    view(api, cfg, "shadow_bloom", {"disabled_sources": ["google_trends", "youtube"]})
    assert api.get_analysis("shadow_bloom") == before


def test_excluding_and_adding_comparables(api, cfg):
    comps = api.get_comparables("shadow_bloom")
    expected = comps["sets"]["expected"]
    base = view(api, cfg, "shadow_bloom")
    fewer = view(api, cfg, "shadow_bloom", {"included_comps": expected[:3]})
    assert fewer["factors"]["comparable_quality"] < base["factors"]["comparable_quality"]
    better = view(api, cfg, "shadow_bloom", {"included_comps": comps["sets"]["optimistic"]})
    worse = view(api, cfg, "shadow_bloom", {"included_comps": comps["sets"]["conservative"]})
    assert (
        better["components"]["comparable_performance"]
        > base["components"]["comparable_performance"]
    )
    assert (
        worse["components"]["comparable_performance"] < base["components"]["comparable_performance"]
    )
    same = view(api, cfg, "shadow_bloom", {"included_comps": list(expected)})
    assert same["overall"] == base["overall"]


def test_rank_regions_suppresses_weak_evidence(api, cfg):
    r = engine.rank_regions(api.get_regions("shadow_bloom")["regions"], cfg)
    assert [x["state"] for x in r["top"]][:3] == ["Maharashtra", "Karnataka", "Delhi"]
    assert all(
        x["evidence_strength"] >= cfg["regional"]["suppress_below_evidence"] for x in r["ranked"]
    )
    assert r["suppressed"] and all(x["suppressed"] for x in r["suppressed"])
    assert [x["rank"] for x in r["ranked"]] == list(range(1, len(r["ranked"]) + 1))
    assert len(r["ranked"]) + len(r["suppressed"]) == 36


def test_low_confidence_title_suppresses_more_states(api, cfg):
    hi = engine.rank_regions(api.get_regions("shadow_bloom")["regions"], cfg)
    lo = engine.rank_regions(api.get_regions("hollow_tide")["regions"], cfg)
    assert len(lo["suppressed"]) > len(hi["suppressed"])


def test_scenario_base_levers_give_zero_delta(api, cfg):
    v = view(api, cfg, "shadow_bloom")
    sc = api.get_scenarios("shadow_bloom")
    r = engine.scenario_result(v, sc, sc["base"]["levers"], cfg)
    assert (r["delta_score"], r["delta_confidence"]) == (0, 0)
    assert r["cost_level"] == "Low" and r["reach_level"] == "Moderate"


def test_scenario_presets_and_recommendation(api, cfg):
    v = view(api, cfg, "shadow_bloom")
    sc = api.get_scenarios("shadow_bloom")
    results = [(p["label"], engine.scenario_result(v, sc, p["levers"], cfg)) for p in sc["presets"]]
    assert all(r["delta_score"] > 0 for _, r in results)
    best, why = engine.recommend_scenario(results, cfg)
    assert best == "Hindi dub + regional-first" and "outweighs" in why


def test_scenario_does_not_change_base_view(api, cfg):
    v = view(api, cfg, "shadow_bloom")
    sc = api.get_scenarios("shadow_bloom")
    engine.scenario_result(v, sc, sc["presets"][1]["levers"], cfg)
    assert (v["overall"], v["confidence"]) == (78, 82)


def test_scenario_values_are_clamped(api, cfg):
    v = view(api, cfg, "shadow_bloom")
    sc = api.get_scenarios("shadow_bloom")
    v = dict(v, overall=99)
    r = engine.scenario_result(v, sc, sc["presets"][1]["levers"], cfg)
    assert r["score"] <= 100


def test_recommend_returns_none_when_nothing_beats_base(cfg):
    worse = {
        "delta_score": -2,
        "delta_confidence": 0,
        "delta_cost": 1.0,
        "cost_level": "Low",
        "reach_level": "Low",
    }
    assert engine.recommend_scenario([("x", worse)], cfg)[0] is None
