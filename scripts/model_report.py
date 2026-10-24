"""Model-level report for the loaded state model and the India success score.

    python scripts/model_report.py            # writes results/MODEL_REPORT.md, state_coverage.csv, 08_*.png, 09_*.png

Reads models/state/LATEST.json and csv/ (for the success model's outcomes). Nothing here retrains.
"""

import argparse
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ml.scoring_config import MarketPotentialConfig  # noqa: E402
from app.ml.state_model import StateModel  # noqa: E402
from app.ml.success import MIN_SKILL, SuccessModel  # noqa: E402
from app.reports import build  # noqa: E402

INK, REAL, SYN = "#1f2933", "#5e3c99", "#b35806"


def coverage_chart(card: dict, path: Path) -> None:
    df = pd.DataFrame(card["states"]).sort_values("real_titles")
    fig, ax = plt.subplots(figsize=(8, 9))
    ax.barh(df["name"], df["real_titles"], color=REAL, label="real titles")
    ax.barh(
        df["name"],
        df["synthetic_rows"],
        left=df["real_titles"],
        color=SYN,
        alpha=0.7,
        label="synthetic rows (weighted at %.0f%%)"
        % (100 * card["training_data"].get("synthetic_weight", 0)),
    )
    ax.axvline(20, color=INK, lw=1, ls="--")
    ax.text(20.5, 0.2, "sparse < 20", fontsize=8, color=INK)
    ax.set_title("Training rows per state: real vs synthetic", loc="left", color=INK)
    ax.legend(frameon=False, loc="lower right")
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def effect_chart(card: dict, path: Path) -> None:
    c = card["training_data"].get("comparison")
    if not c:
        return
    fig, axes = plt.subplots(1, 3, figsize=(10, 3.4))
    for ax, key, title in zip(
        axes,
        ("spearman", "rmse_sparse_states", "rmse_dense_states"),
        (
            "Held-out Spearman (higher better)",
            "Lift RMSE, sparse states",
            "Lift RMSE, dense states",
        ),
        strict=True,
    ):
        ax.bar(
            ["real only", "+ synthetic"],
            [c["real_only"][key], c["augmented"][key]],
            color=[REAL, SYN],
        )
        ax.set_title(title, fontsize=9, loc="left", color=INK)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
    fig.suptitle("Same folds, real validation rows only", fontsize=9, color=INK, x=0.01, ha="left")
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def _f(v, digits: int = 3) -> str:
    return "n/a" if v is None else f"{v:.{digits}f}"


