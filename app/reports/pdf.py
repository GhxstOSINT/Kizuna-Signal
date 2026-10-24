"""PDF report: charts and the worked mathematics, drawn with matplotlib only (no extra dependency)."""

import io
import textwrap

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.backends.backend_pdf import PdfPages  # noqa: E402
from matplotlib.colors import TwoSlopeNorm  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402

PAGE = (8.27, 11.69)
INK, MUTED, GRID = "#1f2933", "#6b7785", "#e3e7ec"
UP, DOWN, NEUTRAL = "#5e3c99", "#b35806", "#8a96a3"  # colour-blind-safe diverging pair (PuOr)
CMAP = plt.get_cmap("PuOr")

# Schematic tile map (col, row), north at the top. Positions are approximate, not to scale.
TILES = {
    "IN-LA": (1, 0),
    "IN-JK": (2, 0),
    "IN-PB": (1, 1),
    "IN-HP": (2, 1),
    "IN-UT": (3, 1),
    "IN-CH": (0, 2),
    "IN-HR": (1, 2),
    "IN-DL": (2, 2),
    "IN-UP": (3, 2),
    "IN-BR": (4, 2),
    "IN-SK": (5, 2),
    "IN-AR": (6, 2),
    "IN-RJ": (1, 3),
    "IN-MP": (2, 3),
    "IN-CT": (3, 3),
    "IN-JH": (4, 3),
    "IN-WB": (5, 3),
    "IN-AS": (6, 3),
    "IN-NL": (7, 3),
    "IN-GJ": (1, 4),
    "IN-MH": (2, 4),
    "IN-TG": (3, 4),
    "IN-OR": (4, 4),
    "IN-ML": (6, 4),
    "IN-MN": (7, 4),
    "IN-DN": (1, 5),
    "IN-GA": (2, 5),
    "IN-KA": (3, 5),
    "IN-AP": (4, 5),
    "IN-TR": (6, 5),
    "IN-MZ": (7, 5),
    "IN-KL": (3, 6),
    "IN-TN": (4, 6),
    "IN-PY": (5, 6),
    "IN-LD": (1, 7),
    "IN-AN": (7, 7),
}


def _page(title: str, subtitle: str = "", n: int = 0):
    fig = plt.figure(figsize=PAGE)
    fig.text(0.07, 0.965, "KIZUNA SIGNAL  |  India performance report", fontsize=8, color=MUTED)
    fig.text(0.93, 0.965, str(n), fontsize=8, color=MUTED, ha="right")
    fig.text(0.07, 0.935, title, fontsize=17, weight="bold", color=INK)
    if subtitle:
        fig.text(0.07, 0.912, subtitle, fontsize=9, color=MUTED)
    return fig


