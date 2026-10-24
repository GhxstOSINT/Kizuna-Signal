"""Train the market-performance model and write the Levenshtein report.

    PYTHONPATH=.packages py -3.12 scripts/train_model.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ml import model  # noqa: E402
from app.ml.corpus import load_existing_titles, load_labeled_corpus  # noqa: E402
from app.ml.levenshtein import (  # noqa: E402
    BUDGET_VOCABULARY,
    GENRE_VOCABULARY,
    PLATFORM_VOCABULARY,
    compare_records,
    vocabulary_confidence,
)

OUT = Path(__file__).resolve().parents[1] / "app" / "ml" / "artifacts"


def nearest(record: dict, peers: list[dict]) -> dict:
    return max(
        ({"against": p["title"], **compare_records(record, p)} for p in peers),
        key=lambda c: c["composite"],
    )


def levenshtein_report() -> dict:
    existing = load_existing_titles()
    released = load_labeled_corpus()
    titles = []
    for record in existing:
        titles.append(
            {
                "title": record["title"],
                "genre_confidence": round(
                    100 * vocabulary_confidence(record["genres"], GENRE_VOCABULARY), 1
                ),
                "platform_confidence": round(
                    100 * vocabulary_confidence([record["platform"]], PLATFORM_VOCABULARY), 1
                ),
                "budget_confidence": round(
                    100 * vocabulary_confidence([record["budget"]], BUDGET_VOCABULARY), 1
                ),
                "nearest_existing_title": nearest(
                    record, [p for p in existing if p["id"] != record["id"]]
                ),
                "nearest_released_title": nearest(record, released),
            }
        )
    return {
        "method": "normalized Levenshtein similarity, 0-100; absent fields excluded and weights renormalised",
        "titles": titles,
    }


def main() -> None:
    rows = load_labeled_corpus()
    artifact = model.train(rows)
    model.save(artifact)
    (OUT / "levenshtein_report.json").write_text(
        json.dumps(levenshtein_report(), indent=2), encoding="utf-8"
    )
    m = artifact["metrics"]
    print(
        f"rows={m['real_rows']} baseline_MAE={m['baseline_mean_mae']} LOO_MAE={m['loo_mae']} "
        f"LOO_R2={m['loo_r2']} improvement={m['mae_improvement_vs_baseline_pct']}%"
    )
    print("hyperparameters:", artifact["hyperparameters"], "synthetic_helped:", m["synthetic_helped"])
    print("best without synthetic:", m["best_without_synthetic"])
    print("80% interval half-width:", artifact["conformal"]["q80"])


if __name__ == "__main__":
    main()
