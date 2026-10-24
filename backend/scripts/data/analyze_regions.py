"""Which anime content performs better in which Indian state, plus model-result charts.

    python backend/scripts/data/analyze_regions.py --data data/processed --models models --out results

Interest index: a title's share of post-release India search interest in a state, rescaled
by the number of states that had signal for that title, so 1.0 = that title's average
state, 1.5 = 50% above its own average. A group's lift is the mean index over its titles;
cells are only called significant when the 95% bootstrap interval over titles excludes 1.
Search interest is curiosity, not viewership.
"""

import argparse
import json
import os
import sys
from pathlib import Path

os.environ.setdefault(
    "OPENBLAS_NUM_THREADS", "1"
)  # avoid allocation failures beside the collectors
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # backend/, so `app` imports
from app.core.paths import DATA_DIR, MODELS_DIR, REPORTS_DIR  # noqa: E402
from app.ml.states import STATES  # noqa: E402

# Validated reference palette (blue sequential/diverging arm, red arm, neutral gray midpoint).
INK, MUTED, SURFACE, GRID = "#0b0b0b", "#52514e", "#fcfcfb", "#e4e3df"
BLUE, RED, GRAY = "#2a78d6", "#e34948", "#f0efec"
SEQ = LinearSegmentedColormap.from_list("seq", ["#cde2fb", "#6da7ec", "#256abf", "#0d366b"])
DIV = LinearSegmentedColormap.from_list(
    "div", ["#184f95", "#6da7ec", GRAY, "#ee8f8e", "#b8302f"][::-1]
)
MIN_TITLES = 5
rng = np.random.default_rng(0)

plt.rcParams.update(
    {
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "savefig.facecolor": SURFACE,
        "text.color": INK,
        "axes.labelcolor": MUTED,
        "xtick.color": MUTED,
        "ytick.color": MUTED,
        "axes.edgecolor": GRID,
        "font.size": 9,
        "axes.spines.top": False,
        "axes.spines.right": False,
    }
)


def load(data: Path):
    titles = pd.DataFrame(
        [
            json.loads(line)
            for line in (data / "titles.jsonl").read_text(encoding="utf-8").splitlines()
            if line
        ]
    )
    labels = pd.read_csv(data / "state_labels.csv")
    labels["state_name"] = labels["state"].map(STATES)
    labels["n_valid"] = labels.groupby("title_id")["state"].transform("size")
    labels["index"] = labels["share"] * labels["n_valid"]
    return titles, labels


def explode(titles: pd.DataFrame, column: str) -> pd.DataFrame:
    return titles[["title_id", column]].explode(column).dropna().rename(columns={column: "group"})


def group_lift(groups: pd.DataFrame, labels: pd.DataFrame, n_boot: int = 500) -> pd.DataFrame:
    """Mean interest index per (group, state) with a bootstrap interval over titles."""
    merged = groups.merge(labels[["title_id", "state_name", "index"]], on="title_id")
    out = []
    for (g, s), part in merged.groupby(["group", "state_name"]):
        v = part["index"].to_numpy()
        if len(v) < MIN_TITLES:
            continue
        boots = [rng.choice(v, len(v)).mean() for _ in range(n_boot)]
        lo, hi = np.percentile(boots, [2.5, 97.5])
        out.append(
            {
                "group": g,
                "state": s,
                "n_titles": len(v),
                "lift": v.mean(),
                "ci_lo": lo,
                "ci_hi": hi,
                "significant": bool(lo > 1 or hi < 1),
            }
        )
    return pd.DataFrame(out)


