"""Export builders: PDFs (fpdf2), CSVs and the interactive map HTML. No Streamlit imports."""
import csv
import io
from datetime import datetime

from fpdf import FPDF

from . import charts

_TRANSLATE = str.maketrans({
    "–": "-", "—": "-", "‘": "'", "’": "'", "“": '"', "”": '"',
    "…": "...", "×": "x", "•": "-", " ": " ",
})


def sanitize(text):
    """Make text safe for the built-in Latin-1 PDF fonts; anything else becomes '?'."""
    text = str(text if text is not None else "").translate(_TRANSLATE)
    return text.encode("latin-1", "replace").decode("latin-1")


def make_context(data, scenarios, recommended, approval, audit):
    """Bundle everything an export needs. `data` comes from state.load()."""
    ctx = dict(data)
    ctx.update(scenarios=scenarios, recommended=recommended, approval=approval, audit=audit,
               generated=datetime.now().strftime("%Y-%m-%d %H:%M"))
    return ctx


# ------------------------------------------------------------------ PDF
class _Pdf(FPDF):
    def __init__(self, title):
        super().__init__(format="A4")
        self.doc_title = sanitize(title)
        self.set_auto_page_break(True, margin=15)
        self.set_margins(15, 15, 15)
        self.add_page()

    def footer(self):
        self.set_y(-12)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(110, 114, 140)
        self.cell(0, 6, f"Kizuna Signal - {self.doc_title} - page {self.page_no()}", align="C")

    def h1(self, text):
        self.set_font("Helvetica", "B", 18)
        self.set_text_color(27, 31, 59)
        self.multi_cell(0, 9, sanitize(text), new_x="LMARGIN", new_y="NEXT")

    def h2(self, text):
        self.ln(2)
        self.set_font("Helvetica", "B", 12)
        self.set_text_color(59, 63, 158)
        self.multi_cell(0, 7, sanitize(text), new_x="LMARGIN", new_y="NEXT")
        self.set_text_color(27, 31, 59)

    def p(self, text, size=10, style=""):
        self.set_font("Helvetica", style, size)
        self.set_text_color(27, 31, 59)
        self.multi_cell(0, 5, sanitize(text), new_x="LMARGIN", new_y="NEXT")

    def bullet(self, text, size=10):
        self.set_font("Helvetica", "", size)
        self.set_text_color(27, 31, 59)
        self.set_x(18)
        self.multi_cell(0, 5, sanitize("- " + str(text)), new_x="LMARGIN", new_y="NEXT")

    def kv(self, key, value):
        self.set_font("Helvetica", "B", 10)
        self.cell(48, 5, sanitize(key))
        self.set_font("Helvetica", "", 10)
        self.multi_cell(0, 5, sanitize(value), new_x="LMARGIN", new_y="NEXT")

    def table(self, header, rows, widths):
        self.set_font("Helvetica", "B", 9)
        self.set_fill_color(236, 238, 250)
        for h, w in zip(header, widths):
            self.cell(w, 6, sanitize(h), border=0, fill=True)
        self.ln()
        self.set_font("Helvetica", "", 9)
        for row in rows:
            for v, w in zip(row, widths):
                self.cell(w, 5.5, sanitize(v)[: int(w / 1.9)], border=0)
            self.ln()


def _status_line(ctx):
    a = ctx["approval"]
    if a and a["status"] == "accepted":
        return f"Launch decision ACCEPTED by {a['by']} on {a['time']}"
    return "DRAFT - not yet accepted as a launch decision"


def _versions(ctx):
    an = ctx["analysis"]
    return (f"Analysis {an['analysis_id']} | result v{an['result_version']} | model {an['model_version']} | "
            f"scoring config {an['scoring_config_version']} | feature snapshot {an['feature_snapshot_id']}")


def _headline(pdf, ctx):
    v, m = ctx["view"], ctx["title"]
    pdf.h1(m["title"])
    pdf.p(f"{m['format']} | {', '.join(m['genres'])} | release {m['release_period']}", 10)
    pdf.p(_status_line(ctx), 9, "I")
    pdf.h2("Decision")
    pdf.kv("Market potential", f"{v['overall']} / 100 ({v['label']})")
    pdf.kv("Confidence", f"{v['confidence']}% ({v['confidence_band']}); expected range "
                         f"{v['interval'][0]}-{v['interval'][1]}")
    pdf.kv("Recommendation", ctx["reco"]["headline"])
    if v["low_confidence"]:
        pdf.p("Confidence is low. More evidence is required before a high-investment launch decision.", 10, "B")


