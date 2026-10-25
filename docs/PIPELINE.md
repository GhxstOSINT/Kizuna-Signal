# End-to-end pipeline

```
 INPUTS                      BUILD (scripts/build_all.py)                 SERVE (runtime)
 ------                      ---------------------------                  ---------------
 data/mock titles (3)  --+   1 train_model.py                              POST title -> analysis job
 comparables (24) +      |     labelled corpus (27, Levenshtein de-dupe)     |
 catalog (8) ------------+-->  ridge LOO eval -> market_model.json         1 demo/live source adapters
                         |     Levenshtein report (title, description,       (trends, YouTube, wiki, AniList, region)
 Census 2011 weights     |     genre, platform, budget)                   2 comparables (genre/theme overlap)
 + genre/format          |   2 train_regional.py                          3 five factor scores (0-1)
   affinity assumptions -+-->  1.5M census-weighted synthetic rows          content 0.25 | demand 0.25 | regional 0.20
                               normalise -> ridge -> regional_model.json    | engagement 0.15 | comparable 0.15
                         |   3 score_synthetic.py                         4 weighted average -> market potential %
                         +-->  five factors per row -> weighted average    5 regional_demand model -> state scores
                               -> factor_summary.json, sample CSV         6 confidence (coverage, freshness, quality)
                             4 data/MANIFEST.json (all datasets/models)   7 scenario lab, playbook
                                                                          8 dashboard + GET /api/v1/model/card
```

## Methodologies
- **Levenshtein**: normalised edit distance for entity de-duplication (titles), per-field similarity
  and vocabulary-based genre/platform/budget confidence.
- **Synthetic data**: Bernoulli/normal marginals and census population sampling; targets are z-scored
  then rescaled. Top-4 states carry a x1.25 genre-affinity inflation (an assumption, not census data).
- **Models**: title-performance ridge (27 rows, leave-one-out, not used) and the regional-demand ridge
  (1.5M synthetic rows, 20% holdout, conformal 80% interval, drives state scores).
- **Market potential** = sum(weight x factor), each factor 0-1, reported as a percentage.

## Honest limits
Holdout R2 measures fit to the simulator. Real-title check is a 0.34 rank correlation on 27 titles.
Demand/engagement come from offline demo adapters until live sources are connected.

## Update: real-data paths
Live adapters (Wikimedia, AniList, Google Trends incl. state interest, YouTube) are the default.
Comparable signals are measured from AniList. Scenarios recompute from stored evidence. The
synthetic factor table (`score_synthetic.py`) still uses simulated demand/engagement columns.

## Update: state-level data
`state_signals` table holds dated state measurements. Trends state interest (multi-term, vernacular)
is recorded automatically; partner CSVs are imported via the API and tilt regional scores by up to
+/-8 points after per-capita normalisation.
