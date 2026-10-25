"""PDF of one analysis, styled and ordered like the dashboard's Decision page.

Same look as the site: Instrument Serif headings and numbers, DM Sans body, IBM Plex Mono labels, the warm
paper background, rounded cards, dot badges and the fox mark (fonts in `fonts/`, converted from the
dashboard's own; the map is the dashboard's, see `india_map.json`). Same order as the page: title details,
score, evidence notes, model validation, what shaped the score, regional opportunity, evidence ledger,
comparable evidence, source health. Text is English (the API's own wording); Japanese title names print if
a CJK font is installed. Drawn with matplotlib only: `_Doc` places blocks top to bottom and starts a new
page when the next block does not fit.
"""

import io
import json
import logging
import math
import re
import warnings
from pathlib import Path

import matplotlib
import numpy as np
from matplotlib import font_manager
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.colors import LinearSegmentedColormap, to_rgb
from matplotlib.figure import Figure
from matplotlib.font_manager import FontProperties
from matplotlib.lines import Line2D
from matplotlib.patches import Circle, FancyBboxPatch, Polygon

# Sizes are inches on an A4 page; type is in points.
W, H = 8.27, 11.69
MARGIN, TOP, BOTTOM = 0.65, 1.1, 0.85

# The dashboard's tokens (frontend/src/styles/base.css, animations.css).
PAPER, PANEL, CARD, WHITE = "#f4f4f2", "#fafaf8", "#f8f8f6", "#ffffff"
INK, MUTED, RULE, SOFT, TRACK = "#171817", "#696c69", "#d5d7d4", "#e5e6e3", "#dfe1de"
GREEN, AMBER, RED, GREY, BRAND = "#168765", "#a86a18", "#b44536", "#9a9d99", "#e0601a"
HEAT_LO, HEAT_HI = "#ebe8e1", "#c8362b"
DARK_TEXT, DARK_MUTED = "#f8f8f6", "#aeb1ad"

HERE = Path(__file__).parent
FONT_DIR = HERE / "fonts"
MAP_FILE = HERE / "india_map.json"

# Fallbacks, tried per glyph after the site's fonts, so a Japanese title still prints.
CJK_SANS = [
    "Hiragino Sans",
    "Hiragino Kaku Gothic ProN",
    "Noto Sans CJK JP",
    "Noto Sans JP",
    "IPAexGothic",
    "IPAPGothic",
    "TakaoPGothic",
    "Yu Gothic",
    "Meiryo",
    "MS Gothic",
    "Arial Unicode MS",
]
CJK_SERIF = ["Hiragino Mincho ProN", "Noto Serif CJK JP", "Noto Serif JP", "Yu Mincho"]

BADGE = {
    "strong_opportunity": GREEN,
    "promising_opportunity": GREEN,
    "completed": GREEN,
    "available": GREEN,
    "trained_model": GREEN,
    "test_before_investing": AMBER,
    "partially_completed": AMBER,
    "cached": AMBER,
    "deterministic_fallback": AMBER,
    "limited_opportunity": RED,
    "unavailable": RED,
    "failed": RED,
}

# Same labels as the dashboard (frontend/src/lib/formats.ts and AnalysisPage.tsx).
FORMATS = {
    "anime_series": "Anime series",
    "anime_film": "Anime film",
    "anime_short": "Anime short series",
    "anime_ova": "Anime OVA",
    "anime_ona": "Anime ONA (web release)",
    "anime_special": "Anime special",
    "live_action_series": "Live-action series",
    "live_action_film": "Live-action film",
    "game": "Game",
    "other": "Other",
}
LEGACY_FORMATS = {
    "series": "anime_series",
    "film": "anime_film",
    "animated_film": "anime_film",
    "special": "anime_special",
}
RATINGS = {
    "all_ages": "All ages",
    "7_plus": "7+",
    "13_plus": "13+",
    "16_plus": "16+",
    "18_plus": "18+",
}
MAP_ALIASES = {"Delhi NCR": "Delhi"}
MAP_SHARED_SHAPES = {"Jammu and Kashmir": "Ladakh"}  # the scoring counts Ladakh within J&K

CJK = r"[　-鿿＀-￯]"
TOKEN = re.compile(rf"\s*(?:{CJK}|(?:(?!{CJK})\S)+)")

# Embedding fonts makes fontTools log every table at INFO, which would fill the API log on each download.
logging.getLogger("fontTools").setLevel(logging.WARNING)

_fonts_added = False


def _label(value: str) -> str:
    return re.sub(r"\b\w", lambda m: m.group().upper(), value.replace("_", " "))


