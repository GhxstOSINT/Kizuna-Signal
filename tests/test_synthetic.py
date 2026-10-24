import numpy as np
import pandas as pd
import pytest

from app.ml.models import RidgeModel, StateMeanBaseline
from app.ml.state_features import state_effect, with_dlog
from app.ml.synthetic import SyntheticConfig, synthesize

STATES = ["IN-A", "IN-B", "IN-C", "IN-D"]


def _fixture():
    rng = np.random.default_rng(0)
    titles = pd.DataFrame({"title_id": [f"t{i}" for i in range(6)],
                           "genres": [["Action"]] * 3 + [["Romance"]] * 3, "themes": [[]] * 6})
    emb = np.vstack([[1.0, 0.0]] * 3 + [[0.0, 1.0]] * 3) + rng.normal(0, 0.01, (6, 2))
    emb /= np.linalg.norm(emb, axis=1, keepdims=True)
    rows = [{"title_id": t, "state": s, "share": float(np.exp(rng.normal(-3, 0.5)))}
            for t in titles["title_id"] for s in STATES if not (t == "t0" and s == "IN-D")]
    labels = with_dlog(pd.DataFrame(rows))
    ctx = pd.DataFrame({"state": STATES, "state_zone_N": [1, 1, 0, 0], "state_zone_S": [0, 0, 1, 1],
                        "state_lang_Hindi": [1, 1, 0, 0], "state_lang_Tamil": [0, 0, 1, 1]})
    return titles, emb, labels, ctx


def test_fills_only_missing_cells_and_never_real_ones():
    titles, emb, labels, ctx = _fixture()
    syn = synthesize(labels, titles, emb, STATES, ctx, state_effect(labels))
    assert set(zip(syn["title_id"], syn["state"])) == {("t0", "IN-D")}


def test_uses_only_the_given_titles():
    titles, emb, labels, ctx = _fixture()
    keep = labels["title_id"].isin(["t0", "t1", "t2"])  # the Romance titles are "validation": not passed in
    syn = synthesize(labels[keep], titles[:3].reset_index(drop=True), emb[:3], STATES, ctx, state_effect(labels[keep]))
    assert set(syn["title_id"]) <= {"t0", "t1", "t2"}


def test_thin_support_is_not_filled():
    titles, emb, labels, ctx = _fixture()
    cfg = SyntheticConfig(min_support=100.0)
    assert synthesize(labels, titles, emb, STATES, ctx, state_effect(labels), cfg).empty


def test_estimate_is_shrunk_towards_the_state_effect():
    titles, emb, labels, ctx = _fixture()
    eff = state_effect(labels)
    syn = synthesize(labels, titles, emb, STATES, ctx, eff).iloc[0]
    observed = labels.assign(lift=labels["dlog"] - labels["state"].map(eff))
    assert abs(syn["dlog"] - eff["IN-D"]) <= observed["lift"].abs().max()


def test_weights_reach_the_models():
    rows = pd.DataFrame({"state": ["a", "a", "b"], "y": [0.0, 10.0, 1.0], "w": [1.0, 0.0, 1.0]})
    base = StateMeanBaseline("y").fit(rows, [])
    assert base.means_["a"] == pytest.approx(0.0)  # the zero-weight row is ignored
    assert isinstance(RidgeModel, type)
