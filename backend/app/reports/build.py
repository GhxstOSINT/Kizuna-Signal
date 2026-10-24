"""Assembles one report dict from a prediction. Every renderer (json, csv, xml, pdf) reads this dict only."""

from datetime import UTC, datetime

from app.ml.scoring_config import ConfidenceConfig
from app.ml.state_model import StateModel
from app.ml.states import STATES

REPORT_VERSION = "report-v1"

LIMITATIONS = [
    "Scores describe relative interest and over-performance versus a typical anime; they are not revenue, "
    "viewership or audience-size forecasts.",
    "State labels come from Google Trends relative interest (0-100 normalised), not from consumption data.",
    "The training set is small; state-ranking skill is modest (see the evaluation table) and wide intervals are expected.",
    "Demand momentum and engagement quality are not measured for unreleased titles. A component whose held-out "
    "Spearman is below 0.1 is shown but excluded; the score is renormalised over the rest and `coverage` shows how much "
    "of the 100% weight that is.",
    "Content fit and comparable performance use global AniList popularity as a proxy because no India outcome exists.",
    "Population and internet-penetration weights are empty in data/tables/state_reference.csv, so states are not size-weighted.",
]


SYNTHETIC_LIMITATION = (
    "Training includes synthetic title x state rows for cells Google Trends left empty (weighted averages of similar "
    "titles and of the title's own related states, weight {w:.0%} of a real row). They add no new observations; "
    "validation uses real rows only. Sparse states (under 20 real titles) are still the least reliable."
)


def training_data(rep: dict) -> dict:
    """Real vs synthetic training rows and the held-out comparison with and without the synthetic rows."""
    syn = rep.get("synthetic")
    out = {
        "real_rows": rep.get("n_rows"),
        "synthetic_rows": rep.get("n_synthetic_rows", 0),
        "synthetic_used": bool(syn and syn.get("used_in_final_model")),
    }
    if syn:
        cmp_ = syn["comparison_oof"]
        out["synthetic_weight"] = syn["config"]["weight"]
        out["synthetic_version"] = syn["config"]["version"]
        out["comparison"] = {
            v: {
                "spearman": m["ensemble"]["spearman"]["mean"],
                "top3_hit": m["ensemble"]["top3_hit"]["mean"],
                "rmse_sparse_states": m["state_error"]["sparse"]["rmse"],
                "rmse_dense_states": m["state_error"]["dense"]["rmse"],
            }
            for v, m in cmp_.items()
        }
    return out


def formulas(report: dict) -> list[dict]:
    """Each formula with the numbers used for this title, so the maths can be checked by hand."""
    s, comps = report["success"], {c["key"]: c for c in report["success"]["components"]}
    reg, con, cmp_ = (
        comps["regional_opportunity"],
        comps["content_fit"],
        comps["comparable_performance"],
    )
    m, w = report["model"], ConfidenceConfig()
    f = report["india"]["confidence_factors"]
    out = [
        {
            "id": "lift",
            "name": "Lift (state model target)",
            "latex": r"$\ell_{t,s}=\log p_{t,s}-\overline{\log p}_{t}-\overline{\log p}_{s}+\overline{\log p}$",
            "plain": "lift = log(share) - title mean - state mean + grand mean (means from training titles only)",
            "note": "> 0: the title over-performs in that state versus a typical anime there.",
        },
        {
            "id": "share",
            "name": "Expected state share (softmax)",
            "latex": r"$\pi_s=\exp(e_s+\ell_s)\,/\,\sum_u \exp(e_u+\ell_u)$",
            "plain": "share_s = exp(e_s + lift_s) / sum_u exp(e_u + lift_u); e_s is the state baseline effect",
            "note": "Shares sum to 1 across the scored states.",
        },
        {
            "id": "interval",
            "name": "Lift interval (split conformal)",
            "latex": r"$[\ell_s-q,\ \ell_s+q]$",
            "plain": f"[lift - q, lift + q] with q = {m['interval_half_width']:.3f} (nominal {m['interval_nominal']:.0%})",
            "note": f"q is the {m['interval_nominal']:.0%} quantile of out-of-fold absolute errors; observed "
            f"out-of-fold coverage {m['interval_oof_coverage']:.0%}.",
        },
        {
            "id": "regional",
            "name": "Regional opportunity",
            "latex": r"$R=100\,\Phi\!\left(\sum_s \pi_s\,\ell_s\,/\,\sigma_\ell\right)$",
            "plain": "R = 100 * Phi(sum_s share_s * lift_s / sigma), Phi = standard normal CDF",
            "worked": f"sum = {reg['inputs']['share_weighted_lift']:.3f}, sigma = {reg['inputs']['lift_spread_sigma']:.3f}"
            f" -> R = {reg['value']:.1f}",
        },
        {
            "id": "content",
            "name": "Content fit",
            "latex": r"$C=100\cdot\mathrm{pctile}(\hat{y}_t;\ \hat{y}^{LOFO})$",
            "plain": "C = percentile of the ridge-predicted log popularity among leave-one-franchise-out predictions",
            "worked": f"predicted log popularity = {con['inputs']['predicted_log_popularity']:.2f} -> C = {con['value']:.1f}",
        },
        {
            "id": "comparables",
            "name": "Comparable performance",
            "latex": r"$P=\sum_k w_k\,\mathrm{pop}_k\,/\,\sum_k w_k$",
            "plain": "P = similarity-weighted mean popularity percentile of the comparable titles",
            "worked": (
                "no comparable titles"
                if cmp_["value"] is None
                else f"{cmp_['inputs']['n_comparables']} comparables -> P = {cmp_['value']:.1f}"
            ),
        },
        {
            "id": "success",
            "name": "Success score",
            "latex": r"$S=\sum_i w_i c_i\,/\,\sum_i w_i\quad(i\ \mathrm{measured})$",
            "plain": "S = weighted mean of the measured components; weights are renormalised over those components",
            "worked": f"coverage {s['coverage']:.0%} of the weight counted (validated components only) -> S = {s['score']:.1f} "
            f"(80% range {s['low']:.1f}-{s['high']:.1f})",
        },
        {
            "id": "confidence",
            "name": "Confidence (separate output)",
            "latex": r"$\mathrm{conf}=100\sum_k w_k f_k$",
            "plain": f"confidence = 100 * ({w.completeness} completeness + {w.comparables} comparables + {w.agreement} agreement "
            f"+ {w.interval} interval + {w.out_of_distribution} OOD); weights {w.version}",
            "worked": ", ".join(f"{k} {v:.2f}" for k, v in f.items())
            + f" -> {report['india']['confidence']:.1f}",
        },
    ]
    return out


