# Review of public survey compilation

Checked 24 October 2026 against the current CSV, actual source files, and local
scoring code. All five concerns are substantively correct. The prior CSV passed
format validation but did not meet the requested measurement requirements.

## Findings and correction

| Concern | Verified finding | Treatment |
|---|---|---|
| State coverage | Only Delhi has state rows. It supplies 551 of 754 eligible raters, or 73.1% of the pooled baseline. Delhi drama is 99.902 and comedy 100.6304. No state row matches `anime_series`. | Archive these rows outside live inputs. Near-100 values alone do not prove statistical noise, but this sample cannot establish representative state differences. |
| Catalogue/exposure confounding | The national rating index is 224.6373 for drama, 1.7923 for horror and 0.2987 for news. The source catalogue contains 1,612 drama films, 21 horror films and one news film. Selecting at least one rated title is confounded by catalogue size, language-specific presentation and incomplete rating activity. | Do not interpret this as preference or viewing reach. Dividing by catalogue size would change the metric and would not repair the missing viewing observations. |
| Anime coverage | `fantasy`, `sci-fi` and `adventure` yield no national or regional survey result for `anime_series`. Generic preference rows can match action/comedy/drama/romance/horror through blank content type. Exact combined labels remain combined. | Do not relabel film data as anime or split combined genres into invented marginal percentages. |
| Incompatible denominators | MoMAGIC normalizes over four genre categories; the segmentation study over six. For overlapping rows, the loader weights blank sample size as 1 versus 343. Consequently MoMAGIC contributes about 0.29% to an overlapping two-source genre average. | Keep the source observations separate in research. A weighted mean does not make incompatible instruments comparable. |
| Missing years | 45 of 49 rows have no collection year; four are from the 2019 MoMAGIC survey. Dataset/paper publication dates do not establish collection dates. | Preserve unknown dates. Current local loader changes already warn about undated rows; those edits were left intact. |

The 49 rows are preserved in `data/research/proxies/public_affinity_exploratory.csv`.
The compiler now writes there rather than into `data/survey/`. The live
`data/survey/viewing_affinity.csv` contains the required header and zero data rows.
This deliberately yields no survey signal instead of a misleading signal.

## Additional sources inspected

### GEM / Interpret Anime Global White Paper 2026

[Publisher page](https://www.gem-standard.com/p/en/185).
The report covers 2020-2025, includes India, and lists approximately 1,000
respondents aged 13-65 per country. Its contents explicitly include anime genre
preferences and country profiles. This is a stronger lead for national anime
research. Published prices are USD 4,000 for the Japanese report and bilingual
analysis tool, or USD 5,000 including an English report. No purchase was made.

The public page does not expose the full Indian genre table or Indian state
breakdowns. Preference questions may still differ from watching percentages.
Request exact questions, genre categories, Indian bases, collection dates and
state cross-tabs before considering a purchase. No CSV rows were derived.

### Chennai anime/manga study, 2026

[Author-uploaded paper](https://www.researchgate.net/publication/407114557_Global_Media_Local_Markets_How_Anime_and_Manga_Influence_Consumer_Behavior_in_Chennai%27s_Emerging_Youth_Segment),
DOI 10.55041/IJSREM64330.
The paper reports 412 respondents aged 15-30 in Chennai, selected using
purposive/snowball sampling. Reported popular categories are action/shonen 68.4%,
romance/shojo 54.6%, psychological thriller 41.3% and isekai 38.9%.

This is a local anime-specific lead, but the published labels mix genres and
demographics. It does not provide a matching all-India baseline. Chennai is not
representative of all Tamil Nadu. The initial review inspected the author upload.
In the subsequent expanded search, the DOI was verified through Crossref and the
publisher's complete PDF was downloaded. Its fieldwork spans October 2025-January
2026. Four published Chennai findings are now preserved in
`regional_genre_evidence.csv`, with city scope and measurement limitations. They
still do not qualify as state viewing indices. See `regional_genre_evidence.md`
for the expanded source audit. The paper's results were not independently
validated against individual responses.

### Bengaluru youth study, May 2023

[Original paper](https://www.ijsdr.org/papers/IJSDR2305232.pdf).
The study concerns anime among Bengaluru youth and includes genre questions.
Its discussion of a convenience sample of 107 appears in a literature-review
section about an earlier American study, and the number recurs later in the
discussion. It is not a verified Bengaluru respondent base. This ambiguity,
the absence of a clean state-genre viewing table, and the lack of a compatible
national denominator prevent using it for Karnataka indices. No CSV rows were
derived.

### Consumer Behaviour Towards Anime in India, April 2024

[Original paper](https://ijirt.org/publishedpaper/IJIRT163544_PAPER.pdf).
It describes 100 respondents, recruited through online, convenience and snowball
methods. Genre preferences are among its objectives, but the published findings
do not provide the complete state-by-genre viewing table required here. No CSV
rows were derived.

### Trinity Media Review, 2025 anime study

[Original issue](https://www.tips.edu.in/download_pdf/323.pdf), printed pages 8-13.
It reports action/adventure 88.2%, romance 58.8%, psychological/thriller 47.1%.
The recruitment discussion targets global online anime communities. The relevant
section does not establish an Indian respondent base, a complete genre response
table, or usable state samples. Its bibliography calls the underlying 2024
questionnaire results unpublished. Do not infer a sample size from rounded
percentages. No CSV rows were derived.

### International Anime Research Project, 2025 results

[Research team's preliminary findings](https://sites.google.com/site/animeresearch/past-results/anime-survey-2025-preliminary-results).
The study includes 1,369 fans, with India reported as 1.6% of the sample. Genres
are measured on a seven-point liking scale; published comparisons are global.
That is a small Indian subset, without Indian state cross-tabs or a compatible
viewing-percentage denominator. No global means were relabelled as Indian data.

### Crunchyroll / National Research Group

[Original public study](https://view.ceros.com/nrgmr/crunchyroll-global-state-of-anime).
It describes 29,000 general entertainment consumers aged 13-54 across seven
markets including India, with 3,500 anime fans in the research. These are pooled
study bases, not Indian state counts. No public complete Indian-state anime
genre-viewing cross-tab was identified. No CSV rows were derived.

## Data needed to populate the live file

Use one common questionnaire and period for state and national measurements.
For every emitted state/genre/type row, retain the state numerator and denominator
and the corresponding India numerator and denominator, along with weighting,
collection year and provenance. Use a fixed documented genre set for national
normalization. Keep survey waves, preference scales, watching percentages,
platform behaviour and search-interest indices separate.

No compatible public replacement table was found in this search. The new leads
are documented for follow-up, not asserted to fill the missing state data.
