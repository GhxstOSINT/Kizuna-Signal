# Data sources and evidence flow

`KIZUNA_DEMO_MODE=true` (default) keeps every source on the deterministic offline demo so tests and
the hackathon demo never touch the network. `KIZUNA_DEMO_MODE=false` switches the whole pipeline
to real evidence. **In live mode a source is either real or reported unavailable — it never falls
back to demo numbers.**

| Source | Live mode | Granularity | Notes |
|---|---|---|---|
| Google Trends (`pytrends`) | search interest vs a benchmark, momentum, stability; interest by state | India, **state** | unofficial; cached 6h; 15-min cool-down after a 429 |
| YouTube Data API v3 | views, like+comment rate, views/day for trailer videos | global (search biased to IN) | needs `KIZUNA_YOUTUBE_API_KEY`; unconfigured => unavailable |
| Wikimedia Pageviews | 90-day article page views (en + ja) | global | article match must be >= 0.85 similar or the source is unavailable |
| AniList GraphQL | the title's community strength + metadata; genre comparables | global | 30 req/min currently; cached 24h |
| Census 2011 (static table) | population, urban share, state language | **state** | `app/data/india_states_census2011.csv`; urban % entered by hand, re-verify |
| Survey CSVs (optional) | genre / content-type affinity by state | **state** | `data/survey/README.md`; absent => stated in warnings |

## Flow of one analysis
1. All five sources are collected in parallel (`SourceRegistry`).
2. Comparable titles come from AniList (genre pool ranked by genre/theme similarity, sequels
   collapsed, signal discounted 15% because the pool is the genre's top titles).
3. Five components are computed from measured metrics only (`scoring._components`); a component
   with no evidence is **unmeasured**: its weight is redistributed, the score is shrunk toward 50 by
   sqrt(measured weight share), and it is excluded from the drivers.
4. Confidence combines inputs, source coverage, measured-weight share, freshness, quality and
   comparable similarity, then is multiplied by 0.5-1.0 according to how much title-specific
   demand/engagement evidence exists. With none, the result is `insufficient_evidence`.
5. State scores (`services/regional.py`): demand (Trends by state, shrunk toward the median for
   small states) 35%, state size 20%, urbanisation 10%, localization targeting 15%, survey
   affinity 20% (absent signals are dropped and weights renormalised), blended 45/55 with the title's
   market score. Every state lists its evidence in `reasons`.

## What this is not
* **The scoring is not machine-learned.** The weights, shrinkage factors and scale ceilings are
  hand-set heuristics (documented in code and above) and are not fitted to outcomes. Training
  needs labelled outcomes (e.g. historical Indian performance of Japanese titles) that this repo
  does not have.
* **Trained models exist but are not used by the app.** `scripts/train_title_model.py` and
  `scripts/train_regional_model.py` write XGBoost models and reports to `data/training/`. The title
  model predicts *global* AniList popularity/score, not India demand. The regional model is fitted
  to a small table (996 rows, 62 titles) and is weak (R² about 0.09). Nothing under `app/` loads
  either model. Install their dependencies with `pip install -e ".[ml]"`.
* Scores measure public interest signals, not revenue or viewership. Google Trends, YouTube and
  Wikimedia are not India-only except Trends.
* Census figures are from 2011 and describe population, not behaviour.
