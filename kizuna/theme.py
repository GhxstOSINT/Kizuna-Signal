"""Shared CSS and small HTML helpers. All dynamic text is HTML-escaped."""
from html import escape as esc

import streamlit as st

INK = "#17191B"
MUTED = "#70747A"
LINE = "#DCDDDF"
PRIMARY = "#4658C9"
GOOD = "#18745F"
BAD = "#A43F38"
WARN = "#9B6D21"

DECISION_KIND = {
    "Strong opportunity": "good",
    "Promising opportunity": "info",
    "Test before investing": "warn",
    "Limited opportunity": "bad",
    "Insufficient evidence": "bad",
}

CSS = f"""
<style>
:root {{--kz-ink:{INK};--kz-muted:{MUTED};--kz-line:{LINE};--kz-paper:#f0f0ee;--kz-white:#fafaf9;--kz-accent:{PRIMARY};}}
html, body, [class*="stApp"] {{font-family:Arial,sans-serif;color:var(--kz-ink);}}
[data-testid="stAppViewContainer"] {{background:var(--kz-paper);}}
[data-testid="stHeader"] {{background:rgba(240,240,238,.82);}}
[data-testid="stSidebar"] {{background:#e9e9e7;border-right:1px solid var(--kz-line);}}
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {{color:#4f5358;}}
[data-testid="stSidebarNav"] {{padding-top:1.2rem;}}
[data-testid="stSidebarNav"] a {{border-radius:8px;margin:2px 8px;}}
[data-testid="stSidebarNav"] a[aria-current="page"] {{background:#dedfdf;color:var(--kz-ink);}}
[data-testid="stMain"] .block-container {{max-width:1440px;padding-top:3rem;padding-bottom:4rem;}}
h1,h2,h3 {{font-family:Georgia,'Times New Roman',serif !important;font-weight:400 !important;letter-spacing:-.035em !important;color:var(--kz-ink);}}
h1 {{font-size:clamp(2.4rem,4.4vw,4.4rem) !important;line-height:1.02 !important;}}
h2 {{font-size:2.15rem !important;line-height:1.08 !important;}}
h3 {{font-size:1.55rem !important;}}
p {{line-height:1.55;}}
[data-testid="stButton"] button {{border-radius:999px;border:1px solid var(--kz-ink);background:var(--kz-ink);color:#fff;min-height:2.75rem;padding:.45rem 1.25rem;font-weight:600;transition:transform .18s ease,background .18s ease;}}
[data-testid="stButton"] button:hover {{background:#34373a;border-color:#34373a;transform:translateY(-1px);}}
[data-testid="stButton"] button[kind="secondary"] {{background:transparent;color:var(--kz-ink);}}
[data-testid="stTextInput"] input,[data-testid="stSelectbox"] [role="combobox"], [data-testid="stMultiSelect"] [role="combobox"] {{border-radius:9px;background:var(--kz-white);}}
[data-testid="stMetric"] {{background:rgba(250,250,249,.8);border:1px solid var(--kz-line);border-radius:12px;padding:1rem 1.1rem;}}
[data-testid="stMetricLabel"] p {{font-family:Consolas,monospace;text-transform:uppercase;letter-spacing:.09em;font-size:.66rem;color:var(--kz-muted);}}
[data-testid="stMetricValue"] {{font-family:Georgia,'Times New Roman',serif;font-size:2rem;color:var(--kz-ink);}}
[data-testid="stExpander"] {{border:1px solid var(--kz-line);border-radius:12px;background:rgba(250,250,249,.6);}}
.kz-card {{border:1px solid var(--kz-line);border-radius:14px;padding:18px;background:rgba(250,250,249,.9);box-shadow:0 5px 20px rgba(21,24,27,.025);}}
.kz-card.tall {{min-height:410px;}}
.kz-poster {{height:90px;border-radius:9px;display:flex;align-items:center;justify-content:center;color:#fff;font-weight:600;font-size:1.45rem;letter-spacing:.04em;margin-bottom:16px;filter:saturate(.72);}}
.kz-title {{font-size:1.12rem;font-weight:700;color:{INK};margin:0 0 2px 0;}}
.kz-sub {{color:{MUTED};font-size:.82rem;}}
.kz-row {{display:flex;justify-content:space-between;gap:12px;font-size:.86rem;padding:5px 0;color:{INK};border-bottom:1px solid rgba(220,221,223,.58);}}
.kz-row:last-child {{border-bottom:0;}}
.kz-row span:first-child {{color:{MUTED};}}
.kz-badge {{display:inline-block;padding:3px 10px;border-radius:999px;font-size:.73rem;font-weight:600;}}
.kz-badge.good {{background:#e3f1ec;color:{GOOD};}}
.kz-badge.info {{background:#e9eaf5;color:{PRIMARY};}}
.kz-badge.warn {{background:#f5eee0;color:{WARN};}}
.kz-badge.bad {{background:#f5e8e6;color:{BAD};}}
.kz-badge.neutral {{background:#e9e9e7;color:{MUTED};}}
.kz-big {{font-family:Georgia,'Times New Roman',serif;font-size:3.2rem;font-weight:400;line-height:1;color:{INK};}}
.kz-big small {{font-family:Arial,sans-serif;font-size:.95rem;font-weight:400;color:{MUTED};}}
.kz-label {{font-family:Consolas,monospace;font-size:.68rem;letter-spacing:.12em;text-transform:uppercase;color:{MUTED};margin:10px 0 5px;}}
.kz-meter {{height:5px;border-radius:6px;background:#e4e4e1;overflow:hidden;margin:8px 0 12px;}}
.kz-meter > div {{height:100%;border-radius:6px;}}
.kz-hero {{position:relative;overflow:hidden;border:1px solid var(--kz-line);border-radius:16px;padding:22px 24px;background:var(--kz-white);}}
.kz-reco {{font-size:1.05rem;font-weight:600;color:{INK};margin-top:8px;}}
.kz-note {{border-left:3px solid {WARN};background:#f7f2e8;padding:9px 12px;border-radius:4px;font-size:.88rem;}}
.kz-note.bad {{border-color:{BAD};background:#f7ecea;}}
.kz-note.info {{border-color:{PRIMARY};background:#eef0f8;}}
.kz-stage {{padding:4px 0;font-size:.95rem;}}
.kz-eyebrow {{font:500 .68rem Consolas,monospace;letter-spacing:.14em;text-transform:uppercase;color:#75797c;}}
.kz-ticker {{display:flex;align-items:center;gap:12px;flex-wrap:wrap;background:#17191b;color:#f2f2ef;border-radius:9px;padding:11px 15px;font:400 .68rem Consolas,monospace;letter-spacing:.07em;text-transform:uppercase;}}
.kz-ticker .dot {{width:7px;height:7px;border-radius:50%;background:#7bd7b6;box-shadow:0 0 12px rgba(123,215,182,.75);}}
.kz-ticker .sep {{color:#71767a;}}
.kz-portfolio-hero {{position:relative;overflow:hidden;border:1px solid var(--kz-line);border-radius:16px;background:linear-gradient(180deg,#fafaf9 0%,#f5f5f3 100%);padding:30px 34px 28px;margin:20px 0 22px;}}
.kz-portfolio-hero:before {{content:'';position:absolute;left:-5%;right:-5%;top:57%;height:45px;transform:rotate(-2deg);background:linear-gradient(90deg,transparent 0%,rgba(241,131,126,.2) 16%,rgba(246,218,115,.36) 37%,rgba(105,190,234,.34) 59%,rgba(175,146,230,.2) 76%,transparent 100%);filter:blur(16px);pointer-events:none;}}
.kz-portfolio-hero:after {{content:'';position:absolute;left:-3%;right:-3%;top:60%;height:2px;transform:rotate(-2deg);background:linear-gradient(90deg,transparent 0%,rgba(236,132,122,.55) 20%,rgba(236,205,105,.8) 42%,rgba(94,169,225,.8) 61%,rgba(154,134,218,.5) 78%,transparent 100%);filter:blur(2px);pointer-events:none;}}
.kz-portfolio-hero h2 {{position:relative;z-index:1;max-width:900px;font-size:clamp(2.4rem,4vw,4rem)!important;line-height:1.02!important;margin:.6rem 0 .9rem;}}
.kz-portfolio-hero p {{position:relative;z-index:1;max-width:650px;color:#555a5f;font-size:1.04rem;}}
.kz-hero-stats {{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin:0 0 28px;}}
.kz-hero-stat {{padding:14px 16px;border:1px solid var(--kz-line);border-radius:12px;background:rgba(250,250,249,.78);}}
.kz-hero-stat strong {{display:block;font:400 2rem Georgia,'Times New Roman',serif;color:var(--kz-ink);}}
.kz-hero-stat span {{font:400 .63rem Consolas,monospace;letter-spacing:.1em;text-transform:uppercase;color:var(--kz-muted);}}
@media (max-width: 760px) {{.kz-hero-stats{{grid-template-columns:repeat(2,minmax(0,1fr));}}.kz-portfolio-hero{{padding:23px 20px;}}}}
</style>
"""


def inject_css():
    st.markdown(CSS, unsafe_allow_html=True)


def html(markup):
    st.markdown(markup, unsafe_allow_html=True)


def badge(text, kind="neutral"):
    return f'<span class="kz-badge {kind}">{esc(str(text))}</span>'


def decision_badge(label):
    return badge(label, DECISION_KIND.get(label, "neutral"))


def confidence_kind(conf):
    return "good" if conf >= 75 else "warn" if conf >= 55 else "bad"


def meter(value, color=PRIMARY):
    v = max(0, min(100, float(value)))
    return f'<div class="kz-meter"><div style="width:{v:.0f}%; background:{color};"></div></div>'


def row(label, value):
    return f'<div class="kz-row"><span>{esc(str(label))}</span><span>{esc(str(value))}</span></div>'


def note(text, kind="warn"):
    cls = "" if kind == "warn" else f" {kind}"
    return f'<div class="kz-note{cls}">{esc(str(text))}</div>'


def poster(title, accent):
    initials = "".join(w[0] for w in str(title).split()[:2]).upper() or "?"
    return (f'<div class="kz-poster" style="background:linear-gradient(135deg,{esc(accent)},#1B1F3B);">'
            f'{esc(initials)}</div>')