def heatmap(lift: pd.DataFrame, path: Path, title: str, subtitle: str, max_groups: int = 14):
    if lift.empty:
        return
    keep = lift.groupby("group")["n_titles"].max().nlargest(max_groups).index
    lift = lift[lift["group"].isin(keep)]
    mat = lift.pivot(index="group", columns="state", values="lift")
    sig = (
        lift.pivot(index="group", columns="state", values="significant")
        .reindex_like(mat)
        .fillna(False)
    )
    order = mat.mean().sort_values(ascending=False).index
    mat, sig = mat[order], sig[order]
    fig, ax = plt.subplots(
        figsize=(max(9, 0.42 * mat.shape[1] + 3), max(3.2, 0.42 * mat.shape[0] + 2))
    )
    vmax = max(1.5, float(np.nanmax(mat.values)))
    im = ax.imshow(
        mat.values,
        cmap=DIV,
        norm=TwoSlopeNorm(1.0, vmin=min(0.5, np.nanmin(mat.values)), vmax=vmax),
        aspect="auto",
    )
    ax.set_xticks(range(mat.shape[1]), mat.columns, rotation=60, ha="right")
    ax.set_yticks(range(mat.shape[0]), mat.index)
    for i in range(mat.shape[0]):
        for j in range(mat.shape[1]):
            if sig.values[i, j]:  # label only cells whose interval excludes 1
                v = mat.values[i, j]
                ax.text(
                    j,
                    i,
                    f"{v:.1f}",
                    ha="center",
                    va="center",
                    fontsize=7,
                    fontweight="bold",
                    color="white" if (v > 1.5 or v < 0.65) else INK,
                )
    ax.set_title(title, loc="left", fontsize=12, fontweight="bold", pad=24)
    ax.text(0, 1.04, subtitle, transform=ax.transAxes, fontsize=8.5, color=MUTED)
    ax.tick_params(length=0)
    for sp in ax.spines.values():
        sp.set_visible(False)
    cb = fig.colorbar(im, ax=ax, fraction=0.02, pad=0.01)
    cb.set_label("index (1.0 = average)", color=MUTED, fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def state_baseline(labels: pd.DataFrame, path: Path):
    g = (
        labels.groupby("state_name")
        .agg(index=("index", "mean"), n=("title_id", "nunique"))
        .sort_values("index")
    )
    fig, ax = plt.subplots(figsize=(8, 0.26 * len(g) + 1.6))
    ax.barh(g.index, g["index"], color=BLUE, height=0.62)
    ax.axvline(1, color=MUTED, lw=0.8, ls="--")
    ax.set_xlabel("average interest index (1.0 = a title's average state)")
    ax.set_title(
        "Where anime search interest concentrates", loc="left", fontsize=12, fontweight="bold"
    )
    for y, (i, n) in enumerate(zip(g["index"], g["n"], strict=True)):
        ax.text(i + 0.02, y, f"{i:.2f}  (n={n})", va="center", fontsize=7.5, color=MUTED)
    ax.grid(axis="x", color=GRID, lw=0.6)
    ax.set_axisbelow(True)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def top_states_per_genre(lift: pd.DataFrame, path: Path, n_genres: int = 6, k: int = 5):
    genres = lift.groupby("group")["n_titles"].max().nlargest(n_genres).index
    if len(genres) == 0:
        return
    cols = 3
    rows = int(np.ceil(len(genres) / cols))
    fig, axes = plt.subplots(rows, cols, figsize=(12, 2.6 * rows), squeeze=False)
    for ax, g in zip(axes.ravel(), genres, strict=False):  # the grid can have spare axes
        d = lift[lift["group"] == g].nlargest(k, "lift").iloc[::-1]
        ax.barh(d["state"], d["lift"], color=BLUE, height=0.6)
        ax.axvline(1, color=MUTED, lw=0.8, ls="--")
        ax.set_title(
            f"{g}  (n up to {int(lift[lift['group'] == g]['n_titles'].max())})",
            loc="left",
            fontsize=10,
            fontweight="bold",
        )
        ax.grid(axis="x", color=GRID, lw=0.6)
        ax.set_axisbelow(True)
        for y, v in enumerate(d["lift"]):
            ax.text(v + 0.01, y, f"{v:.2f}", va="center", fontsize=7.5, color=MUTED)
    for ax in axes.ravel()[len(genres) :]:
        ax.axis("off")
    fig.suptitle("Top five states per genre", x=0.01, ha="left", fontsize=12, fontweight="bold")
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def title_state_heatmap(labels: pd.DataFrame, titles: pd.DataFrame, path: Path, n: int = 20):
    names = titles.set_index("title_id")["english_title"].fillna(
        titles.set_index("title_id")["romanized_title"]
    )
    top = labels.groupby("title_id").size().nlargest(n).index
    mat = labels[labels["title_id"].isin(top)].pivot(
        index="title_id", columns="state_name", values="index"
    )
    mat.index = [str(names.get(i, i))[:34] for i in mat.index]
    mat = mat[mat.mean().sort_values(ascending=False).index]
    fig, ax = plt.subplots(figsize=(max(9, 0.42 * mat.shape[1] + 3), 0.34 * len(mat) + 2))
    im = ax.imshow(mat.values, cmap=SEQ, aspect="auto")
    ax.set_xticks(range(mat.shape[1]), mat.columns, rotation=60, ha="right")
    ax.set_yticks(range(mat.shape[0]), mat.index)
    ax.set_title(
        "Per-title interest index by state (blank = too little signal)",
        loc="left",
        fontsize=12,
        fontweight="bold",
    )
    ax.tick_params(length=0)
    for sp in ax.spines.values():
        sp.set_visible(False)
    fig.colorbar(im, ax=ax, fraction=0.02, pad=0.01).set_label("interest index", color=MUTED)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def model_charts(report: dict, labels: pd.DataFrame, out: Path):
    metrics = report["metrics"]
    order = ["state_mean", "ridge_genre_state", "xgboost", "ensemble"]
    names = {
        "state_mean": "State average",
        "ridge_genre_state": "Ridge",
        "xgboost": "XGBoost",
        "ensemble": "Ensemble",
    }
    chance = 3 / max(labels.groupby("title_id").size().mean(), 3)
    fig, axes = plt.subplots(1, 2, figsize=(11, 3.6))
    for ax, key, title in (
        (axes[0], "top3_hit", "Top-3 state hit rate"),
        (axes[1], "spearman", "Rank correlation"),
    ):
        m = [metrics[o][key]["mean"] for o in order]
        lo = [m[i] - metrics[o][key]["ci95"][0] for i, o in enumerate(order)]
        hi = [metrics[o][key]["ci95"][1] - m[i] for i, o in enumerate(order)]
        ax.bar(
            [names[o] for o in order],
            m,
            yerr=[lo, hi],
            color=[GRAY if o == "state_mean" else BLUE for o in order],
            edgecolor=MUTED,
            linewidth=0.6,
            width=0.55,
            error_kw={"ecolor": MUTED, "lw": 1, "capsize": 3},
        )
        if key == "top3_hit":
            ax.axhline(chance, color=RED, lw=1, ls="--")
            ax.text(-0.45, chance, "random", color=RED, fontsize=8, va="bottom", ha="left")
        ax.set_title(title, loc="left", fontsize=11, fontweight="bold")
        ax.grid(axis="y", color=GRID, lw=0.6)
        ax.set_axisbelow(True)
        for x, v in enumerate(m):
            ax.text(
                x,
                v + hi[x] + 0.01 * max(m),
                f"{v:.2f}",
                ha="center",
                va="bottom",
                fontsize=8,
                color=INK,
            )
    fig.suptitle(
        f"Held-out titles released from {report['test_release_from']} "
        f"(n={report['n_test_titles']}; bars show 95% bootstrap interval)",
        x=0.01,
        ha="left",
        fontsize=9,
        color=MUTED,
    )
    fig.tight_layout()
    fig.savefig(out / "06_model_performance.png", dpi=160)
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(10, 3.2))
    comp = report["component_importance"]
    axes[0].barh(list(comp), list(comp.values()), color=BLUE, height=0.55)
    axes[0].set_title(
        "What drives XGBoost (mean |SHAP| share)", loc="left", fontsize=10, fontweight="bold"
    )
    ab = report["ablation_top3_hit"]
    axes[1].barh(list(ab), list(ab.values()), color=BLUE, height=0.55)
    axes[1].axvline(chance, color=RED, lw=1, ls="--")
    axes[1].set_title(
        "Top-3 hit using one feature group", loc="left", fontsize=10, fontweight="bold"
    )
    for ax in axes:
        ax.grid(axis="x", color=GRID, lw=0.6)
        ax.set_axisbelow(True)
    fig.tight_layout()
    fig.savefig(out / "07_model_components.png", dpi=160)
    plt.close(fig)