def _round(value: float) -> int:
    return math.floor(value + 0.5)  # half up, like the page's Math.round


def _format_label(value: str) -> str:
    key = re.sub(r"[\s-]+", "_", value.strip().lower())
    key = LEGACY_FORMATS.get(key, key)
    return FORMATS.get(key, value.replace("_", " "))


def _mix(share: float) -> tuple[float, float, float]:
    """The dashboard's colour-mix(hi share%, lo): share 0..1."""
    lo, hi = np.array(to_rgb(HEAT_LO)), np.array(to_rgb(HEAT_HI))
    return tuple(lo + (hi - lo) * share)


def _title_rows(t: dict) -> list[tuple[str, str]]:
    rows = [
        ("Title", f"{t['name']} / {t['english_title']}" if t["english_title"] else t["name"]),
        ("Format", _format_label(t["content_format"])),
        ("Genre", t["primary_genre"]),
        ("Source", t["source_material"]),
        ("Studio", t["studio"]),
        ("Director", t["director"]),
        ("Episodes", str(t["episode_count"]) if t["episode_count"] else None),
        ("Age rating", RATINGS.get(t["age_rating"], t["age_rating"]) if t["age_rating"] else None),
        ("Audience", t["target_audience"]),
        ("Franchise", t["franchise_status"]),
        ("Release", t["expected_release_period"]),
        ("Platform", t["target_platform"]),
        ("Budget", _label(t["marketing_budget"]) if t["marketing_budget"] else None),
        ("Languages", ", ".join(t["target_languages"])),
        ("States", ", ".join(t["target_states"])),
    ]
    return [(name, value) for name, value in rows if value]


def _font_stacks() -> dict[str, list[str]]:
    """Per style, the site's font first, then DejaVu, then whatever Japanese font this machine has."""
    global _fonts_added
    if not _fonts_added:
        for path in sorted(FONT_DIR.glob("*.ttf")):
            font_manager.fontManager.addfont(str(path))
        _fonts_added = True
    have = {f.name for f in font_manager.fontManager.ttflist}

    def keep(names: list[str]) -> list[str]:
        return [n for n in names if n in have]

    return {
        "sans": ["DM Sans", "DejaVu Sans", *keep(CJK_SANS)],
        "serif": ["Instrument Serif", "DejaVu Serif", *keep(CJK_SERIF + CJK_SANS)],
        "mono": ["IBM Plex Mono", "DejaVu Sans Mono", *keep(CJK_SANS)],
    }