def executive_brief_pdf(ctx):
    pdf = _Pdf("Executive brief")
    _headline(pdf, ctx)
    pdf.h2("Top markets")
    top = ctx["regions"]["top"]
    if top:
        pdf.table(["#", "State", "Score", "Confidence", "Language", "Platform"],
                  [[r["rank"], r["state"], r["score"], f"{r['confidence']}%", r["recommended_language"],
                    r["preferred_platform"]] for r in top], [10, 45, 20, 28, 30, 45])
    else:
        pdf.p("No region has enough evidence to be ranked.")
    pdf.h2("Key drivers")
    drivers = [d for d in ctx["view"]["drivers"] if d["active"]]
    for d in sorted((d for d in drivers if d["points"] > 0), key=lambda d: -d["points"])[:3]:
        pdf.bullet(f"{d['points']:+.1f}  {d['label']}")
    for d in sorted((d for d in drivers if d["points"] < 0), key=lambda d: d["points"])[:2]:
        pdf.bullet(f"{d['points']:+.1f}  {d['label']}")
    reco = ctx["reco"]
    pdf.h2("Launch strategy")
    pdf.kv("Platform", reco["platform"])
    pdf.kv("Localization", "; ".join(reco["localization"]))
    pdf.kv("Launch window", reco["launch_window"])
    name, why = ctx["recommended"]
    if name:
        pdf.kv("Best scenario", why)
    pdf.h2("Main limitations")
    for w in [w["message"] for w in ctx["analysis"]["warnings"]][:3]:
        pdf.bullet(w, 9)
    pdf.ln(2)
    pdf.p(_versions(ctx), 7, "I")
    return bytes(pdf.output())


