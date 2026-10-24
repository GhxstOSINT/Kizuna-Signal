# Verified regional genre findings

Checked 24 October 2026. **The original viewing-affinity file cannot be populated
from the inspected public sources without changing the measurement or inventing
a national denominator.** None supplies compatible state and all-India genre
watching percentages with the necessary population definitions.

The user's fallback request, identifying genres popular in particular places,
can be partially met. [`regional_genre_evidence.csv`](regional_genre_evidence.csv)
contains **166 extracted findings from 10 sources**, including city samples,
combined-state results, country-level anime preferences, and separately labelled
book preferences. All 13 teammate-provided sources were inspected; two additional
sources supply Delhi and Chennai findings. The audit records the outcome for all
15 sources, source hashes, raw five-point counts and extracted values.

## Findings that answer the regional question

| Location and actual coverage | What the evidence says | Respondents and question |
|---|---|---|
| Delhi: Delhi respondents in the NCR study | Comedy 68.52%, thriller 60.49%, action 59.26%. Comedy leads the retained genre categories. | 162 Delhi respondents; multiple-choice preferred OTT genres. Collection year unreported; dataset published 2026. No anime-specific question. |
| Gujarat: Ahmedabad city only | Comedy 58%, suspense 57%, crime and mystery/thriller 52%, adventure 43% selected the highest preference category. | 100 respondents, Jan-Mar 2023; five-point film preference scale. These are the percentages choosing category 5, not percentages watching the genres. |
| Tamil Nadu: Chennai city only | Action/shonen 68.4%, romance/shojo 54.6%, psychological thriller 41.3%, isekai 38.9%. | 412 anime/manga consumers aged 15-30; purposive/snowball sample; Oct 2025-Jan 2026. Published as popular anime genres. |
| Andhra Pradesh and Telangana combined | Horror/thriller has the largest theatre-minus-OTT preference score, +90 percentage points; comedy +62. | 235 respondents combined. State sample counts are 119 AP and 116 Telangana, but no separate genre scores are published. |
| Karnataka: Bengaluru and Mysore | Horror/thriller +82 points, action/adventure +52, romance +44 on the theatre-minus-OTT measure. | 220 respondents; venue preference, not viewing reach. |
| Kerala report sample | The numeric chart's largest theatre-minus-OTT score is action/adventure +84 points, followed by horror/thriller +82 and animation/fantasy +64. | 106 respondents. This is a small report sample, not a representative state estimate. |
| Tamil Nadu: Chennai and Coimbatore | Horror/thriller +60 points, romance +52, action/adventure +50. Animation/fantasy is +44, versus +22 in the South survey total. | 218 respondents; theatre-minus-OTT venue preference. The animation/fantasy category is not anime. |
| Uttar Pradesh: Raebareli and surroundings | Action/thriller emerges as a qualitative preference theme in the cinema-going interviews. | 80 interviews in the study; no quantitative genre prevalence or statewide estimate. |