def _clean(ax, grid_axis="x"):
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(colors=MUTED, labelsize=8, length=0)
    ax.grid(axis=grid_axis, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def _num(v, digits: int = 2) -> str:
    return "n/a" if v is None else f"{v:.{digits}f}"


def _wrap(text: str, width: int) -> str:
    return "\n".join(textwrap.wrap(text, width))


# ---------------------------------------------------------------------------- pages
def _summary(r: dict, n: int):
    t, s, ind = r["title"], r["success"], r["india"]
    fig = _page(
        t["name_en"],
        f"{t['format']}  |  {', '.join(t['genres'])}  |  {t['studio'] or 'studio n/a'}"
        f"  |  {t['release_date'] or 'launch date n/a'}",
        n,
    )
    ax = fig.add_axes([0.07, 0.62, 0.86, 0.26])
    ax.axis("off")
    if s:
        ax.text(0, 0.78, f"{s['rating']:.0f}", fontsize=64, weight="bold", color=INK, va="center")
        ax.text(
            0.22,
            0.86,
            f"India success rating, out of 100 ({s['rating_band']})",
            fontsize=13,
            weight="bold",
            color=INK,
        )
        ax.text(
            0.22,
            0.70,
            f"80% range {s['rating_low']:.0f}-{s['rating_high']:.0f}  |  raw weighted score {s['score']:.0f}"
            f" ({s['band']})  |  weight measured {s['coverage']:.0%}",
            fontsize=9,
            color=MUTED,
        )
        ax.text(
            0.22,
            0.58,
            _wrap("Rating = share of the training titles this one outscores. " + s["meaning"], 70),
            fontsize=8,
            color=MUTED,
            va="top",
        )
    ax.text(0, 0.22, f"{ind['confidence']:.0f}", fontsize=34, weight="bold", color=INK, va="center")
    ax.text(
        0.22, 0.30, "Confidence (separate from the score)", fontsize=11, weight="bold", color=INK
    )
    ax.text(
        0.22, 0.14, "Warnings: " + (", ".join(ind["warnings"]) or "none"), fontsize=8, color=MUTED
    )

    if s:
        ax = fig.add_axes([0.28, 0.33, 0.62, 0.24])
        comps = s["components"]
        y = np.arange(len(comps))[::-1]
        for yi, c in zip(y, comps, strict=True):
            if c["status"] == "ok":
                ax.barh(yi, c["value"], color=UP, height=0.55)
                ax.plot([c["low"], c["high"]], [yi, yi], color=INK, lw=1.6)
                ax.text(101, yi, f"{c['value']:.0f}", va="center", fontsize=8, color=INK)
            elif c["status"] == "unvalidated":
                ax.barh(yi, c["value"], color="none", edgecolor=NEUTRAL, hatch="///", height=0.55)
                ax.text(101, yi, f"{c['value']:.0f}", va="center", fontsize=8, color=MUTED)
                ax.text(
                    c["value"] + 8,
                    yi + 0.38,
                    f"unvalidated (rho {c['validation_spearman']:.2f}), not in score",
                    va="center",
                    fontsize=6.5,
                    color=MUTED,
                )
            else:
                ax.barh(yi, 100, color=GRID, height=0.55)
                ax.text(2, yi, "not measured", va="center", fontsize=8, color=MUTED)
        ax.axvline(50, color=MUTED, lw=1, ls=":")
        ax.set_yticks(y, [f"{c['label']}  ({c['weight']:.0%})" for c in comps])
        ax.set_xlim(0, 108)
        ax.set_title(
            "Components (0-100, 50 = typical anime; line = 80% range; hatched = excluded)",
            fontsize=9,
            color=INK,
            loc="left",
        )
        _clean(ax)
    top, bottom = ind["top_states"], ind["bottom_states"]
    names = {st["state"]: st["name"] for st in r["states"]}
    fig.text(
        0.07, 0.27, "Strongest expected over-performance", fontsize=10, weight="bold", color=UP
    )
    fig.text(
        0.07, 0.255, _wrap(", ".join(names[c] for c in top), 48), fontsize=9, color=INK, va="top"
    )
    fig.text(0.53, 0.27, "Weakest expected performance", fontsize=10, weight="bold", color=DOWN)
    fig.text(
        0.53, 0.255, _wrap(", ".join(names[c] for c in bottom), 48), fontsize=9, color=INK, va="top"
    )
    fig.text(0.07, 0.14, _wrap(ind["note"], 105), fontsize=8, color=MUTED, va="top")
    return fig


def _tile_map(r: dict, n: int):
    fig = _page(
        "India: where the title over-performs",
        "Predicted lift per state (schematic tile map, not to scale)",
        n,
    )
    ax = fig.add_axes([0.07, 0.30, 0.86, 0.58])
    ax.set_aspect("equal")
    ax.axis("off")
    lift = {st["state"]: st["lift"] for st in r["states"]}
    lim = max(0.1, max(abs(v) for v in lift.values()))
    norm = TwoSlopeNorm(0, -lim, lim)
    for code, (c, rw) in TILES.items():
        x, y = c, -rw
        if code in lift:
            colour = CMAP(norm(lift[code]))
            lum = 0.299 * colour[0] + 0.587 * colour[1] + 0.114 * colour[2]
            ax.add_patch(
                FancyBboxPatch(
                    (x + 0.04, y + 0.04),
                    0.92,
                    0.92,
                    boxstyle="round,pad=0,rounding_size=0.08",
                    fc=colour,
                    ec="white",
                )
            )
            ax.text(
                x + 0.5,
                y + 0.58,
                code[3:],
                ha="center",
                va="center",
                fontsize=9,
                weight="bold",
                color="white" if lum < 0.55 else INK,
            )
            ax.text(
                x + 0.5,
                y + 0.28,
                f"{lift[code]:+.2f}",
                ha="center",
                va="center",
                fontsize=7,
                color="white" if lum < 0.55 else INK,
            )
        else:
            ax.add_patch(
                FancyBboxPatch(
                    (x + 0.04, y + 0.04),
                    0.92,
                    0.92,
                    boxstyle="round,pad=0,rounding_size=0.08",
                    fc="#f3f4f6",
                    ec="white",
                )
            )
            ax.text(
                x + 0.5,
                y + 0.5,
                code[3:] + "\nn/a",
                ha="center",
                va="center",
                fontsize=7,
                color=MUTED,
            )
    ax.set_xlim(-0.2, 8.2)
    ax.set_ylim(-8.2, 1.2)
    cax = fig.add_axes([0.25, 0.26, 0.5, 0.012])
    sm = plt.cm.ScalarMappable(norm=norm, cmap=CMAP)
    cb = fig.colorbar(sm, cax=cax, orientation="horizontal")
    cb.outline.set_visible(False)
    cb.ax.tick_params(labelsize=8, colors=MUTED, length=0)
    fig.text(0.25, 0.232, "under-performs vs a typical anime", fontsize=8, color=DOWN)
    fig.text(0.75, 0.232, "over-performs", fontsize=8, color=UP, ha="right")
    fig.text(
        0.07,
        0.17,
        _wrap(
            "Lift is on a log scale and centred: 0 means the same relative interest a typical anime gets "
            "in that state. It says where the title does better than usual, not how many people watch.",
            110,
        ),
        fontsize=8,
        color=MUTED,
        va="top",
    )
    return fig


def _ranking(r: dict, n: int):
    fig = _page(
        "State ranking with 80% intervals",
        "Sorted by predicted lift; whiskers are the conformal interval",
        n,
    )
    ax = fig.add_axes([0.27, 0.07, 0.66, 0.82])
    sts = r["states"][::-1]
    y = np.arange(len(sts))
    ax.barh(
        y,
        [s["lift"] for s in sts],
        color=[UP if s["lift"] >= 0 else DOWN for s in sts],
        height=0.62,
    )
    for yi, s in zip(y, sts, strict=True):
        ax.plot([s["low"], s["high"]], [yi, yi], color=INK, lw=0.9)
    ax.axvline(0, color=INK, lw=0.8)
    ax.set_yticks(y, [f"{s['rank']:>2}  {s['name'][:26]}" for s in sts], fontsize=7)
    ax.set_xlabel("predicted lift (log scale)", fontsize=8, color=MUTED)
    _clean(ax)
    return fig


def _share_and_context(r: dict, n: int):
    fig = _page("Demand share, drivers and comparables", "", n)
    ax = fig.add_axes([0.27, 0.58, 0.66, 0.30])
    top = sorted(r["states"], key=lambda s: -s["expected_share"])[:12][::-1]
    ax.barh(
        [s["name"][:26] for s in top],
        [100 * s["expected_share"] for s in top],
        color=UP,
        height=0.6,
    )
    ax.set_title(
        "Expected share of India demand, top 12 states (%)", fontsize=9, loc="left", color=INK
    )
    _clean(ax)

    ax = fig.add_axes([0.27, 0.33, 0.30, 0.15])
    f = r["india"]["confidence_factors"]
    ax.barh(list(f)[::-1], [f[k] for k in list(f)[::-1]], color=NEUTRAL, height=0.55)
    ax.set_xlim(0, 1)
    ax.set_title("Confidence factors (0-1)", fontsize=9, loc="left", color=INK)
    _clean(ax)

    ax = fig.add_axes([0.07, 0.07, 0.86, 0.20])
    ax.axis("off")
    ax.text(0, 1, "Most similar earlier titles", fontsize=9, weight="bold", color=INK, va="top")
    for i, c in enumerate(r["comparables"]):
        ax.text(
            0,
            0.82 - i * 0.16,
            f"{i + 1}.  {c.get('name') or c['title_id']}",
            fontsize=8.5,
            color=INK,
            va="top",
        )
        ax.text(
            1,
            0.82 - i * 0.16,
            f"similarity {c['similarity']:.2f}",
            fontsize=8.5,
            color=MUTED,
            ha="right",
            va="top",
        )
    st = r["states"][0]
    d = ", ".join(f"{x['feature']} ({x['contribution']:+.3f})" for x in st["drivers"])
    fig.text(
        0.07,
        0.30,
        _wrap(f"Top driver features for {st['name']}: {d}", 115),
        fontsize=8,
        color=MUTED,
        va="top",
    )
    return fig


def _math(r: dict, n: int):
    fig = _page("The mathematics", "Every number below is the one used for this title", n)
    y = 0.885
    for f in r.get("formulas", []):
        fig.text(0.07, y, f["name"], fontsize=9, weight="bold", color=INK)
        fig.text(0.07, y - 0.030, f["latex"], fontsize=12, color=INK)
        lines = [f.get("note"), f.get("worked") and "Worked: " + f["worked"]]
        text = _wrap("  ".join(x for x in lines if x), 118)
        if text:
            fig.text(0.07, y - 0.060, text, fontsize=7.5, color=MUTED, va="top")
        y -= 0.105 if text.count("\n") < 1 else 0.115
    s = r["success"]
    if s:
        w = ", ".join(f"{c['label']} {c['weight']:.0%}" for c in s["components"])
        fig.text(
            0.07,
            0.035,
            _wrap(
                f"Weights ({s['config_version']}): {w}. Unavailable components are dropped and the rest "
                f"renormalised.",
                120,
            ),
            fontsize=7.5,
            color=MUTED,
            va="bottom",
        )
    return fig


def _evaluation(r: dict, n: int):
    m = r["model"]
    ev = m["evaluation"]
    fig = _page(
        "How much to trust this",
        f"Model {m['version']}  |  {m['n_labelled_titles']} labelled titles  |  "
        f"{ev['oof_titles']} held-out titles",
        n,
    )
    ax = fig.add_axes([0.30, 0.64, 0.6, 0.20])
    rows = [
        ("Rank correlation (Spearman)", ev["spearman"], 0.0),
        ("Top-3 state hit rate", ev["top3_hit"], ev["top3_hit_chance"]),
    ]
    for i, (_label, met, chance) in enumerate(rows[::-1]):
        ax.barh(i, met["mean"], color=UP, height=0.45)
        ax.plot(met["ci95"], [i, i], color=INK, lw=1.6)
        ax.plot([chance, chance], [i - 0.35, i + 0.35], color=DOWN, lw=2)
    ax.set_yticks(range(2), [x[0] for x in rows[::-1]], fontsize=8)
    ax.set_title(
        "Held-out accuracy (bar = mean, line = 95% interval, orange = chance level)",
        fontsize=9,
        loc="left",
        color=INK,
    )
    _clean(ax)

    cal = (
        f"Interval calibration: nominal {m['interval_nominal']:.0%}, observed out-of-fold "
        f"{m['interval_oof_coverage']:.0%}.   Validation: {ev['scheme']}."
    )
    fig.text(0.07, 0.58, _wrap(cal, 110), fontsize=8.5, color=INK, va="top")
    if r["success"]:
        sm = r["success"]["model"]
        fig.text(
            0.07,
            0.52,
            _wrap(
                f"Content-fit model: {sm['n_titles']} titles, leave-one-franchise-out R2 = "
                f"{sm['loo_r2']:.2f}, Spearman = {sm['loo_spearman']:.2f}. Target is {sm['target']}.",
                110,
            ),
            fontsize=8.5,
            color=INK,
            va="top",
        )
    td = m.get("training_data") or {}
    if td.get("comparison"):
        c = td["comparison"]
        a, b = c.get("real_only"), c.get("augmented")
        line = (
            f"Training rows: {td['real_rows']} real + {td['synthetic_rows']} synthetic (weight {td['synthetic_weight']:.0%}). "
            f"Held-out Spearman {a['spearman']:.2f} without vs {b['spearman']:.2f} with synthetic rows; lift RMSE in sparse "
            f"states {_num(a['rmse_sparse_states'])} vs {_num(b['rmse_sparse_states'])}."
        )
        fig.text(0.07, 0.47, _wrap(line, 110), fontsize=8.5, color=INK, va="top")
    fig.text(0.07, 0.40, "Limitations", fontsize=11, weight="bold", color=INK)
    fig.text(
        0.07,
        0.385,
        "\n".join("- " + _wrap(x, 108).replace("\n", "\n  ") for x in r["limitations"]),
        fontsize=8,
        color=MUTED,
        va="top",
        linespacing=1.5,
    )
    fig.text(
        0.07,
        0.04,
        f"Generated {r['generated_at']}  |  {r['report_version']}  |  scoring {r['success']['config_version'] if r['success'] else 'n/a'}",
        fontsize=7,
        color=MUTED,
    )
    return fig


def to_pdf(report: dict) -> bytes:
    buf = io.BytesIO()
    pages = (
        [_summary, _tile_map, _ranking, _share_and_context]
        + ([_math] if report.get("formulas") else [])
        + [_evaluation]
    )
    with PdfPages(
        buf,
        metadata={
            "Title": f"Kizuna Signal - {report['title']['name_en']}",
            "Author": "Kizuna Signal",
        },
    ) as pdf:
        for i, page in enumerate(pages, 1):
            fig = page(report, i)
            pdf.savefig(fig)
            plt.close(fig)
    return buf.getvalue()
