"""Reproduce verified regional findings without inventing viewing-affinity indices.

Public originals are local in data/research/survey_sources/. The output deliberately
uses an evidence schema: these measurements are not interchangeable viewing rates.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]  # repository root
RAW = ROOT / "data/research/survey_sources"
OUT = ROOT / "data/research/regional_genre_evidence.csv"
AUDIT = ROOT / "data/research/regional_genre_evidence_audit.json"
FIELDS = [
    "state",
    "geography",
    "geography_scope",
    "genre",
    "content_type",
    "measurement",
    "value",
    "unit",
    "sample_size",
    "year",
    "survey_period",
    "publication_year",
    "reference_value",
    "reference_measurement",
    "source_id",
    "source_locator",
    "source",
    "limitations",
]
HAKU = "https://files.hakuhodo.co.jp/files/user/2026/03/20260331_%E6%97%A5%E6%9C%AC%E3%82%A2%E3%83%8B%E3%83%A1IP%E3%82%B0%E3%83%AD%E3%83%BC%E3%83%90%E3%83%AB%E3%83%95%E3%82%A1%E3%83%B3%E3%82%A8%E3%83%B3%E3%82%B2%E3%83%BC%E3%82%B8%E3%83%A1%E3%83%B3%E3%83%88%E8%AA%BF%E6%9F%BB.pdf"
SOURCES = {
    "south_cinema": {
        "url": "https://www.slideshare.net/slideshow/south-cinema-audience-behaviour-reportpdf/261182622",
        "files": ["south_cinema.html", "south_cinema_slide_15.jpg", "south_cinema_slide_25.jpg"],
        "publication_year": 2023,
        "finding": "Regional theatre-minus-OTT genre preference scores; not viewing incidence. AP and Telangana combined.",
    },
    "ncaer": {
        "url": "https://ncaer.org/wp-content/uploads/2022/09/1380783944NBT-North-East-Youth-Readership-Survey-report-19112012-1.pdf",
        "files": ["ncaer_2012.pdf"],
        "publication_year": 2012,
        "year": 2009,
        "finding": "State fiction-book preferences in Table 4.13; reading, not watching. Other NE states remain grouped.",
    },
    "barc": {
        "url": "https://www.barcindia.co.in/newsletter/breaking-the-news-story.pdf",
        "files": ["barc_news_2017.pdf"],
        "publication_year": "",
        "year": 2017,
        "finding": "State-market shares of national news impressions versus total-TV impressions; not viewer reach.",
    },
    "south_anime": {
        "url": "http://jmc.cutn.ac.in/docs/2026JM&CJune4.pdf",
        "files": ["anime_escapism_2026_http.pdf"],
        "publication_year": 2026,
        "finding": "310 purposively sampled anime respondents across five states; genre results pooled, collection year unreported.",
    },
    "intage": {
        "url": "https://www.global-market-surfer.com/pickup/detail/648/?l=en&",
        "files": ["intage_2026.html"],
        "publication_year": 2026,
        "finding": "Bengaluru anime-event lifestyle research; no state-by-genre viewing table.",
    },
    "jetro": {
        "url": "https://www.jetro.go.jp/biz/areareports/2025/dde7ff4cd0c3859d.html",
        "files": ["jetro_2025.html"],
        "publication_year": 2025,
        "finding": "TV Asahi strategy interview; no measured state-genre percentages.",
    },
    "hakuhodo_global": {
        "url": HAKU,
        "files": ["hakuhodo_global_2026.pdf"],
        "publication_year": 2026,
        "year": 2025,
        "finding": "India-arm anime liking percentages; n=1000 potential anime users aged 16-39, fieldwork Aug-Sep 2025. No states.",
    },
    "genre_evolution": {
        "url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC10523098/",
        "files": [],
        "publication_year": 2023,
        "finding": "Inspected indexed full text after PubMed access challenge. Underlying Zenodo data are top Bollywood grossers, not respondents or states.",
        "underlying_data": "https://doi.org/10.5281/zenodo.7154229",
    },
    "southern_clusters": {
        "url": "https://fslmjournals.taylors.edu.my/wp-content/uploads/SEARCH/SEARCH-2023-15-1/SEARCH-2023-P4-15-1.pdf",
        "files": ["southern_cinema_clusters_2023.pdf"],
        "publication_year": 2023,
        "finding": "324 usable responses from five southern cities; published Likert comparisons by cluster and venue, not state cross-tabs.",
    },
    "ahmedabad": {
        "url": "https://www.gapinterdisciplinarities.org/res/articles/(64-77)%20TOLLYWOOD%20VS.%20BOLLYWOOD-A%20STUDY%20ON%20AUDIENCES%20PERCEPTIONS.pdf",
        "files": ["tollywood_bollywood.pdf"],
        "publication_year": 2023,
        "year": 2023,
        "finding": "Ahmedabad city n=100, Jan-Mar 2023; Table 3 has five-point film genre preference distributions.",
    },
    "raebareli": {
        "url": "https://www.arfjournals.com/image/catalog/Journals%20Papers/SAAN/2021/No%201%20(2021)/Final_manuscript_6_Anirban_Mukherjee.pdf",
        "files": ["single_screen_2021.pdf"],
        "publication_year": 2021,
        "finding": "80 qualitative interviews in Raebareli and surroundings; action/thriller theme, no numerical genre prevalence.",
    },
    "kerala_venues": {
        "url": "https://pdfs.semanticscholar.org/9357/21a88132a7a8fe815143a500e12e956cf91e.pdf",
        "files": ["kerala_theatrical_digital.pdf"],
        "publication_year": 2026,
        "finding": "143 purposively sampled Kerala respondents; venue choice for mid-budget drama/comedy, not a genre popularity ranking.",
    },
    "representation": {
        "url": "https://arxiv.org/pdf/2102.09103",
        "files": ["bollywood_representation.pdf"],
        "publication_year": 2021,
        "finding": "Geographic and gender representation in film subtitles; no viewer state-genre survey.",
    },
    "delhi_ncr": {
        "url": "https://data.mendeley.com/datasets/fztpnhzhs6/1",
        "files": ["delhi_ncr.xlsx", "fztpnhzhs6_files.json"],
        "publication_year": 2026,
        "finding": "Original 220 responses inspected. City fields identify 162 Delhi, 45 Haryana, 12 UP and one Rajasthan respondent. Only Delhi meets n>=150.",
    },
    "chennai_anime": {
        "url": "https://ijsrem.com/download/global-media-local-markets-how-anime-and-manga-influence-consumer-behavior-in-chennai-s-emerging-youth-segment/fulltext.pdf",
        "files": ["chennai_anime_2026.pdf"],
        "publication_year": 2026,
        "year": 2026,
        "finding": "Publisher PDF and Crossref DOI verified. Chennai city n=412, Oct 2025-Jan 2026, purposive/snowball sample. Four reported genre preferences.",
    },
}


def read_xlsx(path: Path) -> list[dict[str, str]]:
    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    with zipfile.ZipFile(path) as z:
        strings = [
            "".join(t.text or "" for t in si.findall(".//m:t", ns))
            for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si", ns)
        ]
        records = []
        for row in ET.fromstring(z.read("xl/worksheets/sheet1.xml")).findall(
            ".//m:sheetData/m:row", ns
        ):
            item = {}
            for cell in row.findall("m:c", ns):
                v = cell.find("m:v", ns)
                value = (
                    strings[int(v.text)]
                    if cell.get("t") == "s"
                    else v.text
                    if v is not None
                    else ""
                )
                item[cell.get("r").rstrip("0123456789")] = value
            records.append(item)
        return records


def main() -> None:
    rows = []

    def add(
        sid,
        state,
        geo,
        scope,
        genre,
        kind,
        measurement,
        value,
        unit,
        n,
        locator,
        notes,
        period="",
        reference="",
        reference_measure="",
    ):
        src = SOURCES[sid]
        rows.append(
            dict(
                zip(
                    FIELDS,
                    [
                        state,
                        geo,
                        scope,
                        genre,
                        kind,
                        measurement,
                        value,
                        unit,
                        n,
                        src.get("year", ""),
                        period,
                        src["publication_year"],
                        reference,
                        reference_measure,
                        sid,
                        locator,
                        src["url"],
                        notes,
                    ],
                    strict=True,
                )
            )
        )

    # The chart's main numbers are transcribed. Its inconsistent parenthetical deltas are NOT used.
    genres = [
        "horror / thriller",
        "action / adventure",
        "romance",
        "comedy",
        "crime",
        "animation / fantasy",
        "historical",
        "sci-fi",
        "drama",
    ]
    markets = [
        (
            "",
            "South India survey total",
            "regional_pool",
            779,
            [78, 50, 46, 30, 24, 22, 18, 16, 14],
        ),
        (
            "",
            "Andhra Pradesh & Telangana",
            "combined_states",
            235,
            [90, 32, 36, 62, 16, -8, 14, 14, 44],
        ),
        (
            "Kerala",
            "Kerala report sample",
            "state_sample",
            106,
            [82, 84, 62, 52, 58, 64, 48, 54, 50],
        ),
        (
            "Tamil Nadu",
            "Tamil Nadu: Chennai and Coimbatore",
            "cities_in_state",
            218,
            [60, 50, 52, -4, 4, 44, -2, -18, -40],
        ),
        (
            "Karnataka",
            "Karnataka: Bengaluru and Mysore",
            "cities_in_state",
            220,
            [82, 52, 44, 20, 34, 16, 28, 32, 18],
        ),
    ]
    for state, geo, scope, n, values in markets:
        for genre, value in zip(genres, values, strict=True):
            add(
                "south_cinema",
                state,
                geo,
                scope,
                genre,
                "film",
                "theatre_minus_ott_preference_net_score",
                value,
                "percentage_points",
                n,
                "slide 15; bases checked on slide 25",
                "Venue preference, not watching rate; combined categories preserved; collection year unreported.",
            )

    # Table 4.13 only: overall, not urban/rural subgroups or non-fiction mixed into fiction.
    book_genres = [
        "fantasy",
        "comics",
        "classics",
        "thrillers",
        "science fiction",
        "mythology",
        "humour",
        "romance",
        "graphic novels",
    ]
    book_markets = [
        ("Assam", "Assam", "state_sample", [6.8, 16.7, 3.2, 7.2, 2.7, 9.2, 9.8, 23.8, 20.6]),
        (
            "",
            "Other North-Eastern States",
            "combined_states",
            [5.6, 25.7, 8.9, 3.1, 13.5, 5.6, 2.3, 23.9, 11.4],
        ),
        (
            "Maharashtra",
            "Maharashtra",
            "state_sample",
            [30.6, 15.9, 15, 11.7, 2.7, 12.4, 4.3, 0.2, 7.1],
        ),
        ("Bihar", "Bihar", "state_sample", [23.8, 24.9, 4.7, 19.8, 7.8, 5.4, 3.2, 4.2, 6.3]),
        ("", "Rest of the States", "combined_states", [16.7, 17, 7.6, 18, 9.6, 12.1, 7.3, 5, 6.8]),
        ("India", "All India", "national", [18.5, 17.5, 8.4, 16.3, 8.2, 11.4, 6.5, 5.6, 7.5]),
    ]
    for state, geo, scope, values in book_markets:
        assert abs(sum(values) - 100) <= 0.21
        for genre, value in zip(book_genres, values, strict=True):
            add(
                "ncaer",
                state,
                geo,
                scope,
                genre,
                "book",
                "fiction_book_genre_preference_share",
                value,
                "percent",
                "",
                "Table 4.13; printed p.44; PDF p.68",
                "Reading preference; not film/anime; genre-question sample counts not supplied in this table.",
                "NYRS 2009",
            )

    # Published main survey: 1000 in India, NOT the 5000-person screening base.
    anime_genres = [
        "action",
        "fantasy",
        "comedy",
        "mystery",
        "romance",
        "horror",
        "sci-fi",
        "sports",
        "slice of life",
        "human drama",
        "historical",
    ]
    for genre, value in zip(
        anime_genres, [60, 47.7, 51.3, 55.9, 46.7, 44.6, 41.6, 40.1, 28.3, 34.2, 34.2], strict=True
    ):
        add(
            "hakuhodo_global",
            "India",
            "India arm of global anime fan survey",
            "country_arm",
            genre,
            "anime",
            "liked_anime_genre_share",
            value,
            "percent",
            1000,
            "PDF p.3 genre chart; methods p.5",
            "Potential anime users aged 16-39 include interested non-viewers; no states; chart labels retained; liking not watching.",
            "2025-08 to 2025-09",
        )

    pooled = {
        "action": 28.5,
        "supernatural / magic": 25.3,
        "comedy / slice of life": 10.2,
        "psychological": 9,
        "romance": 8,
        "historical": 6,
        "drama / tragedy": 6,
        "mecha / military": 3,
        "all of the above": 4,
    }
    assert sum(pooled.values()) == 100
    for genre, value in pooled.items():
        add(
            "south_anime",
            "",
            "Kerala; Telangana; Andhra Pradesh; Karnataka; Tamil Nadu (pooled)",
            "combined_states",
            genre,
            "anime",
            "preferred_watching_genre_share",
            value,
            "percent",
            310,
            "Viewership section, printed p.57; PDF p.5",
            "Purposive sample; no state-by-genre cross-tab; do not copy pooled rates into individual states; collection year unknown.",
        )

    preferences = {
        "comedy": [6, 1, 9, 26, 58],
        "action": [9, 19, 18, 28, 26],
        "romantic": [13, 9, 29, 23, 26],
        "patriotic": [9, 17, 26, 30, 18],
        "fiction": [9, 19, 24, 25, 23],
        "biopic": [11, 15, 23, 27, 24],
        "crime and mystery/thriller": [13, 6, 14, 15, 52],
        "adventure": [5, 7, 14, 31, 43],
        "animated movies": [17, 17, 19, 24, 23],
        "historical drama": [13, 17, 19, 25, 26],
        "suspense movies": [6, 6, 11, 20, 57],
        "horror movies": [25, 10, 14, 22, 29],
    }
    for genre, distribution in preferences.items():
        assert sum(distribution) == 100
        add(
            "ahmedabad",
            "Gujarat",
            "Ahmedabad city",
            "city_sample",
            genre,
            "film",
            "most_preferred_response_share",
            distribution[-1],
            "percent",
            100,
            "Table 3; printed p.70; PDF p.7",
            "5-point preference scale: only category 5 shown; non-probability city sample, not all Gujarat.",
            "2023-01 to 2023-03",
            sum(distribution[-2:]),
            "preferred_or_most_preferred_share_percent",
        )

    for venue, value in [("ott_or_digital_home", 76.2), ("cinema", 23.8)]:
        add(
            "kerala_venues",
            "Kerala",
            "Kerala study sample across 14 districts",
            "state_sample",
            "drama / comedy",
            "film",
            f"preferred_venue_{venue}_share",
            value,
            "percent",
            143,
            "Genre-Based Venue Preferences; printed p.138; PDF p.9",
            "Venue choice for a hypothetical mid-budget drama/comedy; not genre popularity; purposive sample; collection year unknown.",
        )
    add(
        "raebareli",
        "Uttar Pradesh",
        "Raebareli town and surrounding rural areas",
        "local_qualitative",
        "action / thriller",
        "film",
        "qualitative_preference_theme",
        "",
        "qualitative",
        80,
        "Findings, printed p.66; PDF p.4",
        "Qualitative finding; 80 is the study interview count, not genre count; no prevalence percentage.",
    )

    for genre, value in {
        "action / shonen": 68.4,
        "romance / shojo": 54.6,
        "psychological thriller": 41.3,
        "isekai": 38.9,
    }.items():
        add(
            "chennai_anime",
            "Tamil Nadu",
            "Chennai city, ages 15-30",
            "city_sample",
            genre,
            "anime",
            "reported_popular_anime_genre_share",
            value,
            "percent",
            412,
            "section 5.1, PDF p.7; fieldwork section 4.2, PDF p.5",
            "Purposive/snowball city sample; no national comparison; genre/demographic combined labels preserved; year is fieldwork end year.",
            "2025-10 to 2026-01",
        )

    delhi_cities = {
        "North Delhi",
        "South Delhi",
        "New Delhi",
        "West Delhi",
        "East Delhi",
        "Central Delhi",
    }
    responses = read_xlsx(RAW / "delhi_ncr.xlsx")[1:]
    delhi = [r for r in responses if r.get("F", "").strip() in delhi_cities]
    assert len(responses) == 220 and len(delhi) == 162
    counts = Counter(g.strip() for r in delhi for g in set(r["S"].split(",")) if g.strip())
    retained = [
        "Action",
        "Adventure",
        "Comedy",
        "Drama",
        "Fiction",
        "Horror",
        "Romance",
        "Thriller",
        "Documentary",
        "Musical",
        "Cartoon/Animation",
        "Live sports",
        "News and current affairs",
    ]
    for genre in retained:
        add(
            "delhi_ncr",
            "Delhi",
            "Delhi respondents within Delhi-NCR study",
            "local_sample",
            genre.lower(),
            "ott_unspecified_format",
            "preferred_ott_genre_share",
            round(100 * counts[genre] / len(delhi), 4),
            "percent",
            len(delhi),
            "Original Data Set.xlsx, columns F (region) and S (genres)",
            "Multiple selection; convenience/local sample; no India denominator or anime-specific question; year unknown.",
            reference=counts[genre],
            reference_measure="respondents_selecting_category",
        )

    barc_markets = [
        ("", "Punjab / Haryana / Chandigarh / Himachal Pradesh / Jammu & Kashmir", 6, 7),
        ("", "Uttar Pradesh / Uttarakhand", 8, 11),
        ("Rajasthan", "Rajasthan", 3, 3),
        ("Delhi", "Delhi", 3, 5),
        ("", "Assam / North East / Sikkim", 2, 4),
        ("Odisha", "Odisha", 3, 3),
        ("West Bengal", "West Bengal", 6, 5),
        ("", "Bihar / Jharkhand", 3, 3),
        ("", "Gujarat / Daman & Diu / Dadra & Nagar Haveli", 6, 5),
        ("", "Maharashtra / Goa", 14, 12),
        ("", "Madhya Pradesh / Chhattisgarh", 7, 6),
        ("Karnataka", "Karnataka", 9, 8),
        ("", "Andhra Pradesh / Telangana", 14, 14),
        ("Kerala", "Kerala", 4, 5),
        ("", "Tamil Nadu / Puducherry", 12, 9),
    ]
    for state, geo, total_tv, news in barc_markets:
        add(
            "barc",
            state,
            geo,
            "state_market" if state else "combined_state_market",
            "news",
            "television",
            "share_of_all_india_news_impressions",
            news,
            "percent",
            "",
            "Viewership by State Markets, PDF p.6",
            "Impressions share, not viewers watching news; rounded published values; markets not split; per-market panel n unavailable.",
            "2017 weeks 08-48",
            total_tv,
            "share_of_all_india_total_tv_impressions_percent",
        )

    rows.sort(key=lambda r: (r["source_id"], r["geography"], r["genre"], r["measurement"]))
    keys = [(r["source_id"], r["geography"], r["genre"], r["measurement"]) for r in rows]
    assert len(keys) == len(set(keys))
    for row in rows:
        if row["value"] != "":
            assert math.isfinite(row["value"])
            assert (-100 if row["unit"] == "percentage_points" else 0) <= row["value"] <= 100
        assert not row["sample_size"] or row["sample_size"] > 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    with OUT.open(newline="") as f:
        assert len(list(csv.DictReader(f))) == len(rows)
    sources = {}
    for sid, src in SOURCES.items():
        sources[sid] = dict(
            src,
            rows=sum(r["source_id"] == sid for r in rows),
            strict_viewing_index_eligible=False,
            sha256={
                name: hashlib.sha256((RAW / name).read_bytes()).hexdigest() for name in src["files"]
            },
        )
    audit = {
        "checked_on": "2026-10-24",
        "output": str(OUT.relative_to(ROOT)),
        "row_count": len(rows),
        "sources": sources,
        "original_teammate_sources_checked": 13,
        "no_exact_viewing_index_rows_obtainable": True,
        "source_counts": dict(Counter(r["source_id"] for r in rows)),
        "csv_rows": rows,
        "ahmedabad_original_five_point_counts": preferences,
        "delhi_original_category_counts": dict(sorted(counts.items())),
        "additional_search_checks": {
            "synthetic_ott_data": "https://github.com/shreyavijayjadhav3/ott-churn-analysis explicitly generates its users and histories; rejected.",
            "myanimelist": "Kaggle inventories and partially downloaded real profile CSV headers inspected (azathoth42/myanimelist, dbdmobile/myanimelist-dataset). These are self-selected global account profiles with free-text locations, not a state survey. Profile-only rows have no genre numerator. Downloads timed out; no partial records or ratings converted into survey rows.",
        },
    }
    AUDIT.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                "rows": len(rows),
                "source_counts": audit["source_counts"],
                "live_viewing_index_rows_added": 0,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
