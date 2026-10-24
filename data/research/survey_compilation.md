# Public affinity compilation

Retrieved 24 October 2026. The archived exploratory file is
[`proxies/public_affinity_exploratory.csv`](proxies/public_affinity_exploratory.csv).
It contains **49 rows: 30 India rows and 19 Delhi rows**, in the seven-column schema.
It has been removed from live survey loading after review. Passing the CSV loader
checks its syntax, not the validity of its measurement or population coverage.
See [the follow-up audit](survey_followup_audit.md) for the five reported issues
and additional anime-specific research.

## What these numbers mean

**These are exploratory preference and rating proxies, not a representative survey
of genre viewing rates.** They use the requested ratio arithmetic on the available
measurements. The measurement difference is explicit in every `source` field and
in comments at the top of the CSV. Do not describe them as measured state-wide
over-watching or under-watching. There is no verified anime-specific genre survey
in this compilation.

The current local application changes warn about proxy-only signals and undated
rows, but still calculate affinity from these measurements. Putting this CSV in
`data/survey/` would make it live input when survey loading is enabled. A blank
`content_type` matches any format, so the broad preference rows can also influence
anime scores despite not being anime-specific. Film rating rows only match film
formats. Sample-size confidence thresholds do not correct sampling bias or the
fact that multiple genre rows reuse the same respondents.

The archive is outside the configured survey directory and the compiler writes
only to the archive. `data/survey/viewing_affinity.csv` contains the expected
header and no data rows. A properly representative viewing file cannot be
reconstructed from the currently retrieved public sources.

## Included sources and calculations

### MoMAGIC / mChamp 2019: four national preference rows