Sources: the first three rows use the [Delhi-NCR Mendeley dataset](https://data.mendeley.com/datasets/fztpnhzhs6/1),
[Ahmedabad paper, Table 3](https://www.gapinterdisciplinarities.org/res/articles/(64-77)%20TOLLYWOOD%20VS.%20BOLLYWOOD-A%20STUDY%20ON%20AUDIENCES%20PERCEPTIONS.pdf),
and [Chennai publisher PDF, section 5.1](https://ijsrem.com/download/global-media-local-markets-how-anime-and-manga-influence-consumer-behavior-in-chennai-s-emerging-youth-segment/fulltext.pdf).
The venue scores come from [South Cinema slide 15](https://www.slideshare.net/slideshow/south-cinema-audience-behaviour-reportpdf/261182622).
The qualitative result comes from [the Raebareli paper](https://www.arfjournals.com/image/catalog/Journals%20Papers/SAAN/2021/No%201%20(2021)/Final_manuscript_6_Anirban_Mukherjee.pdf).

These findings belong to their actual sampled populations. A city, event or
convenience sample is not automatically representative of its state, and the
different measurements must not be averaged together.

## Anime-specific findings

[Hakuhodo/FANFARE's original Japanese report](https://files.hakuhodo.co.jp/files/user/2026/03/20260331_%E6%97%A5%E6%9C%AC%E3%82%A2%E3%83%8B%E3%83%A1IP%E3%82%B0%E3%83%AD%E3%83%BC%E3%83%90%E3%83%AB%E3%83%95%E3%82%A1%E3%83%B3%E3%82%A8%E3%83%B3%E3%82%B2%E3%83%BC%E3%82%B8%E3%83%A1%E3%83%B3%E3%83%88%E8%AA%BF%E6%9F%BB.pdf)
provides 11 genre-liking percentages for its India arm, led by action 60.0%,
mystery 55.9%, comedy 51.3% and fantasy 47.7%. The main India sample is 1,000,
fielded August-September 2025, ages 16-39. The 5,000-person screening sample is
not used as the genre question base. Eligibility includes potential anime users,
including interested people without viewing experience. This is not the share of
all Indian viewers watching these genres, and no state breakdown is published.
The chart labels, not expanded labels in the prose summary, determine the rows.

[Anime and Escapism](http://jmc.cutn.ac.in/docs/2026JM&CJune4.pdf), inspected in the
downloaded 13-page original, reports 310 purposively sampled respondents across
Kerala, Telangana, Andhra Pradesh, Karnataka and Tamil Nadu. The pooled preferred
watching genres are action 28.5%, supernatural/magic 25.3%, comedy/slice of life
10.2%, psychological 9%, romance 8%, historical 6%, drama/tragedy 6%, mecha/military
3%, and all-of-the-above 4%. There are **no published state-by-genre percentages**.
No pooled figure was assigned to an individual state. Collection year is not
established by the June 2026 publication date.

The Chennai anime paper is a useful local result, not a Tamil Nadu-to-India
comparison. Its DOI was verified using Crossref, followed to the publisher and
the full PDF inspected. Fieldwork spans two years, so the CSV `year=2026` is
explicitly the end year and `survey_period` preserves both years. Reported labels
such as action/shonen and romance/shojo combine a genre with a demographic and
are retained without splitting into invented separate percentages.

## Reading and television evidence

[NCAER Table 4.13](https://ncaer.org/wp-content/uploads/2022/09/1380783944NBT-North-East-Youth-Readership-Survey-report-19112012-1.pdf)
uses NYRS 2009, not the 2012 publication year. Among its fiction-book preference
categories, Maharashtra leads with fantasy 30.6%, Bihar with comics 24.9%, and
Assam with romance 23.8%. The other north-eastern states are combined in the
published table. The CSV includes all nine categories for all six table rows,
including the national and combined-region rows. None is labelled as anime or
film. Genre-question respondent counts are not supplied in this table and remain
blank, rather than substituting population estimates for sample sizes.

[BARC's Breaking the News Story](https://www.barcindia.co.in/newsletter/breaking-the-news-story.pdf)
compares each state market's share of all-India news impressions with its share of
total-TV impressions for weeks 08-48 of 2017. These measures are retained in
separate `value` and `reference_value` fields. They are impressions, not unique
viewers, and must not be substituted for the requested watching percentages.
Grouped markets stay grouped. For example, UP/Uttarakhand is one market, not two
independent state measurements. The full-time target population differs from the
report's later event-specific male-22+ analyses; the CSV uses only the initial
state-market table.

## Results for every teammate source

| Source inspected | Decision after inspection |
|---|---|
| South Cinema Audience Behaviour Report, slides 14, 15 and 25 | Retained 45 net venue scores with sample bases. No all-India genre watching rates. |
| NCAER-NBT Youth Readership, especially Tables 4.8-4.16 | Retained 54 values from overall fiction Table 4.13. Useful for reading only. |
| BARC Breaking the News Story, state-market and event-format tables | Retained 15 state-market impression shares and their corresponding total-TV shares. News formats and event windows are not entertainment genres or regular viewing reach. |
| Anime and Escapism | Retained nine pooled response shares, with no state duplication. Original HTTPS certificate was expired; the publisher's public HTTP URL downloaded successfully. |
| INTAGE Part 1 | Bengaluru event lifestyle/values research, not a state-genre survey. No affinity rows extracted. |
| JETRO TV Asahi interview | Broadcast/localisation strategy and examples of popular titles. No measured state-genre table. |
| Hakuhodo Global Fan Survey | Retained 11 India-arm anime-liking shares; actual fieldwork dates and base verified. No states. |
| Mapping movie genre evolution, PubMed 37771613 | Inspected the indexed primary article and data-availability description. Underlying Zenodo data identify top Bollywood grossers over time; no respondent states or genre-viewing denominators. |
| Escapist versus eudaimonic viewers | Full 19-page PDF: 324 usable respondents; published genre Likert results are separated by audience cluster and venue, not state. |
| Tollywood vs Bollywood | Full 14-page PDF: retained 12 highest-preference shares from the Ahmedabad sample. Original five-category counts retained in the audit. |
| Social Experience of Cinema-going in Single Screens | Full 11-page PDF: retained one qualitative action/thriller finding, with no invented percentage. |
| Theatrical Viewing vs Digital Alternatives, Kerala | Full 13-page PDF: retained the 76.2% home/digital and 23.8% theatre choices for a hypothetical mid-budget drama/comedy. Not a ranking of most-watched genres. |
| 70 Years of BHollywood | Full 17-page arXiv PDF: film subtitles and representation, not audience genre-watching by residence. |

The source URLs, retained record counts, downloaded-file SHA-256 hashes and
exclusion reasons are in `regional_genre_evidence_audit.json`.

## Extraction and data-quality rules

- Numeric tables and relevant footnotes were visually checked against the original
  slide images or rendered PDF pages. Percentages were not transcribed from search
  snippets alone.
- Combined genres and grouped states are preserved. `state` is blank for combined
  regions; `geography` names the actual group. Individual state rows can still be
  city samples, identified by `geography_scope`.
- Negative values in the South Cinema chart are valid net venue scores, not
  negative viewing percentages. They are stored as percentage points.
- Some South Cinema parenthetical deltas are inconsistent with their main values
  and overall column. For example, AP/Telangana action/adventure is printed as
  32 with a +18 annotation against overall 50. Kerala animation/fantasy is printed
  as 64 with a +34 annotation against overall 22. Only the main values are
  transcribed; the erroneous-looking annotations are not used or silently repaired.
  The headline calls thriller the top Kerala cinema genre, while the numeric chart
  gives action/adventure 84 and horror/thriller 82. The summary follows the chart.
- A missing collection year stays missing. `publication_year` is separate.
- A qualitative theme has blank `value` and `unit=qualitative`; the 80 interviews
  are a study base, not a count preferring that genre.
- For Ahmedabad, `value` is the percentage choosing the highest of five preference
  categories. `reference_value` is the independently available top-two-category
  percentage. For Delhi, `reference_value` is the original selection count and
  `value=100*count/162`. The reference-measurement column disambiguates them.
- No cross-source average, synthetic respondent, genre expansion, or fabricated
  affinity index was generated. Exact state watching indices remain unavailable.

The additional repository search covered public Mendeley, Kaggle, Zenodo,
Dataverse, OSF and Hugging Face results, plus anime audience and OTT reports.
An Indian OTT project with state and genre fields explicitly generates synthetic
users/histories and was rejected. Original MyAnimeList file inventories and partial
profile downloads were inspected. These are global self-selected account profiles,
not a state survey; profile totals have no genre numerator. The profile downloads
timed out, and no partial profiles or rating records were converted into survey
measurements. No account login, payment or outreach was undertaken.

## Using the files

This CSV fulfils the fallback request for sourced regional genre evidence. It
uses measurement and geography columns because a seven-column affinity schema
cannot express these distinctions faithfully. It is stored in `data/research/`,
outside live survey loading. `data/survey/viewing_affinity.csv` remains header-only.

Reproduce the CSV and audit with the downloaded originals present:

```sh
.venv/bin/python scripts/compile_regional_genre_evidence.py
```

Downloaded originals stay in the gitignored `survey_sources/` directory. The
shareable output contains only aggregates and source citations, not identifiers.