NOTE = (
    "There is no single national score: the state model predicts where a title over-performs and each "
    "state's share of India demand. Read confidence and warnings before relying on the ranking."
)
TOP_N = 5


def prediction_out(
    result: dict, name: str, success: dict | None = None, seo: dict | None = None
) -> dict:
    """Shape a StateModel.predict() result as the /predict response."""
    states = list(result["states"])
    return {
        "model_version": result["model_version"],
        "task": result["task"],
        "title": name,
        "india": {
            "confidence": result["confidence"],
            "confidence_factors": result["confidence_factors"],
            "warnings": result["warnings"],
            "note": NOTE,
            "top_states": [s["state"] for s in states[:TOP_N]],
            "bottom_states": [s["state"] for s in states[-TOP_N:]],
        },
        "states": states,
        "comparables": result["comparables"],
        "success": success,
        "seo": seo,
    }


def title_from_body(body) -> dict:
    return {
        "name_en": body.name_en,
        "name_jp": body.name_jp,
        "format": body.format.value,
        "genres": body.genres,
        "tags": body.tags,
        "studio": body.studio,
        "release_date": str(body.release_date) if body.release_date else None,
        "episodes": body.episodes,
        "minutes_per_episode": body.minutes_per_episode,
        "localization_mode": body.localization_mode.value if body.localization_mode else None,
        "synopsis": body.synopsis,
    }


def assemble(title: dict, out: dict, success: dict | None, model: StateModel) -> dict:
    """`title`: the title facts shown in the report, `out`: the /predict response dict,
    `success`: SuccessModel.score(...) or None."""
    rep = model.report
    ens = rep.get("metrics_oof", {}).get("ensemble", {})
    report = {
        "report_version": REPORT_VERSION,
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "title": title,
        "success": success,
        "india": out["india"],
        "states": out["states"],
        "comparables": out["comparables"],
        "seo": out["seo"],
        "model": {
            "version": out["model_version"],
            "task": out["task"],
            "trained_at": rep.get("trained_at"),
            "n_labelled_titles": rep.get("n_labelled_titles"),
            "n_states": len(rep.get("states", [])),
            "ensemble_weights": rep.get("ensemble_weights"),
            "interval_nominal": rep.get("intervals", {}).get("nominal"),
            "interval_half_width": rep.get("intervals", {}).get("half_width_lift"),
            "interval_oof_coverage": rep.get("intervals", {}).get("oof_coverage"),
            "evaluation": {
                "scheme": rep.get("evaluation"),
                "oof_titles": rep.get("oof_titles"),
                "spearman": ens.get("spearman"),
                "top3_hit": ens.get("top3_hit"),
                "top3_hit_chance": rep.get("chance_top3_hit"),
            },
            "component_importance": rep.get("component_importance"),
            "training_data": training_data(rep),
        },
        "limitations": LIMITATIONS
        + (
            [SYNTHETIC_LIMITATION.format(w=rep["synthetic"]["config"]["weight"])]
            if rep.get("n_synthetic_rows")
            else []
        ),
    }
    if success is not None:
        report["formulas"] = formulas(report)
    return report


def model_card(model: StateModel, success=None) -> dict:
    """Model-level report (no title): data, held-out accuracy with and without synthetic rows, per-state coverage."""
    rep = model.report
    ens = rep.get("metrics_oof", {}).get("ensemble", {})
    err = rep.get("state_error_oof", {}).get("per_state", {})
    sparse = {s for s, n in model.state_titles.items() if n < 20}
    return {
        "model_version": model.version,
        "task": rep.get("task", "state"),
        "trained_at": rep.get("trained_at"),
        "n_labelled_titles": rep.get("n_labelled_titles", 0),
        "n_states": len(model.states),
        "training_data": training_data(rep),
        "evaluation": {
            "scheme": rep.get("evaluation"),
            "oof_titles": rep.get("oof_titles"),
            "spearman": ens.get("spearman"),
            "top3_hit": ens.get("top3_hit"),
            "top3_hit_chance": rep.get("chance_top3_hit"),
            "intervals": rep.get("intervals"),
            "ensemble_weights": rep.get("ensemble_weights"),
        },
        "success_model": success.report if success is not None else None,
        "states": [
            {
                "state": s,
                "name": STATES[s],
                "real_titles": model.state_titles.get(s, 0),
                "synthetic_rows": model.state_synthetic.get(s, 0),
                "sparse": s in sparse,
                "heldout_bias": err.get(s, {}).get("bias"),
                "heldout_rmse": err.get(s, {}).get("rmse"),
            }
            for s in model.states
        ],
        "limitations": LIMITATIONS
        + (
            [SYNTHETIC_LIMITATION.format(w=rep["synthetic"]["config"]["weight"])]
            if rep.get("n_synthetic_rows")
            else []
        ),
    }
