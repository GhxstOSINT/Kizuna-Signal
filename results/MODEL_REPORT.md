# Kizuna Signal: India model report

Model `state-lift-content-v2-20261024T181058`, trained 2026-10-24T18:10:58+00:00. 62 labelled titles, 35 states and UTs.

## Training data

* Real title x state rows: 996
* Synthetic rows: 1152 (used in final model: True)
* Synthetic weight: 30% of a real row (synthetic-v1)

### Effect of the synthetic rows (held-out, real rows only, identical folds)

| | real only | + synthetic |
|---|---|---|
| Spearman (state ranking) | 0.163 | 0.143 |
| Top-3 state hit rate | 0.259 | 0.267 |
| Lift RMSE, sparse states | 2.511 | 2.440 |
| Lift RMSE, dense states | 1.920 | 1.870 |

Synthetic rows are weighted averages of similar titles and of the title's own related states. They add no observations. Read the table as: error moves slightly, ranking skill does not demonstrably change (the Spearman 95% intervals overlap heavily).

## Held-out accuracy (final model)

* Spearman across states: 0.143 (95% 0.041 to 0.246) over 45 titles
* Top-3 state hit rate: 0.267 against 0.219 by chance
* 80% interval observed coverage: 80.2%

## India success score: component validation

A component counts toward the score only if its held-out Spearman is at least 0.1.

| Component | Weight | Held-out Spearman | Status |
|---|---|---|---|
| Content fit | 25% | 0.394 | counted |
| Demand momentum | 25% | n/a | unavailable for an unreleased title |
| Regional opportunity | 20% | 0.143 | counted |
| Engagement quality | 15% | n/a | unavailable for an unreleased title |
| Comparable performance | 15% | 0.159 | counted |

Weight actually counted: 60%. Scores are relative (50 = typical anime in the training set), not revenue or viewership.

Content-fit model: 300 titles, leave-one-franchise-out R2 0.174, Spearman 0.394. Target is global log popularity (post-release proxy; no India outcome exists in the data).

## Per-state coverage and held-out error

| State | Real titles | Synthetic rows | Sparse | Bias | RMSE |
|---|---|---|---|---|---|
| Lakshadweep | 10 | 48 | yes | -1.32 | 1.58 |
| Puducherry | 11 | 49 | yes | -1.02 | 1.53 |
| Dadra and Nagar Haveli and Daman and Diu | 12 | 49 | yes | -1.28 | 2.37 |
| Arunachal Pradesh | 14 | 48 | yes | -0.06 | 3.57 |
| Andaman and Nicobar Islands | 14 | 44 | yes | -0.46 | 1.26 |
| Goa | 15 | 43 | yes | +1.57 | 2.59 |
| Sikkim | 15 | 46 | yes | +1.35 | 2.86 |
| Tripura | 17 | 45 | yes | +1.17 | 2.67 |
| Mizoram | 18 | 42 | yes | -0.34 | 0.93 |
| Chandigarh | 18 | 44 | yes | +2.30 | 3.05 |
| Nagaland | 20 | 42 |  | -0.76 | 1.81 |
| Jammu and Kashmir | 21 | 39 |  | +0.69 | 2.08 |
| Himachal Pradesh | 22 | 40 |  | +4.00 | 4.39 |
| Bihar | 25 | 37 |  | +0.25 | 0.88 |
| Chhattisgarh | 25 | 37 |  | +1.68 | 1.93 |
| Manipur | 25 | 37 |  | +0.95 | 2.76 |
| Uttarakhand | 26 | 36 |  | +2.93 | 3.15 |
| Jharkhand | 28 | 34 |  | +0.83 | 1.96 |
| Odisha | 28 | 34 |  | -0.01 | 0.80 |
| Meghalaya | 29 | 33 |  | +0.36 | 2.83 |
| Andhra Pradesh | 30 | 32 |  | +0.19 | 0.89 |
| Punjab | 30 | 32 |  | +2.38 | 3.22 |
| Haryana | 32 | 30 |  | -0.18 | 0.85 |
| Assam | 34 | 28 |  | -0.15 | 1.03 |
| Rajasthan | 35 | 27 |  | -0.11 | 0.84 |
| Gujarat | 38 | 24 |  | -0.90 | 1.35 |
| Telangana | 38 | 24 |  | -0.33 | 1.08 |
| Kerala | 41 | 20 |  | -0.74 | 1.13 |
| Madhya Pradesh | 41 | 21 |  | -0.66 | 1.04 |
| West Bengal | 43 | 19 |  | -0.95 | 1.68 |
| Uttar Pradesh | 44 | 18 |  | -0.95 | 1.49 |
| Tamil Nadu | 46 | 16 |  | -1.30 | 1.78 |
| Karnataka | 47 | 14 |  | -1.45 | 1.95 |
| Maharashtra | 52 | 10 |  | -0.97 | 1.70 |
| Delhi | 52 | 10 |  | -1.32 | 1.76 |

## Limitations

* Scores describe relative interest and over-performance versus a typical anime; they are not revenue, viewership or audience-size forecasts.
* State labels come from Google Trends relative interest (0-100 normalised), not from consumption data.
* The training set is small; state-ranking skill is modest (see the evaluation table) and wide intervals are expected.
* Demand momentum and engagement quality are not measured for unreleased titles. A component whose held-out Spearman is below 0.1 is shown but excluded; the score is renormalised over the rest and `coverage` shows how much of the 100% weight that is.
* Content fit and comparable performance use global AniList popularity as a proxy because no India outcome exists.
* Population and internet-penetration weights are empty in csv/state_reference.csv, so states are not size-weighted.
* Training includes synthetic title x state rows for cells Google Trends left empty (weighted averages of similar titles and of the title's own related states, weight 30% of a real row). They add no new observations; validation uses real rows only. Sparse states (under 20 real titles) are still the least reliable.