def markdown(card: dict, model: StateModel, success: SuccessModel | None) -> str:
    td, ev = card["training_data"], card["evaluation"]
    cfg = MarketPotentialConfig()
    lines = [
        "# Kizuna Signal: India model report",
        "",
        f"Model `{card['model_version']}`, trained {card['trained_at']}. {card['n_labelled_titles']} labelled titles, "
        f"{card['n_states']} states and UTs.",
        "",
        "## Training data",
        "",
        f"* Real title x state rows: {td['real_rows']}",
        f"* Synthetic rows: {td['synthetic_rows']} (used in final model: {td['synthetic_used']})",
    ]
    if td.get("comparison"):
        a, b = td["comparison"]["real_only"], td["comparison"]["augmented"]
        lines += [
            f"* Synthetic weight: {td['synthetic_weight']:.0%} of a real row ({td['synthetic_version']})",
            "",
            "### Effect of the synthetic rows (held-out, real rows only, identical folds)",
            "",
            "| | real only | + synthetic |",
            "|---|---|---|",
            f"| Spearman (state ranking) | {a['spearman']:.3f} | {b['spearman']:.3f} |",
            f"| Top-3 state hit rate | {a['top3_hit']:.3f} | {b['top3_hit']:.3f} |",
            f"| Lift RMSE, sparse states | {_f(a['rmse_sparse_states'])} | {_f(b['rmse_sparse_states'])} |",
            f"| Lift RMSE, dense states | {_f(a['rmse_dense_states'])} | {_f(b['rmse_dense_states'])} |",
            "",
            "Synthetic rows are weighted averages of similar titles and of the title's own related states. "
            "They add no observations. Read the table as: error moves slightly, ranking skill does not "
            "demonstrably change (the Spearman 95% intervals overlap heavily).",
            "",
        ]
    sp = ev["spearman"]
    lines += [
        "## Held-out accuracy (final model)",
        "",
        f"* Spearman across states: {sp['mean']:.3f} (95% {sp['ci95'][0]:.3f} to {sp['ci95'][1]:.3f}) over {ev['oof_titles']} titles",
        f"* Top-3 state hit rate: {ev['top3_hit']['mean']:.3f} against {ev['top3_hit_chance']:.3f} by chance",
        f"* 80% interval observed coverage: {ev['intervals']['oof_coverage']:.1%}",
        "",
    ]

    lines += [
        "## India success score: component validation",
        "",
        f"A component counts toward the score only if its held-out Spearman is at least {MIN_SKILL}.",
        "",
        "| Component | Weight | Held-out Spearman | Status |",
        "|---|---|---|---|",
    ]
    skill = {"regional_opportunity": sp["mean"]}
    if success is not None:
        skill |= {
            "content_fit": success.report["loo_spearman"],
            "comparable_performance": success.report["comparables_loo_spearman"],
        }
    counted = 0.0
    for key, label in (
        ("content_fit", "Content fit"),
        ("demand_momentum", "Demand momentum"),
        ("regional_opportunity", "Regional opportunity"),
        ("engagement_quality", "Engagement quality"),
        ("comparable_performance", "Comparable performance"),
    ):
        w = getattr(cfg, key)
        if key not in skill:
            lines.append(f"| {label} | {w:.0%} | n/a | unavailable for an unreleased title |")
            continue
        ok = skill[key] >= MIN_SKILL
        counted += w if ok else 0
        lines.append(
            f"| {label} | {w:.0%} | {skill[key]:.3f} | {'counted' if ok else 'shown, excluded'} |"
        )
    lines += [
        "",
        f"Weight actually counted: {counted:.0%}. Scores are relative (50 = typical anime in the training set), "
        "not revenue or viewership.",
        "",
    ]
    if success is not None:
        r = success.report
        lines += [
            f"Content-fit model: {r['n_titles']} titles, leave-one-franchise-out R2 {r['loo_r2']:.3f}, "
            f"Spearman {r['loo_spearman']:.3f}. Target is {r['target']}.",
            "",
        ]

    lines += [
        "## Per-state coverage and held-out error",
        "",
        "| State | Real titles | Synthetic rows | Sparse | Bias | RMSE |",
        "|---|---|---|---|---|---|",
    ]
    for s in sorted(card["states"], key=lambda r: r["real_titles"]):
        bias = "" if s["heldout_bias"] is None else f"{s['heldout_bias']:+.2f}"
        rmse = "" if s["heldout_rmse"] is None else f"{s['heldout_rmse']:.2f}"
        lines.append(
            f"| {s['name']} | {s['real_titles']} | {s['synthetic_rows']} | {'yes' if s['sparse'] else ''} | {bias} | {rmse} |"
        )
    lines += ["", "## Limitations", ""] + [f"* {x}" for x in card["limitations"]]
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", type=Path, default=Path("models"))
    ap.add_argument("--csv", type=Path, default=Path("csv"))
    ap.add_argument("--out", type=Path, default=Path("results"))
    args = ap.parse_args()

    model = StateModel.load(args.models)
    success = SuccessModel.from_csv(model, args.csv)
    card = build.model_card(model, success)
    args.out.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(card["states"]).to_csv(args.out / "state_coverage.csv", index=False)
    coverage_chart(card, args.out / "08_training_rows_per_state.png")
    effect_chart(card, args.out / "09_synthetic_effect.png")
    (args.out / "MODEL_REPORT.md").write_text(markdown(card, model, success), encoding="utf-8")
    print(f"wrote {args.out / 'MODEL_REPORT.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