class _Doc:
    """Cursor-based page builder. `y` is inches from the top edge; `x`/`w` are the current column."""

    def __init__(self, pdf: PdfPages, report: dict, stacks: dict[str, list[str]]):
        self.pdf, self.report, self.stacks = pdf, report, stacks
        self.x, self.w = MARGIN, W - 2 * MARGIN
        self.page = 0
        self.panels: list[dict] = []
        self._widths: dict[tuple, float] = {}
        self._new_page()

    # ---------------------------------------------------------------- pages
    def _new_page(self) -> None:
        self.fig = Figure(figsize=(W, H), facecolor=PAPER)
        self.renderer = FigureCanvasAgg(self.fig).get_renderer()
        self.page += 1
        self.y = TOP
        self.fox(MARGIN, 0.38, 0.3)
        self.text(MARGIN + 0.42, 0.4, "Kizuna Signal", 17, kind="serif")
        self.text(W - MARGIN, 0.47, f"{self.page:02d}", 8, MUTED, "mono", ha="right")
        self.line(MARGIN, W - MARGIN, 0.84)
        self.line(MARGIN, W - MARGIN, H - 0.62)
        a = self.report["analysis"]
        self.text(MARGIN, H - 0.5, f"ANALYSIS {a['id']}", 6.5, MUTED, "mono")
        self.text(
            W - MARGIN,
            H - 0.5,
            f"GENERATED {self.report['generated_at'][:10]}",
            6.5,
            MUTED,
            "mono",
            ha="right",
        )

    def break_page(self) -> None:
        for p in self.panels:
            self._backdrop(p, self.y + p["pad"] * 0.5)
        self.pdf.savefig(self.fig)
        self._new_page()
        for p in self.panels:
            p["y0"] = self.y
            self.y += p["pad"]

    def need(self, height: float) -> None:
        if self.y + height > H - BOTTOM:
            self.break_page()

    def finish(self) -> None:
        self.pdf.savefig(self.fig)

    # ---------------------------------------------------------------- drawing
    def text(self, x, y, s, size=9.5, color=INK, kind="sans", bold=False, ha="left") -> None:
        """`y` is the top of the line; the baseline sits just under it."""
        self.fig.text(
            x,
            H - (y + size * 0.78 / 72),
            s,
            fontsize=size,
            color=color,
            family=self.stacks[kind],
            weight="bold" if bold else "normal",
            ha=ha,
            va="baseline",
            transform=self.fig.dpi_scale_trans,
        )

    def line(self, x0, x1, y=None, color=RULE) -> None:
        y = self.y if y is None else y
        self.fig.add_artist(
            Line2D(
                [x0, x1], [H - y, H - y], color=color, lw=0.6, transform=self.fig.dpi_scale_trans
            )
        )

    def vline(self, x, y0, y1, color=RULE) -> None:
        self.fig.add_artist(
            Line2D(
                [x, x], [H - y0, H - y1], color=color, lw=0.6, transform=self.fig.dpi_scale_trans
            )
        )

    def box(self, x, y0, w, h, fc=CARD, ec=RULE, z=0, radius=0.1) -> None:
        self.fig.add_artist(
            FancyBboxPatch(
                (x, H - (y0 + h)),
                w,
                h,
                boxstyle=f"round,pad=0,rounding_size={radius}",
                fc=fc,
                ec=ec,
                lw=0.6,
                zorder=z,
                transform=self.fig.dpi_scale_trans,
            )
        )

    def bar(self, x, y, w, h, color, z=0) -> None:
        """A flat progress bar, as the page's component and region tracks."""
        self.fig.add_artist(
            FancyBboxPatch(
                (x, H - (y + h)),
                w,
                h,
                boxstyle="square,pad=0",
                fc=color,
                ec="none",
                zorder=z,
                transform=self.fig.dpi_scale_trans,
            )
        )

    def dot(self, cx, cy, r, color) -> None:
        self.fig.add_artist(
            Circle(
                (cx, H - cy), r, fc=color, ec="none", transform=self.fig.dpi_scale_trans, zorder=3
            )
        )

    def fox(self, x, y, size) -> None:
        """The dashboard's fox mark (frontend/src/components/FoxMark.tsx), drawn from its 48-unit paths."""
        k = size / 48

        def poly(points, color):
            xy = [(x + px * k, H - (y + py * k)) for px, py in points]
            self.fig.add_artist(
                Polygon(
                    xy,
                    closed=True,
                    fc=color,
                    ec="none",
                    transform=self.fig.dpi_scale_trans,
                    zorder=3,
                )
            )

        poly([(4, 5), (17, 14), (31, 14), (44, 5), (42, 27), (24, 45), (6, 27)], "#f2761f")
        poly([(6, 27), (16, 25), (24, 31), (32, 25), (42, 27), (24, 45)], "#fff1e0")
        poly([(13, 20), (20, 22.5), (13, 25)], "#2a140a")
        poly([(35, 20), (28, 22.5), (35, 25)], "#2a140a")
        poly([(21.5, 41), (26.5, 41), (24, 44.5)], "#2a140a")

    def badge_width(self, s: str) -> float:
        return 0.17 + self.width(s.upper(), 7.5, "mono")

    def badge(self, x, y, status, label=None) -> float:
        """The dashboard's badge: a status-coloured dot and an uppercase mono label."""
        s = (label or status.replace("_", " ")).upper()
        self.dot(x + 0.045, y + 0.065, 0.032, BADGE.get(status, GREY))
        self.text(x + 0.17, y, s, 7.5, INK, "mono")
        return self.badge_width(s)

    # ---------------------------------------------------------------- text measure and flow
    def width(self, s: str, size: float, kind: str = "sans", bold: bool = False) -> float:
        key = (s, size, kind, bold)
        if key not in self._widths:
            prop = FontProperties(
                family=self.stacks[kind], size=size, weight="bold" if bold else "normal"
            )
            px, _, _ = self.renderer.get_text_width_height_descent(s, prop, False)
            self._widths[key] = px / self.fig.dpi
        return self._widths[key]

    def wrap(
        self, text: str, size: float, width: float, kind: str = "sans", bold: bool = False
    ) -> list[str]:
        lines: list[str] = []
        for para in str(text).split("\n"):
            current = ""
            for token in TOKEN.findall(para) or [""]:
                if current and self.width(current + token, size, kind, bold) > width:
                    lines.append(current)
                    current = token.lstrip()
                else:
                    current += token
                while self.width(current, size, kind, bold) > width and len(current) > 1:
                    cut = len(current) - 1  # one word wider than the column: break it by letters
                    while cut > 1 and self.width(current[:cut], size, kind, bold) > width:
                        cut -= 1
                    lines.append(current[:cut])
                    current = current[cut:]
            lines.append(current)
        return lines

    @staticmethod
    def leading(size: float, ratio: float = 1.5) -> float:
        return size * ratio / 72

    def para(self, s, size=9.5, color=INK, gap=0.0, ha="left") -> None:
        x = self.x + self.w / 2 if ha == "center" else self.x
        for ln in self.wrap(s, size, self.w):
            self.need(self.leading(size))
            self.text(x, self.y, ln, size, color, ha=ha)
            self.y += self.leading(size)
        self.y += gap

    def heading(
        self, title: str, note: str | None = None, center: bool = False, top: float = 0.42
    ) -> None:
        """A section title in Instrument Serif with its muted note, as the page's SectionHeading."""
        self.y += top
        self.need(1.4)
        x = self.x + self.w / 2 if center else self.x
        self.text(x, self.y, title, 27, kind="serif", ha="center" if center else "left")
        self.y += 0.52
        if note:
            self.para(note, 9.5, MUTED, ha="center" if center else "left")
        self.y += 0.14

    # ---------------------------------------------------------------- panels
    def begin_panel(self, fc=CARD, ec=RULE, pad=0.22) -> None:
        self.need(pad * 2 + 0.6)
        self.panels.append(dict(fc=fc, ec=ec, pad=pad, y0=self.y, ox=self.x, ow=self.w))
        self.y += pad
        self.x += pad
        self.w -= 2 * pad

    def end_panel(self) -> None:
        p = self.panels.pop()
        self.y += p["pad"]
        self.x, self.w = p["ox"], p["ow"]
        self._backdrop(p, self.y)

    def _backdrop(self, p: dict, y1: float) -> None:
        self.box(p["ox"], p["y0"], p["ow"], y1 - p["y0"], p["fc"], p["ec"])

    # ---------------------------------------------------------------- sections
    def build(self) -> None:
        r, t = self.report["result"], self.report["title"]
        self.hero(r)
        self.title_details(t)
        self.score(r)
        self.evidence_notes(r["data_quality_warnings"])
        if r["score_origin"] == "trained_model":
            self.model_validation(r["model_evaluation"])
        self.components(r)
        if r["regional_scores"]:
            self.regions(r["regional_scores"])
        self.ledger(r)
        self.comparables(r["comparable_titles"])
        self.sources(r["source_status"])
        self.next_actions()
        self.finish()

    def hero(self, r: dict) -> None:
        self.text(self.x, self.y - 0.05, "Decision intelligence", 50, kind="serif")
        self.y += 0.95
        self.para(
            "A frozen, versioned result with evidence, regional opportunity and launch guidance.",
            11,
            MUTED,
        )
        self.y += 0.1
        # the dashboard's signal rail: dot, state, rule, versions
        self.dot(self.x + 0.05, self.y + 0.07, 0.04, GREEN)
        self.text(self.x + 0.17, self.y, "SAVED ANALYSIS", 8, MUTED, "mono")
        rail_x = self.x + 0.17 + self.width("SAVED ANALYSIS", 8, "mono") + 0.15
        self.line(rail_x, rail_x + 0.35, self.y + 0.07)
        versions = f"{r['model_version']} / {r['scoring_version']}".upper()
        self.text(rail_x + 0.5, self.y, versions, 8, MUTED, "mono")
        self.y += 0.3

    def title_details(self, t: dict) -> None:
        self.heading(
            "Title details",
            "The intake record saved by the backend for this analysis.",
            center=True,
        )
        rows = _title_rows(t)
        cols = 3
        cw, pad = self.w / cols, 0.16
        self.begin_panel(fc=PANEL, pad=0)
        for i in range(0, len(rows), cols):
            cells = rows[i : i + cols]
            lines = [self.wrap(value, 14, cw - 2 * pad, "serif") for _, value in cells]
            height = pad + 0.22 + max(len(ln) for ln in lines) * self.leading(14, 1.2) + pad
            self.need(height)
            for j, ((name, _), ln) in enumerate(zip(cells, lines, strict=True)):
                cx = self.x + j * cw + cw / 2
                self.text(cx, self.y + pad, name.upper(), 7, MUTED, "mono", ha="center")
                for k, piece in enumerate(ln):
                    top = self.y + pad + 0.22 + k * self.leading(14, 1.2)
                    self.text(cx, top, piece, 14, kind="serif", ha="center")
                if j < len(cells) - 1:
                    self.vline(self.x + (j + 1) * cw, self.y, self.y + height)
            self.y += height
            if i + cols < len(rows):
                self.line(self.x, self.x + self.w)
        self.end_panel()

    def score(self, r: dict) -> None:
        """The score card: the number on the left, its badges and figures on the right, split by a rule."""
        self.y += 0.3
        half = self.w / 2
        meaning = self.wrap(r["score_meaning"], 9, half - 0.7)
        height = max(2.35, 1.62 + len(meaning) * self.leading(9) + 0.3)
        self.need(height)
        x, y = self.x, self.y
        self.box(x, y, self.w, height)
        self.vline(x + half, y, y + height)
        # left: label, big serif number, "/ 100"
        cx = x + half / 2
        self.text(cx, y + 0.32, "MARKET POTENTIAL", 8, MUTED, "mono", ha="center")
        big = str(_round(r["market_potential_score"]))
        bw, sw = self.width(big, 108, "serif"), self.width("/ 100", 15)
        start = cx - (bw + 0.12 + sw) / 2
        self.text(start, y + 0.55, big, 108, kind="serif")
        self.text(start + bw + 0.12, y + 0.55 + (108 - 15) * 0.78 / 72, "/ 100", 15, MUTED)
        # right: badges, the two figures, what the score means
        cx = x + half + half / 2
        badges = [_label(s) for s in (r["decision_classification"], r["score_origin"])]
        total = sum(self.badge_width(lbl) for lbl in badges) + 0.2
        bx = cx - total / 2
        for status, lbl in zip(
            (r["decision_classification"], r["score_origin"]), badges, strict=True
        ):
            bx += self.badge(bx, y + 0.32, status, lbl) + 0.2
        low, high = r["confidence_interval"]
        figures = [
            ("EVIDENCE CONFIDENCE", f"{_round(r['confidence_score'])}%"),
            ("EXPECTED RANGE", f"{_round(low)} to {_round(high)}"),
        ]
        for k, (name, value) in enumerate(figures):
            fx = cx + (k - 0.5) * half / 2
            self.text(fx, y + 0.8, name, 7, MUTED, "mono", ha="center")
            self.text(fx, y + 0.98, value, 30, kind="serif", ha="center")
        for i, ln in enumerate(meaning):
            self.text(cx, y + 1.62 + i * self.leading(9), ln, 9, MUTED, ha="center")
        self.y += height

    def evidence_notes(self, notes: list[str]) -> None:
        """The notes band: a serif title with the brand dot on the left, the notes ruled apart on the right."""
        if not notes:
            return
        self.y += 0.3
        self.begin_panel()
        panel = self.panels[-1]
        inner_x, inner_right = self.x, panel["ox"] + panel["ow"] - panel["pad"]
        self.dot(self.x + 0.05, self.y + 0.17, 0.045, BRAND)
        self.text(self.x + 0.2, self.y, "Evidence notes", 21, kind="serif")
        self.x = inner_x + 2.15
        self.w = inner_right - self.x
        for i, note in enumerate(notes):
            if i:
                self.line(self.x, self.x + self.w, self.y + 0.03)
                self.y += 0.1
            self.para(note, 9, MUTED, gap=0.04)
        self.x, self.w = inner_x, inner_right - inner_x
        self.end_panel()

    def model_validation(self, m: dict) -> None:
        self.y += 0.3
        self.begin_panel()
        self.heading(
            "Model validation",
            "Historical holdout results describe ranking performance on past titles. "
            "They are not a guarantee for a new release.",
            top=0.0,
        )

        def num(key, fmt):
            v = m.get(key)
            return fmt(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else "—"

        stats = [
            (str(m.get("labelled_titles", "—")), "Labelled titles used"),
            (str(m.get("oof_titles", "—")), "Out-of-fold titles"),
            (num("spearman", lambda v: f"{v:.2f}"), "Mean Spearman ranking"),
            (num("top3_hit", lambda v: f"{_round(v * 100)}%"), "Top-three hit rate"),
        ]
        self.need(1.0)
        gap = 0.1
        tile_w = (self.w - 3 * gap) / 4
        for i, (value, name) in enumerate(stats):
            tx = self.x + i * (tile_w + gap)
            self.box(tx, self.y, tile_w, 0.9, WHITE, RULE, 1, 0.06)
            self.text(tx + 0.14, self.y + 0.1, value, 26, kind="serif")
            self.text(tx + 0.14, self.y + 0.62, name, 7.5, MUTED)
        self.y += 1.02
        scheme = m.get("scheme")
        self.para(
            f"Validation: {scheme or 'not reported'}. "
            "India-specific commercial outcomes are not part of this training target.",
            8.5,
            MUTED,
        )
        self.end_panel()

    def components(self, r: dict) -> None:
        trained = r["score_origin"] == "trained_model"
        self.heading(
            "What shaped the score",
            "Only measured components that passed held-out validation contribute to this score. "
            "Unavailable and unvalidated components are excluded."
            if trained
            else "The fallback components combine into this market-potential result.",
        )
        self.line(self.x, self.x + self.w)
        track = self.x + 2.4
        track_w = self.w - 2.4 - 0.6
        for key, value in sorted(r["component_scores"].items(), key=lambda kv: -kv[1]):
            self.need(0.55)
            self.text(self.x, self.y + 0.17, _label(key), 10.5)
            self.bar(track, self.y + 0.24, track_w, 0.065, TRACK)
            self.bar(
                track, self.y + 0.24, max(track_w * min(value, 100) / 100, 0.02), 0.065, INK, 1
            )
            self.text(
                self.x + self.w, self.y + 0.11, str(_round(value)), 20, kind="serif", ha="right"
            )
            self.y += 0.55
            self.line(self.x, self.x + self.w)
        details = r["component_details"]
        if details:
            self.y += 0.18
        gap = 0.12
        card_w = (self.w - gap) / 2
        for i in range(0, len(details), 2):
            cells = []
            for item in details[i : i + 2]:
                reason = item.get("reason")
                if not isinstance(reason, str):
                    weight = f"{float(item.get('weight', 0)) * 100:g}"
                    rho = item.get("validation_spearman")
                    shown = "not reported" if rho is None else rho
                    reason = f"{weight}% configured weight; {shown} held-out Spearman."
                cells.append((item, self.wrap(reason, 8.5, card_w - 0.3)))
            height = 0.5 + max(len(body) for _, body in cells) * self.leading(8.5) + 0.12
            self.need(height)
            for j, (item, body) in enumerate(cells):
                cx = self.x + j * (card_w + gap)
                self.box(cx, self.y, card_w, height, WHITE, RULE, 1, 0.06)
                self.text(cx + 0.15, self.y + 0.14, _label(str(item["key"])), 10, bold=True)
                status = str(item["status"]).replace("_", " ").upper()
                self.text(cx + card_w - 0.15, self.y + 0.16, status, 6.5, MUTED, "mono", ha="right")
                for k, ln in enumerate(body):
                    self.text(cx + 0.15, self.y + 0.42 + k * self.leading(8.5), ln, 8.5, MUTED)
            self.y += height + gap

    # -- regional opportunity ------------------------------------------------
    def regions(self, regions: list[dict]) -> None:
        ranked = sorted(regions, key=lambda region: -region["score"])
        self.need(5.9)  # the heading stays with its map
        self.heading(
            "Regional opportunity", "The strongest current state-language-platform combinations."
        )
        self.line(self.x, self.x + self.w)
        self.y += 0.22
        data = json.loads(MAP_FILE.read_text(encoding="utf-8"))
        low, high = ranked[-1]["score"], ranked[0]["score"]

        def heat(score: float) -> float:
            return 1.0 if high == low else (score - low) / (high - low)

        by_shape = {MAP_ALIASES.get(r["state"], r["state"]): r for r in ranked}
        for state, shape in MAP_SHARED_SHAPES.items():
            if state in by_shape and shape not in by_shape:
                by_shape[shape] = by_shape[state]
        top = ranked[0]
        top_shapes = {MAP_ALIASES.get(top["state"], top["state"])} | {
            shape for state, shape in MAP_SHARED_SHAPES.items() if state == top["state"]
        }

        map_w = 3.5
        map_h = map_w * data["height"] / data["width"]
        ax = self.fig.add_axes([self.x / W, (H - self.y - map_h) / H, map_w / W, map_h / H])
        ax.set_xlim(0, data["width"])
        ax.set_ylim(data["height"], 0)
        ax.axis("off")
        ax.patch.set_alpha(0)
        for state in sorted(data["states"], key=lambda s: s["name"] in top_shapes):
            region = by_shape.get(state["name"])
            selected = state["name"] in top_shapes
            for ring in state["rings"]:
                ax.add_patch(
                    Polygon(
                        ring,
                        closed=True,
                        fc=_mix(heat(region["score"])) if region else SOFT,
                        ec=INK if selected else PAPER,
                        lw=0.9 if selected else 0.35,
                    )
                )
        legend_y = self.y + map_h + 0.1
        self.text(self.x, legend_y, f"LOWER · {_round(low)}", 7.5, MUTED, "mono")
        legend = self.fig.add_axes(
            [(self.x + 1.15) / W, (H - legend_y - 0.12) / H, 1.0 / W, 0.09 / H]
        )
        legend.imshow(
            np.linspace(0, 1, 64)[None, :],
            cmap=LinearSegmentedColormap.from_list("h", [HEAT_LO, HEAT_HI]),
            aspect="auto",
        )
        legend.axis("off")
        self.text(self.x + 2.3, legend_y, f"{_round(high)} · HIGHER", 7.5, MUTED, "mono")
        self.text(
            self.x,
            legend_y + 0.22,
            "Colour is relative to the regions scored in this analysis.",
            8,
            MUTED,
        )

        # the strongest region's detail, as the page shows it first
        dx = self.x + map_w + 0.4
        dw = self.w - map_w - 0.4
        y = self.y
        self.text(dx, y, f"RANK 01 / {len(ranked):02d}", 8, MUTED, "mono")
        y += 0.3
        for ln in self.wrap(top["state"], 30, dw, "serif"):
            self.text(dx, y, ln, 30, kind="serif")
            y += 0.5
        score = str(_round(top["score"]))
        self.text(dx, y, score, 54, kind="serif")
        confidence = f"/100 · Confidence {_round(top['confidence'])}%"
        self.text(dx + self.width(score, 54, "serif") + 0.1, y + 0.45, confidence, 9.5, MUTED)
        y += 0.95
        self.text(dx, y, f"{top['recommended_language']} · {top['preferred_platform']}", 9.5, MUTED)
        y += 0.32
        for reason in top["reasons"]:
            self.text(dx, y, "•", 9, MUTED)
            for ln in self.wrap(reason, 9, dw - 0.2):
                self.text(dx + 0.2, y, ln, 9, MUTED)
                y += self.leading(9, 1.55)
            y += 0.04
        self.y = max(y, self.y + map_h + 0.5) + 0.2

        self.line(self.x, self.x + self.w)
        bar_x, bar_w = self.x + 5.0, self.w - 5.0 - 0.55
        for rank, region in enumerate(ranked, start=1):
            self.need(0.36)
            self.text(self.x + 0.05, self.y + 0.11, f"{rank:02d}", 8, MUTED, "mono")
            name_size = min(10, 10 * 2.9 / self.width(region["state"], 10))
            self.text(self.x + 0.5, self.y + 0.1, region["state"], name_size)
            detail = f"{region['recommended_language']} · {region['preferred_platform']} · {_round(region['confidence'])}%"
            self.text(self.x + 3.5, self.y + 0.12, detail, 8, MUTED)
            self.bar(bar_x, self.y + 0.15, bar_w, 0.05, TRACK)
            self.bar(
                bar_x,
                self.y + 0.15,
                max(bar_w * region["score"] / 100, 0.02),
                0.05,
                _mix(heat(region["score"])),
                1,
            )
            self.text(
                self.x + self.w - 0.05,
                self.y + 0.06,
                str(_round(region["score"])),
                14,
                kind="serif",
                ha="right",
            )
            self.y += 0.36
            self.line(self.x, self.x + self.w)

    # -- evidence ledger -----------------------------------------------------
    def ledger(self, r: dict) -> None:
        self.heading(
            "Evidence ledger",
            "Positive and negative contributions are shown with their backend explanation.",
        )
        pos, neg = r["positive_drivers"], r["negative_drivers"]
        gap = 0.45
        col_w = (self.w - gap) / 2
        self.need(1.2)
        for k, title in enumerate(("SIGNALS SUPPORTING INVESTMENT", "SIGNALS REQUIRING CAUTION")):
            self.text(self.x + k * (col_w + gap), self.y, title, 8.5, bold=True)
        self.y += 0.32
        for i in range(max(len(pos), len(neg), 1)):
            columns = [
                (pos[i] if i < len(pos) else None, GREEN, "+"),
                (neg[i] if i < len(neg) else None, RED, "−"),
            ]
            blocks = [
                (d, color, sign, self.wrap(d["evidence"], 9, col_w - 0.8)) if d else None
                for d, color, sign in columns
            ]
            body_heights = [0.28 + len(b[3]) * self.leading(9) for b in blocks if b]
            height = 0.12 + max(body_heights or [0.3]) + 0.14
            self.need(height)
            for k, block in enumerate(blocks):
                cx = self.x + k * (col_w + gap)
                if block:
                    d, color, sign, body = block
                    self.line(cx, cx + col_w)
                    self.text(cx, self.y + 0.14, d["name"], 10.5, bold=True)
                    self.text(
                        cx + col_w,
                        self.y + 0.15,
                        f"{sign}{d['contribution']:.1f}",
                        11,
                        color,
                        "mono",
                        ha="right",
                    )
                    for j, ln in enumerate(body):
                        self.text(cx, self.y + 0.4 + j * self.leading(9), ln, 9, MUTED)
                elif k == 1 and i == 0:
                    self.line(cx, cx + col_w)
                    self.text(
                        cx,
                        self.y + 0.14,
                        "No material negative driver was emitted by this result.",
                        9,
                        MUTED,
                    )
            self.y += height

    # -- comparable evidence -------------------------------------------------
    def comparables(self, items: list[dict]) -> None:
        self.heading(
            "Comparable evidence",
            "Similarity is contextual evidence, not proof of identical commercial performance.",
        )
        self.line(self.x, self.x + self.w)
        for item in items:
            reasons = self.wrap(" · ".join(item["reasons"]), 9, self.w - 2.2)
            height = 0.52 + len(reasons) * self.leading(9)
            self.need(height)
            self.text(self.x, self.y + 0.16, item["title"], 17, kind="serif")
            similar = f"{_round(item['similarity'] * 100)}% SIMILAR"
            self.text(self.x + self.w - 1.0, self.y + 0.2, similar, 7.5, INK, "mono", ha="right")
            self.text(
                self.x + self.w,
                self.y + 0.2,
                f"{_round(item['market_signal'])} SIGNAL",
                7.5,
                INK,
                "mono",
                ha="right",
            )
            for j, ln in enumerate(reasons):
                self.text(self.x, self.y + 0.5 + j * self.leading(9), ln, 9, MUTED)
            self.y += height
            self.line(self.x, self.x + self.w)

    # -- source health -------------------------------------------------------
    def sources(self, sources: list[dict]) -> None:
        self.heading(
            "Source health",
            "Every source carries availability, freshness, quality, provenance and warnings.",
        )
        self.line(self.x, self.x + self.w)
        for s in sources:
            warn = self.wrap(" ".join(s["warnings"]) or "No source warning.", 9, self.w)
            height = 0.9 + len(warn) * self.leading(9)
            self.need(height)
            self.badge(self.x, self.y + 0.2, s["status"])
            self.text(self.x + 1.1, self.y + 0.17, _label(s["source"]), 12, bold=True)
            facts = [
                ("FRESHNESS", f"{_round(s['freshness_score'] * 100)}%"),
                ("QUALITY", f"{_round(s['quality_score'] * 100)}%"),
                ("MODE", s["provenance"].get("mode") or "unspecified"),
            ]
            for k, (name, value) in enumerate(facts):
                fx = self.x + (2.9 + k * 1.0 if k < 2 else 4.9)
                self.text(fx, self.y + 0.12, name, 7, MUTED, "mono")
                self.text(fx, self.y + 0.3, value, 9.5)
            for j, ln in enumerate(warn):
                self.text(self.x, self.y + 0.66 + j * self.leading(9), ln, 9, MUTED)
            self.y += height
            self.line(self.x, self.x + self.w)

    def next_actions(self) -> None:
        """The page's closing dark band."""
        self.y += 0.5
        self.need(1.2)
        self.box(self.x, self.y, self.w, 1.0, INK, INK, 0, 0.1)
        self.text(
            self.x + 0.3, self.y + 0.24, "Turn the result into a decision.", 22, DARK_TEXT, "serif"
        )
        self.text(
            self.x + 0.3,
            self.y + 0.66,
            "Compare controlled changes, then review the recommended launch sequence.",
            9.5,
            DARK_MUTED,
        )
        self.y += 1.0


def _render(report: dict, fonttype: int) -> bytes:
    buf = io.BytesIO()
    a = report["analysis"]
    meta = {
        "Title": f"Kizuna Signal analysis: {report['title']['english_title'] or report['title']['name']}",
        "Author": "Kizuna Signal",
        "Subject": f"Analysis {a['id']}",
    }
    stacks = _font_stacks()
    with matplotlib.rc_context({"pdf.fonttype": fonttype}):
        with warnings.catch_warnings():
            warnings.simplefilter(
                "ignore"
            )  # a title glyph with no installed font is skipped, not fatal
            with PdfPages(buf, metadata=meta) as pdf:
                _Doc(pdf, report, stacks).build()
    return buf.getvalue()


def to_pdf(report: dict) -> bytes:
    try:
        return _render(report, 42)  # real text, selectable and searchable
    except Exception:  # noqa: BLE001  some CJK fonts (CFF outlines) cannot be embedded as TrueType
        return _render(report, 3)
