# Survey / viewing-behaviour data

Drop one or more `.csv` files in this folder (or point `KIZUNA_SURVEY_DIR` elsewhere). They are
read on every analysis in live mode (`KIZUNA_DEMO_MODE=false`); there is no sample data here on
purpose — the system reports "No survey data loaded" until you add real files.

| column | required | meaning |
|---|---|---|
| `state` | yes | Indian state/UT (aliases such as `Delhi NCR` work), or `India` for a national row |
| `genre` | yes | genre as surveyed (`fantasy`, `action`, `romance`, ...) — matched to the title's genres |
| `index` | yes | viewing-affinity index, **100 = that state's average viewer**, 150 = 50% over-index |
| `content_type` | no | `anime`, `drama`, `film`, ... — matched against the title's content format; blank = any |
| `sample_size` | no | respondents behind the row; rows are averaged weighted by it (default 1) |
| `year` | no | survey year; data older than 3 years triggers a staleness warning |
| `source` | no | citation shown in provenance (default: file name) |

Lines starting with `#` are comments. Bad rows (unknown state, non-numeric values) are skipped and
reported in the analysis warnings instead of failing the run.

How it is used: state rows feed each state's score (20% weight) and its confidence; national rows
feed the `genre_affinity` metric, which adjusts `content_fit` (35%) and `regional_opportunity`.
