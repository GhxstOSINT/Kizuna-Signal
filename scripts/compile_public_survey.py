"""Compile explicitly labelled exploratory affinity proxies from public source files.

Run with the project Python from the repository root. Original downloads live in
data/research/survey_sources (gitignored); see data/research/survey_compilation.md.
This does not estimate population viewing rates or fill missing states.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import sys
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import app.services.sources  # noqa: E402, F401  # Initialize registry before SurveyData.
from app.services.census import resolve_state  # noqa: E402
from app.services.survey import SurveyData  # noqa: E402

RAW = ROOT / "data/research/survey_sources"
OUT = ROOT / "data/research/proxies/public_affinity_exploratory.csv"
AUDIT = ROOT / "data/research/survey_compilation_audit.json"
FIELDS = ["state", "genre", "content_type", "index", "sample_size", "year", "source"]
NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
IR_URL = "https://arxiv.org/abs/1801.02203"
SEG_URL = "https://data.mendeley.com/datasets/vcp7w8t2kg/1"
DELHI_URL = "https://data.mendeley.com/datasets/fztpnhzhs6/1"
REVIEW_URL = "https://data.mendeley.com/datasets/6gcy6nhxj6/1"
MO_URL = "https://www.momagic.com/index.php/portfolio/55-of-indians-prefer-ott-platforms-vs-41-that-still-prefer-dth-momagic-survey/"
YG_URL = "https://yougov.com/articles/44094-seven-ten-urban-indians-claim-their-frequency-goin"
PA_URL = "https://www.parrotanalytics.com/insights/state-of-streaming-and-television-in-india-q3-2023-netflix-sony-tv-amazon-prime-video-disney-and-hbo/"


def sheets(path: Path) -> list[list[dict[str, str]]]:
    """Read cell values without executing formulas or requiring an Excel engine."""
    result = []
    with zipfile.ZipFile(path) as z:
        strings = []
        if "xl/sharedStrings.xml" in z.namelist():
            strings = [
                "".join(t.text or "" for t in item.findall(".//m:t", NS))
                for item in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si", NS)
            ]
        names = sorted(
            (n for n in z.namelist() if re.fullmatch(r"xl/worksheets/sheet\d+.xml", n)),
            key=lambda n: int(re.search(r"sheet(\d+)", n)[1]),
        )
        for name in names:
            rows = []
            for row in ET.fromstring(z.read(name)).findall(".//m:sheetData/m:row", NS):
                values = {}
                for cell in row.findall("m:c", NS):
                    v = cell.find("m:v", NS)
                    kind = cell.get("t")
                    if kind == "s" and v is not None:
                        value = strings[int(v.text)]
                    elif kind == "inlineStr":
                        value = "".join(t.text or "" for t in cell.findall(".//m:t", NS))
                    else:
                        value = v.text if v is not None else ""
                    values[re.sub(r"\d", "", cell.get("r"))] = value
                rows.append(values)
            result.append(rows)
    return result


def main() -> None:
    rows = []
    observations = []
    notes = []

    def add(state, genre, fmt, index, n, year, source):
        rows.append(
            dict(zip(FIELDS, [state, genre, fmt, round(index, 4), n, year, source], strict=True))
        )

    def national_preferences(values, n, year, url, label):
        # Each source keeps its own category set. Never pool raw percentages across surveys.
        baseline = mean(values.values())
        for genre, value in sorted(values.items()):
            add(
                "India",
                genre,
                "",
                100 * value / baseline,
                n,
                year,
                f"PREFERENCE_PROXY; {label}; {url}",
            )
            observations.append(
                {
                    "source": url,
                    "measurement": "preferred_genre",
                    "genre": genre,
                    "value": value,
                    "unit": "percent",
                    "base_n": n,
                    "mean_category_percent": baseline,
                }
            )

    # Public 2019 press release lists all four genre shares, summing to 100%.
    # Overall survey base is approximate; per-question base is not separately supplied.
    national_preferences(
        {"comedy": 45, "action": 23, "drama": 19, "horror": 13},
        "",
        2019,
        MO_URL,
        "2019; approximately 7500 overall; item base unknown",
    )

    # Download is aggregate tables, not the 343 individual respondent records.
    segment = sheets(RAW / "ott_segmentation.xlsx")[0]
    counts = {}
    section = ""
    for record in segment:
        section = record.get("A", "").strip() or section
        if section == "Preferred Genre" and record.get("C"):
            counts[record["B"].strip().lower()] = int(record["C"])
    assert sum(counts.values()) == 343 and len(counts) == 6
    national_preferences(
        {g: 100 * c / 343 for g, c in counts.items()},
        343,
        "",
        SEG_URL,
        "published 2024; survey year unreported; convenience sample",
    )

    # An observed like OR dislike is rating evidence. A zero is NOT a negative viewing response.
    with (RAW / "regional_users.csv").open(newline="") as f:
        users = {r["_id"]: r for r in csv.DictReader(f)}
    with (RAW / "regional_movies.csv").open(newline="") as f:
        movies = {r["movie_id"]: set(json.loads(r["genre"])) for r in csv.DictReader(f)}
    ratings = [
        json.loads(line)
        for line in (RAW / "regional_ratings.json").read_text().splitlines()
        if line.strip()
    ]
    genre_set = sorted({g for gs in movies.values() for g in gs})
    members = defaultdict(list)
    excluded_raters = Counter()
    for record in ratings:
        user = users.get(record["_id"])
        state = resolve_state(user.get("state", "")) if user else None
        if state is None:
            excluded_raters["missing or unresolved state"] += 1
            continue
        selected = [
            movie
            for movie, values in record["rated"].items()
            if movie in movies and any(str(v) in {"1", "-1"} for v in values)
        ]
        if not selected:
            excluded_raters["no nonzero movie ratings"] += 1
            continue
        genres = set().union(*(movies[movie] for movie in selected))
        members[state.name].append(genres)
    population = [gs for group in members.values() for gs in group]
    pooled = Counter(g for gs in population for g in gs)
    fractions = {g: pooled[g] / len(population) for g in genre_set}
    baseline = mean(fractions.values())
    ir_source = f"RATING_PROXY; 2017 release/2018 paper; Delhi-heavy respondent pool; {IR_URL}"
    for genre in genre_set:
        # Omit an unobserved genre rather than emitting zero as evidence of no viewing.
        if pooled[genre] == 0:
            continue
        canonical = genre.lower()
        add(
            "India",
            canonical,
            "film",
            100 * fractions[genre] / baseline,
            len(population),
            "",
            ir_source,
        )
        for state, group in sorted(members.items()):
            if len(group) < 150:
                continue
            count = sum(genre in gs for gs in group)
            if count == 0:
                continue
            add(
                state,
                canonical,
                "film",
                100 * (count / len(group)) / fractions[genre],
                len(group),
                "",
                ir_source,
            )
        observations.append(
            {
                "source": IR_URL,
                "measurement": "at_least_one_nonzero_rating_in_genre",
                "genre": canonical,
                "pooled_count": pooled[genre],
                "pooled_n": len(population),
                "state_counts": {
                    s: sum(genre in gs for gs in group) for s, group in sorted(members.items())
                },
                "state_bases": {s: len(group) for s, group in sorted(members.items())},
            }
        )
    notes.append(
        {
            "source": IR_URL,
            "downloaded_users": len(users),
            "downloaded_movies": len(movies),
            "rating_records": len(ratings),
            "eligible_raters": len(population),
            "excluded_raters": dict(excluded_raters),
            "states_below_150": {s: len(g) for s, g in sorted(members.items()) if len(g) < 150},
            "unobserved_genres_omitted": [g for g in genre_set if pooled[g] == 0],
        }
    )

    # Retain useful regional observations without inventing an all-India denominator.
    delhi = sheets(RAW / "delhi_ncr.xlsx")[0][1:]
    valid = [r for r in delhi if r.get("S", "").strip()]
    preferences = Counter(g.strip() for r in valid for g in set(r["S"].split(",")) if g.strip())
    observations.append(
        {
            "source": DELHI_URL,
            "measurement": "preferred_OTT_categories",
            "geography": "Delhi NCR (multiple states)",
            "respondents": len(delhi),
            "answered_n": len(valid),
            "category_counts": dict(sorted(preferences.items())),
            "regions": dict(sorted(Counter(r.get("F", "").strip() for r in delhi).items())),
            "excluded_from_csv": "No matching national baseline. Categories also mix genres, formats and origin.",
        }
    )
    reviewers = sheets(RAW / "movie_reviewers.xlsx")[0][2:]
    observations.append(
        {
            "source": REVIEW_URL,
            "measurement": "favorite_genre",
            "respondents": len(reviewers),
            "counts": dict(sorted(Counter(r.get("C", "").strip() for r in reviewers).items())),
            "excluded_from_csv": "No location fields and Indian respondent residence not established.",
        }
    )
    observations.append(
        {
            "source": YG_URL,
            "measurement": "preferred_film_genre",
            "year": 2022,
            "base_n": 1004,
            "population": "urban Indian respondents",
            "percentages": {"comedy": 67, "action": 54, "thriller": 51},
            "excluded_from_csv": "Article gives leading genres, not a confirmed full genre list for the national mean.",
        }
    )
    observations.append(
        {
            "source": PA_URL,
            "measurement": "series_demand_share",
            "period": "2023 Q3",
            "percentages": {"drama": 47.5, "animation": 7.2, "horror": 1.4},
            "excluded_from_csv": "Demand share is not viewer percentage; incomplete genre table in article text.",
        }
    )

    rows.sort(
        key=lambda r: (
            r["state"] != "India",
            r["state"],
            r["content_type"],
            r["genre"],
            r["source"],
        )
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8", newline="") as f:
        f.write(
            "# EXPLORATORY PROXIES: preference surveys and observed movie ratings, NOT representative viewing rates.\n"
        )
        f.write(
            "# Broad preference rows have blank content_type; film rating rows are not anime evidence.\n"
        )
        f.write(
            "# State ratios use the SAME rating sample pooled across India, dominated by Delhi; not population estimates.\n"
        )
        f.write(
            "# Blank year means collection year unreported; these sources include old data despite no automatic stale warning.\n"
        )
        f.write(
            "# Research archive only; do not load as a viewing survey. See ../survey_compilation.md.\n"
        )
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    parsed, errors = SurveyData._read(OUT)
    assert not errors, errors
    assert len(parsed) == len(rows)
    hashes = {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(RAW.iterdir())
        if p.is_file() and not p.name.startswith(".")
    }
    report = {
        "retrieved_on": "2026-10-24",
        "output": str(OUT.relative_to(ROOT)),
        "kind": "exploratory proxies, not a representative viewing survey",
        "row_count": len(rows),
        "rows_by_state": dict(Counter(r["state"] for r in rows)),
        "rows_by_measurement": dict(Counter(r["source"].split(";")[0] for r in rows)),
        "minimum_state_base": 150,
        "observations": observations,
        "notes": notes,
        "raw_sha256": hashes,
    }
    AUDIT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(
        json.dumps(
            {
                "rows": len(rows),
                "states": report["rows_by_state"],
                "measurements": report["rows_by_measurement"],
                "loader_errors": errors,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
