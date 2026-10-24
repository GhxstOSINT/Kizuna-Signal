"""Pure scoring and recalculation logic (no Streamlit).

The base analysis is a frozen snapshot. Source toggles, comparable changes and
scenario levers are overrides recomputed here; nothing mutates the snapshot.
All weights, thresholds and lever effects come from data/mock/config.json.
"""


def _round(x):
    """Round half up so 80.5 -> 81 (Python's round() is banker's rounding)."""
    return int(x + 0.5)


def _clamp(v, lo=0.0, hi=100.0):
    return max(lo, min(hi, v))


# ---------------------------------------------------------------- scoring
def primary_components(cfg):
    return [c for c in cfg["components"] if c["primary"]]


def weighted_overall(components, cfg):
    return sum(c["weight"] / 100 * components[c["id"]] for c in primary_components(cfg))


def confidence_score(factors, cfg):
    return sum(f["weight"] * factors[f["id"]] for f in cfg["confidence_factors"])


def interval(conf, score, cfg):
    half = cfg["interval"]["base"] + cfg["interval"]["slope"] * (100 - conf)
    h = _round(half)
    return (int(_clamp(score - h)), int(_clamp(score + h)))


def decision_label(score, conf, cfg):
    d = cfg["decision"]
    if conf < d["insufficient_below_confidence"]:
        return d["insufficient_label"]
    for band in d["bands"]:
        if score >= band["min_score"]:
            return band["label"]
    return d["bands"][-1]["label"]


def confidence_band(conf):
    return "High" if conf >= 75 else "Medium" if conf >= 55 else "Low"


def apply_effects(components, factors, effects):
    """Return copies of components/factors with an effects dict applied (clamped 0-100)."""
    comps, facs = dict(components), dict(factors)
    for k, d in effects.get("components", {}).items():
        if k in comps:
            comps[k] = _clamp(comps[k] + d)
    for k, d in effects.get("confidence_factors", {}).items():
        if k in facs:
            facs[k] = _clamp(facs[k] + d)
    return comps, facs


# ------------------------------------------------------------- comparables
def default_comparable_ids(comparables):
    return list(comparables["sets"]["expected"])


def _stats(comps_by_id, ids):
    sims = [comps_by_id[i]["similarity"] for i in ids]
    perfs = [comps_by_id[i]["india_performance"] for i in ids]
    wsum = sum(sims)
    return (sum(s * p for s, p in zip(sims, perfs)) / wsum, sum(sims) / len(sims), len(ids))


def comparable_adjustment(comparables, current_ids):
    """(delta to Comparable Performance, delta to comparable-quality factor)."""
    by_id = {c["id"]: c for c in comparables["comparables"]}
    perf0, sim0, n0 = _stats(by_id, default_comparable_ids(comparables))
    perf1, sim1, n1 = _stats(by_id, current_ids)
    return perf1 - perf0, 5 * (n1 - n0) + 40 * (sim1 - sim0)


# -------------------------------------------------------------------- view
def compute_view(analysis, sources, comparables, cfg, overrides=None, include_optional=False):
    """Recompute the headline numbers from the frozen analysis plus overrides.

    overrides: {"disabled_sources": [ids], "included_comps": [ids] or None}
    Returns a dict with adjusted values and the deltas against the base.
    """
    overrides = overrides or {}
    disabled = list(overrides.get("disabled_sources", []))
    included = overrides.get("included_comps")
    if included is None:
        included = default_comparable_ids(comparables)

    base = analysis.get("_authoritative") or _headline(
        analysis["components"], analysis["confidence_factors"], cfg
    )

    comps = dict(analysis["components"])
    facs = dict(analysis["confidence_factors"])
    by_src = {s["id"]: s for s in sources}
    for sid in disabled:
        src = by_src.get(sid)
        if src and src["status"] == "available":
            comps, facs = apply_effects(comps, facs, src["effect_if_disabled"])
    d_perf, d_quality = comparable_adjustment(comparables, included)
    comps["comparable_performance"] = _clamp(comps["comparable_performance"] + d_perf)
    facs["comparable_quality"] = _clamp(facs["comparable_quality"] + d_quality)

    no_overrides = not disabled and overrides.get("included_comps") is None
    cur = base if no_overrides and analysis.get("_authoritative") else _headline(comps, facs, cfg)
    drivers = []
    for d in analysis["drivers"]:
        active = not set(d["source_ids"]).issubset(disabled)
        drivers.append(dict(d, active=active))
    return {
        "components": comps, "factors": facs,
        "overall": cur["score"], "confidence": cur["confidence"],
        "interval": cur["interval"], "label": cur["label"],
        "confidence_band": confidence_band(cur["confidence"]),
        "low_confidence": cur["confidence"] < cfg["decision"]["insufficient_below_confidence"],
        "base": base,
        "delta_score": cur["score"] - base["score"],
        "delta_confidence": cur["confidence"] - base["confidence"],
        "drivers": drivers, "included_comps": list(included),
        "disabled_sources": disabled,
        "visible_components": [c for c in cfg["components"] if c["primary"] or include_optional],
    }


