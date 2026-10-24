# Synthetic survey data

**Everything here is simulated. None of it is measured viewing behaviour.** It exists to exercise
the survey pipeline (loader, state scoring, content-fit blend) and to demo it at volume. It must not
be presented as research or used to support a real launch decision.

| File | What it is |
|---|---|
| `synthetic_viewing_affinity.csv` | 1,887 aggregated rows in the survey-loader schema (`data/survey/README.md`): 36 states + `India`, 17 genres, 3 waves (2024-2026), `content_type=anime`. |
| `microdata/synthetic_survey_respondents.csv` | About 291,000 cleaned simulated respondents (state, wave, 17 genre yes/no flags). Git-ignored; regenerate it. |
| `synthetic_survey_audit.json` | Seed, assumed base rates, input handling and cleaning counts per wave. |

Every affinity row's `source` starts with `PROXY synthetic:`, so the app lowers the source quality
to 0.75 and warns that the signal is not measured viewing.

## Using it

**This folder is the app's default survey folder (`KIZUNA_SURVEY_DIR=data/synthetic`) in both demo
and live mode.** The regional source uses the Census tables plus these rows, and every analysis
carries the proxy warning and a lowered source quality (0.75). To exclude simulated rows, set
`KIZUNA_SURVEY_DIR=data/survey` (real rows only). Do **not** copy these files into `data/survey/`.

The respondent file sits in `microdata/` because the loader reads every `*.csv` directly inside its
folder and rejects files without `state`, `genre` and `index` columns.

Regenerate (deterministic for a given seed) or scale up:

```sh
python backend/scripts/data/generate_synthetic_survey.py                    # about 300,000 respondents
python backend/scripts/data/generate_synthetic_survey.py --respondents 1000000 --seed 7
```

## How it is generated

A latent-normal (probit) simulation. A respondent watches genre `g` when

    z = a_g + b_sg + u_s + trend_g + rho * e_i + sqrt(1 - rho^2) * eta_ig  >  0

with `e_i` (respondent engagement) and `eta_ig` standard normal, redrawn beyond +/-3, so the share
of state `s` watching genre `g` is `Phi(a_g + b_sg + u_s + trend_g)`.

* **`a_g` (national level):** AniList popularity order of the 17 genres (from
  `data/training/super_training_dataset.csv`), rescaled to a 12%-82% watch rate. The *range is an
  assumption*: no public source gives India genre percentages (see
  `data/research/survey_followup_audit.md`).
* **`b_sg` (state x genre):** the Google-Trends `lift` in
  `data/training/training_table_title_x_state.csv`, winsorised, shrunk and damped, plus normal
  noise. Because that is search interest, this part overlaps the Trends signal the app already
  scores on; do not treat the two as independent evidence.
* **`u_s` (state engagement):** Census urban share (z-score capped at +/-2) plus normal noise.
* **Sample sizes:** proportional to the square root of state population, minimum 400 per wave, so
  small states are noisy, as real surveys are.
* **Index:** `100 * state rate / population-weighted all-India rate`. `India` rows use
  `100 * rate / mean rate across genres`, as the loader README defines.

## Outlier handling

1. Trends lifts are winsorised at median +/- 3.5 robust sigmas before use.
2. Draws from the normal distribution are truncated at +/-3 sigma.
3. 2% straight-liners and 1% all-"no" respondents are *injected*, then removed: all-"no", ticking
   15 or more of 17 genres, or a modified z-score above 3.5 on genres ticked. The audit reports
   how many injected bad respondents were caught (all of them) and how many genuine ones were
   dropped (about 0.4%).
4. State x genre indices are winsorised across states per genre (median +/- 3.5 robust sigmas,
   bounded to 25-300).
5. Urban share is capped so Delhi and Chandigarh are not extreme.

## Limits

* The structure is built in, so a model trained on this data will recover that structure and
  nothing real about India.
* `year` is a simulated wave, not a collection date. The anime-only content type means other
  formats (manga, film) match no rows.
