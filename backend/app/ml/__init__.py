"""Machine-learning layer: the state model, the India success score, and their building blocks.

Map (all modules are flat here on purpose, see the pickle warning below):

State model, the real runtime path (served by /predict, /model, /predict/report)
    state_model.py      StateModel: fit, predict, save/load models/state/<version>/
    state_features.py   lift label, history features, state context (data/tables/data_dictionary.csv)
    csv_data.py         loads the training tables in data/tables/
    synthetic.py        weighted fill for sparse title x state cells
    success.py          India success score (0-100) and its validated components
    scoring_config.py   versioned weights and thresholds

Building blocks shared by the above
    features.py         content encoder and (title, state) feature rows
    embeddings.py       synopsis embeddings (sentence-transformers or TF-IDF + SVD)
    models.py           Ridge, XGBoost, ensemble and state-mean baseline
    intervals.py        split-conformal prediction intervals
    evaluate.py, split.py, explain.py, comparables.py, confidence.py
    states.py, schema.py

Initial AniList + Trends pipeline (used by backend/scripts and tests only, not by the API)
    dataset.py, titles.py, demand.py, train.py

Do not move or rename state_model.py, features.py, models.py, embeddings.py or intervals.py, nor
the classes in them. `joblib.dump(StateModel)` stores their import paths (app.ml.<module>), so a
rename makes every saved models/state/*/model.joblib, including ones trained elsewhere, unloadable.
"""