def _headline(components, factors, cfg):
    score = _round(weighted_overall(components, cfg))
    conf = _round(confidence_score(factors, cfg))
    return {"score": score, "confidence": conf, "interval": interval(conf, score, cfg),
            "label": decision_label(score, conf, cfg)}


# ------------------------------------------------------------------ regions
def rank_regions(regions, cfg):
    """Split regions into ranked / suppressed. Weak evidence never gets a rank."""
    r = cfg["regional"]
    ranked, suppressed = [], []
    for reg in regions:
        reg = dict(reg)
        if reg["evidence_strength"] < r["suppress_below_evidence"]:
            reg["suppressed"] = True
            reg["evidence_flag"] = "insufficient"
            suppressed.append(reg)
        else:
            reg["suppressed"] = False
            reg["evidence_flag"] = "limited" if reg["evidence_strength"] < r["limited_below_evidence"] else "ok"
            ranked.append(reg)
    ranked.sort(key=lambda x: (-x["score"], x["state"]))
    for i, reg in enumerate(ranked, 1):
        reg["rank"] = i
    return {"ranked": ranked, "suppressed": sorted(suppressed, key=lambda x: x["state"]),
            "top": ranked[: r["top_n"]]}


# ---------------------------------------------------------------- scenarios
def _level(points, levels):
    for lv in levels:
        if points < lv["below"]:
            return lv["label"]
    return levels[-1]["label"]


def cost_level(points, cfg):
    return _level(points, cfg["cost_levels"])


def reach_level(points, cfg):
    return _level(points, cfg["reach_levels"])


def _lever_sum(levers, cfg):
    tot = {"score": 0.0, "confidence": 0.0, "cost": 0.0, "reach": 0.0}
    for lever, option in levers.items():
        eff = cfg["levers"][lever]["options"][option]
        for k in tot:
            tot[k] += eff[k]
    return tot


def scenario_result(view, scenarios, levers, cfg):
    """Apply lever overrides to the current view and return score/confidence/cost/reach."""
    base_tot = _lever_sum(scenarios["base"]["levers"], cfg)
    new_tot = _lever_sum(levers, cfg)
    delta = {k: new_tot[k] - base_tot[k] for k in base_tot}
    score = int(_clamp(_round(view["overall"] + delta["score"])))
    conf = int(_clamp(_round(view["confidence"] + delta["confidence"])))
    cost_pts = max(0.0, scenarios["base"]["cost_points"] + delta["cost"])
    reach_pts = max(0.0, scenarios["base"]["reach_points"] + delta["reach"])
    return {
        "levers": dict(levers), "score": score, "confidence": conf,
        "interval": interval(conf, score, cfg),
        "label": decision_label(score, conf, cfg),
        "cost_points": cost_pts, "cost_level": cost_level(cost_pts, cfg),
        "reach_points": reach_pts, "reach_level": reach_level(reach_pts, cfg),
        "delta_score": score - view["overall"], "delta_confidence": conf - view["confidence"],
        "delta_cost": cost_pts - scenarios["base"]["cost_points"],
        "delta_reach": reach_pts - scenarios["base"]["reach_points"],
    }


def recommend_scenario(results, cfg):
    """Pick the best of [(name, result)] by the configured objective; return (name, rationale)."""
    w = cfg["scenario_objective"]

    def value(r):
        return w["score"] * r["delta_score"] + w["confidence"] * r["delta_confidence"] + w["cost"] * r["delta_cost"]

    best_name, best = max(results, key=lambda nr: value(nr[1]))
    if value(best) <= 0:
        return None, "No alternative beats the base strategy once cost and confidence are considered."
    rationale = (f"{best_name}: {best['delta_score']:+d} score, {best['delta_confidence']:+d} confidence, "
                 f"cost {best['cost_level']}, reach {best['reach_level']}. "
                 "The expected gain outweighs the additional cost.")
    return best_name, rationale


def scenario_label(cfg, lever, option):
    return cfg["levers"][lever]["options"][option]["label"]



def scenario_results(view, scenarios, cfg):
    """[(name, result)]: the base strategy first, then each preset scenario."""
    out = [("Base strategy", scenario_result(view, scenarios, scenarios["base"]["levers"], cfg))]
    for p in scenarios["presets"]:
        out.append((p["label"], scenario_result(view, scenarios, p["levers"], cfg)))
    return out