def full_report_pdf(ctx):
    pdf = _Pdf("Full analysis")
    m, v, cfg = ctx["title"], ctx["view"], ctx["cfg"]
    _headline(pdf, ctx)

    pdf.h2("Input assumptions")
    for k, val in [("Synopsis", m["synopsis"]), ("Source material", m["source_material"]),
                   ("Studio", m.get("studio") or "-"), ("Target platform", m["target_platform"]),
                   ("Target languages", ", ".join(m.get("target_languages") or []) or "-"),
                   ("Budget band", m.get("budget_band") or "-"), ("Input completeness", f"{m['completeness']}%")]:
        pdf.kv(k, val)

    pdf.h2("Score components")
    pdf.table(["Component", "Weight", "Score"],
              [[c["label"], f"{c['weight']}%", f"{v['components'][c['id']]:.0f}"]
               for c in cfg["components"] if c["primary"]], [90, 30, 30])
    pdf.h2("Confidence factors")
    pdf.table(["Factor", "Weight", "Value"],
              [[f["label"], f"{f['weight'] * 100:.0f}%", f"{v['factors'][f['id']]:.0f}"]
               for f in cfg["confidence_factors"]], [90, 30, 30])
    if ctx["view"]["disabled_sources"] or ctx["view"]["delta_score"] or ctx["view"]["delta_confidence"]:
        pdf.p(f"Analyst overrides were active (score {v['delta_score']:+d}, confidence "
              f"{v['delta_confidence']:+d} vs base). Disabled sources: "
              f"{', '.join(v['disabled_sources']) or 'none'}.", 9, "I")

    pdf.h2("Regional ranking")
    pdf.table(["#", "State", "Score", "Confidence", "Evidence", "Language"],
              [[r["rank"], r["state"], r["score"], f"{r['confidence']}%", r["evidence_flag"],
                r["recommended_language"]] for r in ctx["regions"]["ranked"][:12]], [10, 55, 20, 28, 28, 30])
    n = len(ctx["regions"]["suppressed"])
    if n:
        pdf.p(f"{n} regions have insufficient evidence and are not ranked.", 9, "I")

    pdf.h2("Comparable titles (included)")
    by_id = {c["id"]: c for c in ctx["comparables"]["comparables"]}
    for cid in v["included_comps"]:
        c = by_id[cid]
        pdf.bullet(f"{c['title']} ({c['year']}), similarity {c['similarity'] * 100:.0f}%: {c['reason']}", 9)

    pdf.h2("Prediction drivers")
    for d in sorted(v["drivers"], key=lambda d: -d["points"]):
        pdf.bullet(f"{d['points']:+.1f}  {d['label']}" + ("" if d["active"] else " (source disabled)"), 9)

    pdf.h2("Scenario comparison")
    pdf.table(["Scenario", "Score", "Confidence", "Cost", "Reach"],
              [[name, r["score"], f"{r['confidence']}%", r["cost_level"], r["reach_level"]]
               for name, r in ctx["scenarios"]], [70, 20, 28, 25, 25])
    name, why = ctx["recommended"]
    pdf.p(f"Recommended option: {why}", 9, "I")

    reco = ctx["reco"]
    pdf.h2("Launch recommendation")
    pdf.kv("Decision", reco["headline"])
    pdf.kv("Priority markets", ", ".join(reco["priority_markets"]))
    pdf.kv("Target audience", "; ".join(reco["target_audience"]))
    pdf.kv("Positioning", reco["positioning"])
    for item in reco["items"]:
        pdf.p(f"{item['topic']}: {item['decision']}", 10, "B")
        pdf.bullet(f"Expected benefit: {item['expected_benefit']}", 9)
        pdf.bullet(f"Evidence: {'; '.join(item['evidence'])}", 9)
        pdf.bullet(f"Confidence: {item['confidence']}%   Principal risk: {item['principal_risk']}", 9)

    pdf.h2("Data limitations")
    for w in ctx["analysis"]["warnings"]:
        pdf.bullet(w["message"], 9)
    for lim in ctx["analysis"]["limitations"]:
        pdf.bullet(lim, 9)

    pdf.h2("Sources, model and approvals")
    for s in ctx["sources"]:
        pdf.bullet(f"{s['name']}: {s['status']} ({s['mode']}), last collected {s['last_collected'] or '-'}", 9)
    pdf.p(_versions(ctx), 8, "I")
    pdf.p(f"Generated {ctx['generated']}. " + _status_line(ctx), 8, "I")
    if ctx["audit"]:
        pdf.h2("Audit trail")
        for e in ctx["audit"][-15:]:
            pdf.bullet(f"{e['time']} {e['user']}: {e['action']} ({e['previous']} -> {e['new']})", 8)
    return bytes(pdf.output())


# ------------------------------------------------------------ CSV / HTML
def _csv(header, rows):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(header)
    w.writerows(rows)
    return buf.getvalue().encode("utf-8")


def regional_csv(ctx):
    rows = []
    for r in ctx["regions"]["ranked"] + ctx["regions"]["suppressed"]:
        rows.append([r.get("rank", ""), r["state"], r["score"], r["confidence"], r["evidence_strength"],
                     r["evidence_flag"], "yes" if r["suppressed"] else "no", r["demand_momentum"],
                     r["recommended_language"], r["secondary_language"], r["preferred_platform"],
                     r["audience_segment"]])
    return _csv(["rank", "state", "score", "confidence_pct", "evidence_strength", "evidence_flag",
                 "not_ranked", "demand_momentum", "recommended_language", "secondary_language",
                 "preferred_platform", "audience_segment"], rows)


def scenario_csv(ctx):
    cfg = ctx["cfg"]
    rows = []
    for name, r in ctx["scenarios"]:
        settings = "; ".join(f"{cfg['levers'][k]['label']}={cfg['levers'][k]['options'][o]['label']}"
                             for k, o in r["levers"].items())
        rows.append([name, r["score"], r["confidence"], f"{r['interval'][0]}-{r['interval'][1]}",
                     r["delta_score"], r["delta_confidence"], r["cost_level"], r["reach_level"], settings])
    return _csv(["scenario", "score", "confidence_pct", "range", "delta_score", "delta_confidence",
                 "cost", "reach", "settings"], rows)


def map_html(ctx):
    fig = charts.choropleth(ctx["regions"])
    fig.update_layout(title=f"{ctx['title']['title']}: regional opportunity", height=700)
    return fig.to_html(include_plotlyjs=True, full_html=True).encode("utf-8")
