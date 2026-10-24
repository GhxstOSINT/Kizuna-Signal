"""Plotly figures. Colours follow kizuna.theme."""
import json
from functools import lru_cache

import plotly.graph_objects as go

from .config import GEO_KEY, GEO_PATH
from .theme import BAD, GOOD, INK, MUTED, PRIMARY, WARN

CHART_CONFIG = {"displayModeBar": False}
GREY = "#D5D7DF"


@lru_cache(maxsize=1)
def _geojson():
    with open(GEO_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def _layout(fig, height):
    fig.update_layout(height=height, margin=dict(l=0, r=10, t=10, b=0), paper_bgcolor="rgba(0,0,0,0)",
                      plot_bgcolor="rgba(0,0,0,0)", font=dict(color=INK, size=13), showlegend=False)
    return fig


def score_color(v):
    return GOOD if v >= 75 else PRIMARY if v >= 60 else WARN


def component_bars(view):
    comps = view["visible_components"]
    labels = [c["label"] + ("" if c["primary"] else " (optional)") for c in comps]
    vals = [view["components"][c["id"]] for c in comps]
    base = view["base"]
    fig = go.Figure(go.Bar(
        x=vals[::-1], y=labels[::-1], orientation="h",
        marker_color=[score_color(v) for v in vals[::-1]],
        text=[f"{v:.0f}" for v in vals[::-1]], textposition="outside", cliponaxis=False,
        hovertemplate="%{y}: %{x:.0f}<extra></extra>"))
    fig.update_xaxes(range=[0, 105], showgrid=False, showticklabels=False, zeroline=False)
    fig.update_yaxes(automargin=True)
    return _layout(fig, 60 + 46 * len(comps))


def language_bars(affinity):
    rows = sorted(affinity, key=lambda a: a["affinity"])
    fig = go.Figure(go.Bar(
        x=[r["affinity"] for r in rows], y=[r["language"] for r in rows], orientation="h",
        marker_color=[score_color(r["affinity"]) for r in rows],
        text=[f"{r['affinity']}  ({r['confidence']}% conf.)" for r in rows],
        textposition="outside", cliponaxis=False,
        hovertemplate="%{y}: affinity %{x}<extra></extra>"))
    fig.update_xaxes(range=[0, 140], showgrid=False, showticklabels=False, zeroline=False)
    return _layout(fig, 30 + 26 * len(rows))


def choropleth(ranking, selected=None):
    geo = _geojson()
    ranked, supp = ranking["ranked"], ranking["suppressed"]
    fig = go.Figure()
    if ranked:
        fig.add_trace(go.Choropleth(
            geojson=geo, featureidkey=GEO_KEY, locations=[r["state"] for r in ranked],
            z=[r["score"] for r in ranked], zmin=30, zmax=90,
            colorscale=[[0, "#E6E8FA"], [0.5, "#8D93D8"], [1, "#1F2A8A"]],
            marker=dict(line=dict(color="#FFFFFF", width=0.6)),
            colorbar=dict(title="Score", thickness=12, len=0.6),
            customdata=[[r["rank"], r["confidence"], r["demand_momentum"]] for r in ranked],
            hovertemplate="<b>%{location}</b><br>Score %{z}<br>Rank #%{customdata[0]}"
                          "<br>Confidence %{customdata[1]}%<br>Momentum %{customdata[2]}<extra></extra>"))
    if supp:
        fig.add_trace(go.Choropleth(
            geojson=geo, featureidkey=GEO_KEY, locations=[r["state"] for r in supp],
            z=[0] * len(supp), colorscale=[[0, GREY], [1, GREY]], showscale=False,
            marker=dict(line=dict(color="#FFFFFF", width=0.6)),
            hovertemplate="<b>%{location}</b><br>Insufficient evidence, not ranked<extra></extra>"))
    if selected:
        fig.add_trace(go.Choropleth(
            geojson=geo, featureidkey=GEO_KEY, locations=[selected], z=[0], showscale=False,
            colorscale=[[0, "rgba(0,0,0,0)"], [1, "rgba(0,0,0,0)"]],
            marker=dict(line=dict(color=INK, width=2.5)), hoverinfo="skip"))
    # Fixed mainland-India window: fitbounds would zoom out to include the far island territories.
    fig.update_geos(visible=False, lonaxis_range=[68, 98], lataxis_range=[7, 37.5], projection_type="mercator")
    fig.update_layout(height=600, margin=dict(l=0, r=0, t=0, b=0), paper_bgcolor="rgba(0,0,0,0)",
                      clickmode="event+select", dragmode=False)
    return fig


def driver_bars(drivers):
    rows = sorted(drivers, key=lambda d: d["points"])
    colors = []
    for d in rows:
        if not d["active"]:
            colors.append(GREY)
        else:
            colors.append(GOOD if d["points"] > 0 else BAD)
    fig = go.Figure(go.Bar(
        x=[d["points"] for d in rows], y=[d["label"] for d in rows], orientation="h",
        marker_color=colors, text=[f"{d['points']:+.1f}" for d in rows], textposition="outside",
        cliponaxis=False, hovertemplate="%{y}: %{x:+.1f}<extra></extra>"))
    fig.update_xaxes(zeroline=True, zerolinecolor=MUTED, showgrid=False, showticklabels=False,
                     range=[-12, 14])
    fig.update_yaxes(automargin=True)
    return _layout(fig, 70 + 38 * len(rows))


def scenario_bars(results, metric, title, fmt="{:.0f}"):
    names = [n for n, _ in results]
    vals = [r[metric] for _, r in results]
    fig = go.Figure(go.Bar(
        x=names, y=vals, marker_color=[MUTED] + [PRIMARY] * (len(names) - 1),
        text=[fmt.format(v) for v in vals], textposition="outside", cliponaxis=False,
        hovertemplate="%{x}: %{y:.0f}<extra></extra>"))
    fig.update_yaxes(range=[0, 110], showgrid=False, showticklabels=False)
    fig.update_layout(title=dict(text=title, font=dict(size=14)))
    _layout(fig, 280)
    fig.update_layout(margin=dict(l=0, r=0, t=40, b=0))
    return fig