def write_insights(
    genre_lift: pd.DataFrame,
    theme_lift: pd.DataFrame,
    labels: pd.DataFrame,
    titles: pd.DataFrame,
    report: dict | None,
    out: Path,
):
    both = pd.concat(
        [genre_lift.assign(kind="genre"), theme_lift.assign(kind="theme")], ignore_index=True
    )
    both.round(3).to_csv(out / "region_insights.csv", index=False)
    lines = [
        "# Which content performs better in which region",
        "",
        f"Based on {labels['title_id'].nunique()} titles, {labels['state'].nunique()} states with signal. "
        "Index 1.0 = a title's average state. A result is listed only when its 95% bootstrap interval "
        f"(over titles) excludes 1.0 and at least {MIN_TITLES} titles support it. Search interest is "
        "curiosity, not viewership.",
        "",
    ]
    for kind, lift in (("Genre", genre_lift), ("Theme/tag", theme_lift)):
        lines += [f"## {kind} over- and under-indexing", ""]
        sig = lift[lift["significant"]] if len(lift) else lift
        if sig.empty:
            lines += ["No statistically clear pattern yet; collect more titles.", ""]
            continue
        for g, part in sig.groupby("group"):
            up = part[part["lift"] > 1].nlargest(3, "lift")
            down = part[part["lift"] < 1].nsmallest(3, "lift")
            bits = []
            if len(up):
                bits.append(
                    "stronger in "
                    + ", ".join(
                        f"{r.state} ({r.lift:.2f}x, n={r.n_titles})" for r in up.itertuples()
                    )
                )
            if len(down):
                bits.append(
                    "weaker in "
                    + ", ".join(
                        f"{r.state} ({r.lift:.2f}x, n={r.n_titles})" for r in down.itertuples()
                    )
                )
            lines.append(f"- **{g}**: " + "; ".join(bits))
        lines.append("")
    names = titles.set_index("title_id")["english_title"]
    lines += ["## Best-performing titles per state (highest index)", ""]
    for s, part in labels.groupby("state_name"):
        top = part.nlargest(3, "index")
        lines.append(
            f"- **{s}**: "
            + ", ".join(
                f"{names.get(r.title_id, r.title_id)} ({r.index:.2f}x)" for r in top.itertuples()
            )
        )
    if report:
        m = report["metrics"]
        lines += [
            "",
            "## Model result (held-out, newest titles)",
            "",
            f"- Top-3 state hit rate: XGBoost {m['xgboost']['top3_hit']['mean']:.2f}, "
            f"ensemble {m['ensemble']['top3_hit']['mean']:.2f}, "
            f"Ridge {m['ridge_genre_state']['top3_hit']['mean']:.2f}, "
            f"state-average baseline {m['state_mean']['top3_hit']['mean']:.2f} "
            f"(n={report['n_test_titles']} test titles).",
            f"- Beats the baselines: **{report['beats_baselines']}**. "
            f"Interval coverage {report['intervals']['observed']:.2f} vs nominal {report['intervals']['nominal']}.",
        ]
    (out / "REGIONAL_INSIGHTS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, default=DATA_DIR / "processed")
    ap.add_argument("--models", type=Path, default=MODELS_DIR)
    ap.add_argument("--out", type=Path, default=REPORTS_DIR)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    titles, labels = load(args.data)
    labels = labels[labels["title_id"].isin(titles["title_id"])]
    genre_lift = group_lift(explode(titles, "genres"), labels)
    theme_lift = group_lift(explode(titles, "themes"), labels)

    state_baseline(labels, args.out / "03_state_baseline.png")
    heatmap(
        genre_lift,
        args.out / "01_genre_state_lift.png",
        "Genre x state: where each genre over- or under-performs",
        f"Blue = above the title's average state, red = below. Numbers shown only where the 95% interval "
        f"excludes 1.0 (genres with >= {MIN_TITLES} titles).",
    )
    heatmap(
        theme_lift,
        args.out / "04_theme_state_lift.png",
        "Tag x state: which themes travel where",
        "Same encoding as the genre chart; the 14 best-supported tags.",
    )
    top_states_per_genre(genre_lift, args.out / "02_top_states_per_genre.png")
    title_state_heatmap(labels, titles, args.out / "05_title_state_heatmap.png")

    report_path = args.models / "initial_report.json"
    report = json.loads(report_path.read_text(encoding="utf-8")) if report_path.exists() else None
    if report:
        model_charts(report, labels, args.out)
    write_insights(genre_lift, theme_lift, labels, titles, report, args.out)
    print(f"wrote charts and REGIONAL_INSIGHTS.md to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