[Original press release](https://www.momagic.com/index.php/portfolio/55-of-indians-prefer-ott-platforms-vs-41-that-still-prefer-dth-momagic-survey/)

The survey ran June to mid-August 2019. Although the hosting page displays a later
publication date, the survey year is 2019. Its four reported genre percentages are
comedy 45, action 23, drama 19, horror 13. Their mean is 25, yielding indices
180, 92, 76 and 52 respectively. This measures preferred genre, not viewing reach.

The release gives approximately 7,500 overall respondents, but no separate genre
question base. `sample_size` is therefore blank rather than an invented exact
7,500. The existing loader assigns blank sample sizes weight 1.

### OTT segmentation study: six national preference rows

[Mendeley record, DOI 10.17632/vcp7w8t2kg.1](https://data.mendeley.com/datasets/vcp7w8t2kg/1)

Downloaded `Table.xlsx`, locally named `ott_segmentation.xlsx`. This is a workbook
of aggregate study tables, **not raw individual survey responses**. Sheet 1 reports
preferred genre counts: comedy 68, romance 36, action 53, crime thrillers 133,
drama 30 and non-fiction 23. The counts sum to 343. Each index is
`100 * genre_count / (343 / 6)`. Every row has `sample_size=343`.

The sample is a convenience sample of Indian OTT consumers. The record was
published in 2024, but the collection year is unreported, so `year` is blank.
`crime thrillers` remains one combined category; it is not duplicated into
separate crime and thriller rows. `non-fiction` is preserved as its original
category. They will only match titles with equivalent normalized genre tags.

License: CC BY 4.0. Contributors: Angana Bose, Saurabh Mishra, Kavita Srivastava,
Amruthom KU. Changes: extracted published counts and calculated relative indices.

### Indian Regional Movie Dataset: 20 national and 19 Delhi rating rows

[Paper](https://arxiv.org/abs/1801.02203) by Prerna Agarwal, Richa Verma and
Angshul Majumdar. [Original public download folder](https://drive.google.com/drive/folders/18g2y8sia_Uv2PDwwRGvdBbVyPR4ieo4s).

All three original files downloaded successfully. The files contain 924 user
records, 2,850 movies and 763 rating records. These counts differ from the paper's
summary; this compilation uses the downloaded records. Nine rating records have
no nonzero movie ratings, leaving 754 eligible raters, including 551 in Delhi.

For each eligible rater, count a genre once if at least one movie in that genre
has an explicit like (`1`) or dislike (`-1`). Both are rating evidence. Ignore
zeros, unrated movies, and form-submit fields. This is a proxy for genre exposure,
not a complete record of what someone watched or liked. Movies can have several
genres. No ratings or missing responses are imputed.

For each genre:

```
state fraction = eligible state raters with any nonzero rating in genre / eligible state raters
pooled fraction = eligible raters with any nonzero rating in genre / 754
state index = 100 * state fraction / pooled fraction
national index = 100 * pooled fraction / mean(pooled fractions across 21 catalogue genres)
```

The national baseline is this **Delhi-heavy respondent pool**, not a weighted
all-India audience estimate. Only Delhi has at least 150 eligible respondents.
All other states are omitted. The audit records their actual sample counts.

Catalogue genres with no observed ratings are omitted instead of asserting no
viewing. Western has no observations nationally; news has none in Delhi. The
national mean still uses the fixed 21-genre catalogue, including Western's zero
observed rating fraction. This explains why the mean of the emitted national
rows alone is not exactly 100. Source genre labels are retained: for example,
`sci-fi`, `sport` and `animation` are not silently turned into other title tags.

The paper was submitted in 2018 and lists a 2017 dataset release; the actual
response collection year is not established. `year` is blank. The source field
records the historical release context. Raw respondent identifiers stay in the
local, gitignored originals; output and audit files contain only aggregates.

## Retrieved but excluded from affinity rows

| Source | Retrieved material and reason |
|---|---|
| [Delhi-NCR OTT survey](https://data.mendeley.com/datasets/fztpnhzhs6/1) | Downloaded original `Data Set.xlsx`, 220 records. Genre/category counts and city counts are in the audit. No comparable national baseline exists. Its respondents live across Delhi, Haryana, Uttar Pradesh and Rajasthan; the whole sample is not assigned to Delhi. Genre answers also mix formats and origins. |
| [Movie reviewer survey](https://data.mendeley.com/datasets/6gcy6nhxj6/1) | Downloaded original `Movie_Survey_Final_1071.xlsx`, 1,071 records. Favourite-genre counts are in the audit. No state/country residence fields establish Indian respondent coverage. Indian films and platforms alone do not establish residence. |
| [YouGov 2022](https://yougov.com/articles/44094-seven-ten-urban-indians-claim-their-frequency-goin) | Retrieved article. Comedy 67%, action 54%, thriller 51%, urban sample 1,004. These are leading preferences; the complete genre question/category list is not established, so averaging only these three would invent the national denominator. |
| [Hotstar India Watch 2019](https://secure-media.hotstar.com/media-website/indiawatchreport2019/India_Watch_Report_2019.pdf) | Downloaded the complete 55-page PDF. Includes platform consumption shares, demographic charts and geographic comparisons, but no complete numerical state-genre reach table with matching national denominators. Watch-time shares and audience composition are not respondent reach. |
| [Parrot Analytics Q3 2023](https://www.parrotanalytics.com/insights/state-of-streaming-and-television-in-india-q3-2023-netflix-sony-tv-amazon-prime-video-disney-and-hbo/) | Retrieved article. Selected demand shares are in the audit. Proprietary demand is not percentage of viewers watching; article text does not supply the complete genre table. |
| [Comscore 2021](https://www.comscore.com/Insights/Presentations-and-Whitepapers/2021/Exclusive-research-OTT-in-India) | Retrieved landing page. No downloadable numerical survey table or usable full genre denominator was exposed there. |
| [Hakuhodo anime study 2026](https://www.hakuhodoindia.com/news/anime-study) | Retrieved public study announcement. Platform/device/dubbing percentages for anime viewers are not within-anime genre reach. |
| [Ormax OTT audience report 2026](https://ormaxmedia.com/insights/stories/the-ormax-ott-audience-report-2026.html) | Retrieved public announcement. The full report requires subscription. Audience totals, growth rates and content-format growth are not genre-viewing percentages. |

The Mendeley Delhi-NCR and reviewer records are CC BY 4.0. Attribute their
contributors from the linked records if reusing their data. Retrieved snapshots
are local reference material; a public download does not itself grant unrestricted
redistribution rights to all reports.

## Reproduce and validate

From the repository root, with the downloaded originals present:

```sh
.venv/bin/python scripts/compile_public_survey.py
.venv/bin/python -m pytest tests/unit/test_census_and_survey.py
```

The compiler checks the six segmentation counts, emits the archived CSV, reads it
through the actual application loader for syntax validation only, and writes aggregate calculation evidence plus
SHA-256 hashes to `survey_compilation_audit.json`. It does not send respondent
data anywhere. Original downloads are retained in the gitignored
`data/research/survey_sources/` directory on this machine.

Source collection dates are not replaced with publication years. The application's
staleness function now warns about blank-year rows, but cannot date them, and only
evaluates the newest known year for staleness. The archive is historical.
The application's default sample-size weighting also combines sources with
different question/category sets; the resulting blend is an exploratory signal,
not a statistically pooled survey estimate.
