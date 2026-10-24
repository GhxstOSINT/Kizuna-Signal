"""Shared CSS and small HTML helpers. All dynamic text is HTML-escaped."""
from html import escape as esc

import streamlit as st

INK = "#1B1F3B"
MUTED = "#5F6485"
LINE = "#E3E6F0"
PRIMARY = "#3B3F9E"
GOOD = "#1B7F6B"
BAD = "#B3382C"
WARN = "#B7791F"

DECISION_KIND = {
    "Strong opportunity": "good",
    "Promising opportunity": "info",
    "Test before investing": "warn",
    "Limited opportunity": "bad",
    "Insufficient evidence": "bad",
}

CSS = f"""
<style>
.kz-card {{border:1px solid {LINE}; border-radius:12px; padding:16px; background:#fff; height:100%;}}
.kz-poster {{height:84px; border-radius:8px; display:flex; align-items:center; justify-content:center;
  color:#fff; font-weight:700; font-size:1.5rem; letter-spacing:.04em; margin-bottom:12px;}}
.kz-title {{font-size:1.15rem; font-weight:700; color:{INK}; margin:0 0 2px 0;}}
.kz-sub {{color:{MUTED}; font-size:.82rem;}}
.kz-row {{display:flex; justify-content:space-between; font-size:.88rem; padding:3px 0; color:{INK};}}
.kz-row span:first-child {{color:{MUTED};}}
.kz-badge {{display:inline-block; padding:2px 10px; border-radius:999px; font-size:.78rem; font-weight:600;}}
.kz-badge.good {{background:#E3F4EF; color:{GOOD};}}
.kz-badge.info {{background:#E6E8FA; color:{PRIMARY};}}
.kz-badge.warn {{background:#FBF1DD; color:{WARN};}}
.kz-badge.bad {{background:#FBE7E4; color:{BAD};}}
.kz-badge.neutral {{background:#EEF0F6; color:{MUTED};}}
.kz-big {{font-size:2.6rem; font-weight:800; line-height:1; color:{INK};}}
.kz-big small {{font-size:1rem; font-weight:500; color:{MUTED};}}
.kz-label {{font-size:.75rem; letter-spacing:.06em; text-transform:uppercase; color:{MUTED}; margin-bottom:4px;}}
.kz-meter {{height:8px; border-radius:6px; background:#EEF0F6; overflow:hidden; margin:4px 0 8px 0;}}
.kz-meter > div {{height:100%; border-radius:6px;}}
.kz-hero {{border:1px solid {LINE}; border-radius:14px; padding:20px 24px; background:#F8F9FD;}}
.kz-reco {{font-size:1.05rem; font-weight:600; color:{INK}; margin-top:8px;}}
.kz-note {{border-left:4px solid {WARN}; background:#FFFBF2; padding:8px 12px; border-radius:4px; font-size:.88rem;}}
.kz-note.bad {{border-color:{BAD}; background:#FDF3F1;}}
.kz-note.info {{border-color:{PRIMARY}; background:#F3F4FC;}}
.kz-stage {{padding:4px 0; font-size:.95rem;}}
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
