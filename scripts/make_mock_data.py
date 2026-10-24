"""Generate the mock backend JSON under data/mock/.

Run once (`python scripts/make_mock_data.py`); afterwards the JSON is the source
of truth and can be hand-edited. All numbers are illustrative mock values.
The unreleased titles are fictional; comparables are real historical titles
with made-up performance scores.
"""
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "mock"
GEO = ROOT / "data" / "geo" / "india_states.geojson"

# ----------------------------------------------------------------------------
# Global config
# ----------------------------------------------------------------------------
COMPONENTS = [
    {"id": "content_fit", "label": "Content Fit", "weight": 25, "primary": True},
    {"id": "demand_momentum", "label": "Demand Momentum", "weight": 25, "primary": True},
    {"id": "regional_opportunity", "label": "Regional Opportunity", "weight": 20, "primary": True},
    {"id": "engagement_quality", "label": "Engagement Quality", "weight": 15, "primary": True},
    {"id": "comparable_performance", "label": "Comparable Performance", "weight": 15, "primary": True},
    {"id": "localization_readiness", "label": "Localization Readiness", "weight": 0, "primary": False},
]

CONFIDENCE_FACTORS = [
    {"id": "data_completeness", "label": "Data completeness", "weight": 0.20},
    {"id": "source_agreement", "label": "Source agreement", "weight": 0.25},
    {"id": "comparable_quality", "label": "Comparable quality", "weight": 0.20},
    {"id": "regional_evidence", "label": "Regional evidence", "weight": 0.20},
    {"id": "data_freshness", "label": "Data freshness", "weight": 0.15},
]

LEVERS = {
    "localization": {
        "label": "Localization",
        "options": {
            "subs_hindi": {"label": "Hindi subtitles", "score": 0, "confidence": 0, "cost": 0, "reach": 0},
            "dub_hindi_subs_regional": {"label": "Hindi dub + Tamil/Telugu subtitles", "score": 4, "confidence": -1, "cost": 1, "reach": 2},
            "multilingual_dub": {"label": "Multilingual dub (Hindi, Tamil, Telugu)", "score": 6, "confidence": -3, "cost": 2.5, "reach": 3},
            "english_subs_only": {"label": "English subtitles only", "score": -5, "confidence": 0, "cost": -0.5, "reach": -1},
        },
    },
    "distribution": {
        "label": "Distribution",
        "options": {
            "ott": {"label": "OTT", "score": 0, "confidence": 0, "cost": 0, "reach": 0},
            "theatrical": {"label": "Theatrical", "score": -3, "confidence": -2, "cost": 2, "reach": 0},
            "tv": {"label": "Television", "score": -5, "confidence": -1, "cost": 1.5, "reach": 1},
            "digital_first": {"label": "Digital-first", "score": 1, "confidence": 0, "cost": 0, "reach": 0},
            "hybrid": {"label": "Hybrid (OTT + theatrical)", "score": 2, "confidence": -1, "cost": 2, "reach": 1},
        },
    },
    "geography": {
        "label": "Geography",
        "options": {
            "national": {"label": "National launch", "score": 0, "confidence": 0, "cost": 0, "reach": 0},
            "regional_first": {"label": "Regional-first rollout", "score": 1, "confidence": 1, "cost": -0.5, "reach": -1},
            "selected_states": {"label": "Selected-state focus", "score": 1, "confidence": 2, "cost": -1, "reach": -2},
        },
    },
    "release_window": {
        "label": "Release window",
        "options": {
            "mar_apr": {"label": "March-April", "score": 0, "confidence": 0, "cost": 0, "reach": 0},
            "jun_jul": {"label": "June-July", "score": -1, "confidence": 0, "cost": 0, "reach": 0},
            "oct_nov_festive": {"label": "October-November (festive season)", "score": 2, "confidence": -1, "cost": 0.5, "reach": 0},
            "jan_feb": {"label": "January-February", "score": -1, "confidence": 0, "cost": 0, "reach": 0},
        },
    },
    "marketing_budget": {
        "label": "Marketing budget",
        "options": {
            "low": {"label": "Low", "score": -3, "confidence": 0, "cost": -1, "reach": -1},
            "medium": {"label": "Medium", "score": 0, "confidence": 0, "cost": 0, "reach": 0},
            "high": {"label": "High", "score": 3, "confidence": -1, "cost": 1.5, "reach": 1},
        },
    },
}

# state -> (local language, addressable-market index, base evidence strength)
STATES = {
    "Andaman & Nicobar": ("Hindi", 6, 18),
    "Andhra Pradesh": ("Telugu", 66, 66),
    "Arunachal Pradesh": ("English", 10, 22),
    "Assam": ("Assamese", 45, 44),
    "Bihar": ("Hindi", 70, 52),
    "Chandigarh": ("Punjabi", 34, 54),
    "Chhattisgarh": ("Hindi", 42, 44),
    "Dadra and Nagar Haveli and Daman and Diu": ("Gujarati", 14, 28),
    "Delhi": ("Hindi", 88, 86),
    "Goa": ("English", 30, 56),
    "Gujarat": ("Gujarati", 75, 72),
    "Haryana": ("Hindi", 60, 64),
    "Himachal Pradesh": ("Hindi", 28, 42),
    "Jammu & Kashmir": ("Hindi", 32, 36),
    "Jharkhand": ("Hindi", 48, 46),
    "Karnataka": ("Kannada", 85, 86),
    "Kerala": ("Malayalam", 62, 74),
    "Ladakh": ("Hindi", 5, 16),
    "Lakshadweep": ("Malayalam", 3, 10),
    "Madhya Pradesh": ("Hindi", 64, 58),
    "Maharashtra": ("Marathi", 95, 88),
    "Manipur": ("English", 16, 26),
    "Meghalaya": ("English", 16, 28),
    "Mizoram": ("English", 10, 26),
    "Nagaland": ("English", 12, 24),
    "Odisha": ("Odia", 50, 48),
    "Puducherry": ("Tamil", 24, 45),
    "Punjab": ("Punjabi", 55, 60),
    "Rajasthan": ("Hindi", 68, 62),
    "Sikkim": ("English", 8, 30),
    "Tamil Nadu": ("Tamil", 82, 85),
    "Telangana": ("Telugu", 76, 82),
    "Tripura": ("Bengali", 18, 30),
    "Uttar Pradesh": ("Hindi", 90, 78),
    "Uttarakhand": ("Hindi", 36, 50),
    "West Bengal": ("Bengali", 78, 74),
}

LANGUAGES = ["Hindi", "English", "Tamil", "Telugu", "Kannada", "Malayalam",
             "Bengali", "Marathi", "Gujarati", "Punjabi", "Odia", "Assamese"]

CONFIG = {
    "scoring_config_version": "sc-2026.10-a",
    "components": COMPONENTS,
    "confidence_factors": CONFIDENCE_FACTORS,
    "interval": {"base": 2, "slope": 0.22},
    "decision": {
        "insufficient_below_confidence": 50,
        "insufficient_label": "Insufficient evidence",
        "bands": [
            {"min_score": 75, "label": "Strong opportunity"},
            {"min_score": 65, "label": "Promising opportunity"},
            {"min_score": 50, "label": "Test before investing"},
            {"min_score": 0, "label": "Limited opportunity"},
        ],
    },
    "regional": {"suppress_below_evidence": 40, "limited_below_evidence": 55, "top_n": 5},
    "min_comparables": 2,
    "languages": LANGUAGES,
    "states": {s: {"language": v[0], "market_index": v[1]} for s, v in STATES.items()},
    "levers": LEVERS,
    "scenario_objective": {"score": 1.0, "confidence": 0.3, "cost": -1.5},
    "cost_levels": [{"below": 1.5, "label": "Low"}, {"below": 3.5, "label": "Medium"}, {"below": 999, "label": "High"}],
    "reach_levels": [{"below": 2, "label": "Limited"}, {"below": 4, "label": "Moderate"},
                     {"below": 6, "label": "High"}, {"below": 999, "label": "Very high"}],
    "pipeline_stages": [
        "Title metadata validated",
        "Public demand signals collected",
        "Content DNA generated",
        "Comparable titles identified",
        "Calculating regional opportunity",
        "Generating launch recommendation",
    ],
    "content_formats": ["Anime series", "Animated film", "Live-action film",
                        "Television series", "Manga adaptation", "Character IP"],
}

# ----------------------------------------------------------------------------
# Sources (shared shape, per-title status overrides)
# ----------------------------------------------------------------------------
SOURCE_DEFS = [
    {"id": "anilist", "name": "AniList", "feeds": ["content_fit", "comparable_performance"],
     "caveat": "Popularity is a historical outcome; post-release data is blocked for the predicted title.",
     "effect_if_disabled": {"components": {"content_fit": -6, "comparable_performance": -3},
                            "confidence_factors": {"data_completeness": -10, "comparable_quality": -4}}},
    {"id": "google_trends", "name": "Google Trends", "feeds": ["demand_momentum", "regional_opportunity"],
     "caveat": "Values are relative interest (0-100 normalised), not search volume.",
     "effect_if_disabled": {"components": {"demand_momentum": -9, "regional_opportunity": -4},
                            "confidence_factors": {"data_completeness": -12, "data_freshness": -4, "source_agreement": -3}}},
    {"id": "youtube", "name": "YouTube", "feeds": ["engagement_quality", "demand_momentum"],
     "caveat": "Trailer statistics are global, not India-only.",
     "effect_if_disabled": {"components": {"engagement_quality": -10, "demand_momentum": -2},
                            "confidence_factors": {"data_completeness": -8, "source_agreement": 2}}},
    {"id": "wikimedia", "name": "Wikimedia", "feeds": ["demand_momentum"],
     "caveat": "Page views indicate curiosity, not consumption.",
     "effect_if_disabled": {"components": {"demand_momentum": -3},
                            "confidence_factors": {"data_completeness": -5, "source_agreement": -1}}},
    {"id": "census", "name": "Census India", "feeds": ["regional_opportunity"],
     "caveat": "Demographic table year is older than current behaviour.",
     "effect_if_disabled": {"components": {"regional_opportunity": -5},
                            "confidence_factors": {"regional_evidence": -8, "data_completeness": -3}}},
]


def sources_for(status_overrides):
    out = []
    for d in SOURCE_DEFS:
        ov = status_overrides.get(d["id"], {})
        s = {
            "id": d["id"], "name": d["name"], "status": "available", "mode": "live",
            "last_collected": "2026-10-22T14:02:00+05:30", "quota": None, "note": "",
            "caveat": d["caveat"], "feeds": d["feeds"], "toggleable": True,
            "effect_if_disabled": d["effect_if_disabled"],
        }
        s.update(ov)
        if s["status"] != "available":
            s["toggleable"] = False
        out.append(s)
    out.append({
        "id": "datameet", "name": "DataMeet (boundaries)", "status": "available", "mode": "cached",
        "last_collected": "2026-09-30T09:00:00+05:30", "quota": None, "note": "Static boundary file.",
        "caveat": "State-name mapping validated against the boundary file.", "feeds": [],
        "toggleable": False, "effect_if_disabled": {"components": {}, "confidence_factors": {}},
    })
    out.append({
        "id": "partner_csv", "name": "Partner data", "status": "not_connected", "mode": "none",
        "last_collected": None, "quota": None, "note": "Coming later (pilot phase).",
        "caveat": "Licensing, spend and outcome data require a contracted schema.", "feeds": [],
        "toggleable": False, "effect_if_disabled": {"components": {}, "confidence_factors": {}},
    })
    return out


# ----------------------------------------------------------------------------
# Titles
# ----------------------------------------------------------------------------
TITLES = {}

TITLES["shadow_bloom"] = {
    "meta": {
        "title": "Shadow Bloom", "title_jp": "シャドウブルーム", "english_title": "Shadow Bloom",
        "synopsis": "A teenage spirit guardian must protect a fading mountain shrine from the shadows "
                    "that feed on forgotten promises, while learning what friendship costs.",
        "format": "Anime series", "genres": ["Fantasy", "Action", "Coming of Age"],
        "age_rating": "13+", "release_period": "March 2027", "source_material": "Original",
        "episodes": 12, "studio": "Hikari Studio", "franchise_status": "New IP",
        "themes": ["Friendship", "Folklore", "Sacrifice"], "intended_audience": "Youth and anime fans",
        "target_platform": "OTT", "target_languages": ["Hindi", "Tamil", "Telugu"],
        "target_states": [], "budget_band": "Medium", "director": "A. Mizuno", "cast": [],
        "accent": "#3B3F9E", "trailer_url": "https://www.youtube.com/watch?v=mock-shadow-bloom",
        "completeness": 91,
    },
    "status": "complete", "last_analysis": "2026-10-22",
    "components": {"content_fit": 83, "demand_momentum": 76, "regional_opportunity": 82,
                   "engagement_quality": 71, "comparable_performance": 77, "localization_readiness": 73},
    "factors": {"data_completeness": 88, "source_agreement": 82, "comparable_quality": 84,
                "regional_evidence": 74, "data_freshness": 85},
    "expect": (78, 82),
    "source_overrides": {"google_trends": {"mode": "cached", "note": "Cached export used (Oct 20)."}},
    "state_off": 36, "evidence_adj": 0,
    "top_states": {"Maharashtra": 86, "Karnataka": 82, "Delhi": 80, "Tamil Nadu": 78, "Telangana": 76},
    "dub_languages": ["Hindi", "Tamil", "Telugu"], "platform": "OTT", "theatrical_metros": False,
    "hook": "Strong fantasy-anime search growth",
    "language_affinity": {"Hindi": (88, 86), "English": (70, 80), "Tamil": (78, 80), "Telugu": (74, 76),
                          "Kannada": (66, 66), "Malayalam": (58, 60), "Bengali": (48, 38),
                          "Marathi": (62, 64), "Gujarati": (50, 52), "Punjabi": (46, 48),
                          "Odia": (34, 30), "Assamese": (30, 26)},
    "content_dna": {
        "genres": [("Fantasy", 0.9), ("Action", 0.8), ("Coming of Age", 0.6)],
        "themes": [("Friendship", 0.85), ("Folklore", 0.7), ("Sacrifice", 0.55)],
        "archetypes": ["Reluctant guardian", "Found family", "Ancient curse"],
        "audience_fit": {"Youth 16-30": 88, "Fandom intensity": 74, "Mainstream crossover": 58,
                         "Family suitability": 52, "Premium-market suitability": 70},
        "sensitivity_flags": ["Mild supernatural violence", "Religious/shrine imagery (check regional sensitivity)"],
    },
    "drivers": [
        ("Strong fantasy-action affinity", 8.2, "content_fit", ["anilist", "google_trends"],
         "Fantasy-action titles over-index on Indian anime streaming interest."),
        ("Growing Indian search momentum", 6.7, "demand_momentum", ["google_trends", "wikimedia"],
         "Relative search interest for the franchise terms rose over the last 12 weeks."),
        ("Strong performance of similar titles", 5.4, "comparable_performance", ["anilist"],
         "Five closest comparables show high Indian demand."),
        ("High youth-audience fit", 4.1, "content_fit", ["census", "anilist"],
         "Target audience aligns with the large 16-30 urban segment."),
        ("Existing interest in the source material", 3.8, "demand_momentum", ["wikimedia", "youtube"],
         "Studio and folklore themes show sustained information-seeking."),
        ("Limited awareness outside major cities", -4.8, "regional_opportunity", ["google_trends", "census"],
         "Tier-2 and smaller markets show sparse query data."),
        ("Weak Bengali-language evidence", -2.9, "regional_opportunity", ["google_trends", "census"],
         "Few Bengali-language signals; West Bengal interval is wider."),
        ("High dubbing requirement", -2.3, "content_fit", ["anilist"],
         "Multilingual dubbing raises cost and delays regional reach."),
        ("Limited franchise recognition", -1.7, "demand_momentum", ["wikimedia", "anilist"],
         "New IP with no existing manga or game base."),
    ],
    "warnings": [
        ("youtube_global", "warning", "YouTube statistics are global, not India-only."),
        ("regional_sparse", "warning", "Regional evidence is limited for Assam and Odisha."),
        ("trends_relative", "info", "Google Trends values represent relative interest."),
        ("revenue_missing", "info", "Revenue data was not available."),
    ],
    "comparables": [
        ("jujutsu_kaisen", "Jujutsu Kaisen", 2020, "Anime series", 0.88, "High", "Strong", "Strong", "Exact", 84,
         "Supernatural action, youth audience, ensemble characters and urban fantasy."),
        ("demon_slayer", "Demon Slayer", 2019, "Anime series", 0.84, "High", "Strong", "Strong", "Exact", 88,
         "Folklore-driven fantasy action with a sibling bond at its core."),
        ("solo_leveling", "Solo Leveling", 2024, "Anime series", 0.79, "High", "Strong", "Moderate", "Exact", 80,
         "Dark fantasy action with a power-growth arc popular with gaming audiences."),
        ("frieren", "Frieren: Beyond Journey's End", 2023, "Anime series", 0.74, "Medium", "Moderate", "Strong", "Exact", 70,
         "Reflective fantasy about relationships and time; strong critical reception."),
        ("chainsaw_man", "Chainsaw Man", 2022, "Anime series", 0.72, "Medium", "Moderate", "Strong", "Exact", 74,
         "Dark action with a strong youth fandom; edgier tone."),
        ("naruto", "Naruto", 2002, "Anime series", 0.70, "High", "Moderate", "Strong", "Exact", 91,
         "Long-running coming-of-age action with deep Indian TV fandom."),
        ("blue_exorcist", "Blue Exorcist", 2011, "Anime series", 0.68, "Medium", "Strong", "Moderate", "Exact", 58,
         "Supernatural action with a reluctant hero; older release, lower reach."),
        ("dororo", "Dororo", 2019, "Anime series", 0.62, "Low", "Moderate", "Moderate", "Exact", 52,
         "Folklore-based dark fantasy; niche appeal outside fandom."),
    ],
    "comp_sets": {
        "expected": ["jujutsu_kaisen", "demon_slayer", "solo_leveling", "frieren", "chainsaw_man"],
        "optimistic": ["demon_slayer", "naruto", "jujutsu_kaisen", "solo_leveling", "chainsaw_man"],
        "conservative": ["frieren", "blue_exorcist", "dororo", "chainsaw_man", "solo_leveling"],
    },
    "base_levers": {"localization": "subs_hindi", "distribution": "ott", "geography": "national",
                    "release_window": "mar_apr", "marketing_budget": "medium"},
    "base_cost": 1.0, "base_reach": 3.0,
    "presets": [
        {"id": "regional_dub", "label": "Hindi dub + regional-first",
         "levers": {"localization": "dub_hindi_subs_regional", "distribution": "ott", "geography": "regional_first",
                    "release_window": "mar_apr", "marketing_budget": "medium"},
         "summary": "OTT release with a Hindi dub and Tamil/Telugu subtitles, rolled out region by region."},
        {"id": "full_multilingual", "label": "Multilingual dub + high marketing",
         "levers": {"localization": "multilingual_dub", "distribution": "ott", "geography": "national",
                    "release_window": "mar_apr", "marketing_budget": "high"},
         "summary": "Full Hindi, Tamil and Telugu dubs with a high national campaign budget."},
    ],
    "recommendation": {
        "headline": "Proceed with a controlled regional-first multilingual OTT launch.",
        "platform": "OTT-first release",
        "priority_markets": ["Maharashtra", "Karnataka", "Delhi", "Tamil Nadu", "Telangana"],
        "localization": ["Hindi dub", "Tamil and Telugu subtitles", "English subtitles retained"],
        "target_audience": ["Urban viewers aged 16-30", "Fantasy and action anime fans",
                            "Existing manga and gaming communities"],
        "launch_window": "March-April 2027",
        "positioning": "Character-driven supernatural action with emotion, friendship and folklore-adjacent themes.",
        "campaign": ["Launch a subtitled teaser first",
                     "Test Hindi and Tamil trailer variants",
                     "Partner with anime and gaming creators",
                     "Run fan screenings in Mumbai, Bengaluru and Delhi",
                     "Increase campaign investment only after engagement validation"],
        "risks": [("Limited awareness outside major cities", "Start with metro-focused creator partnerships and expand on validated engagement."),
                  ("Weak Bengali-language evidence", "Treat West Bengal as a later-phase market; collect Bengali trailer feedback first."),
                  ("High dubbing cost", "Dub Hindi first; keep Tamil and Telugu as subtitles until demand is proven.")],
        "items": [
            ("Localization", "Release with a Hindi dub and Tamil/Telugu subtitles.",
             "Expected score uplift in Maharashtra, Tamil Nadu and Telangana outweighs the added localization cost.",
             ["Scenario lab: regional dub vs. Hindi subtitles", "Language affinity: Hindi 88, Tamil 78, Telugu 74"], 80,
             "Dubbing cost may not be recovered if engagement is below forecast."),
            ("Platform", "Launch OTT-first.",
             "Every top-five state prefers OTT; theatrical shows a lower score and higher cost.",
             ["Distribution lever: theatrical -3 score, +2 cost"], 84,
             "OTT platform commitments are not yet contracted."),
            ("Timing", "Target March-April 2027.",
             "Seasonality is neutral and avoids examination periods.",
             ["Release-window lever"], 70,
             "Seasonality assumptions are illustrative."),
        ],
    },
}

TITLES["hollow_tide"] = {
    "meta": {
        "title": "Hollow Tide", "title_jp": "ホロウ・タイド", "english_title": "Hollow Tide",
        "synopsis": "After a coastal town loses every memory of one night, a young archivist pieces together "
                    "what the tide took, and who is still pulling it back.",
        "format": "Animated film", "genres": ["Mystery", "Psychological", "Drama"],
        "age_rating": "16+", "release_period": "June 2027", "source_material": "Original",
        "episodes": None, "duration_minutes": 108, "studio": "Nami Pictures", "franchise_status": "New IP",
        "themes": ["Memory", "Grief", "Community"], "intended_audience": "Adult arthouse and anime audiences",
        "target_platform": "Theatrical", "target_languages": ["Hindi", "English"],
        "target_states": [], "budget_band": "High", "director": "K. Aoyama", "cast": [],
        "accent": "#1F6F6B", "trailer_url": "",
        "completeness": 62,
    },
    "status": "complete", "last_analysis": "2026-10-21",
    "components": {"content_fit": 89, "demand_momentum": 82, "regional_opportunity": 79,
                   "engagement_quality": 70, "comparable_performance": 78, "localization_readiness": 61},
    "factors": {"data_completeness": 45, "source_agreement": 40, "comparable_quality": 42,
                "regional_evidence": 38, "data_freshness": 52},
    "expect": (81, 43),
    "source_overrides": {
        "google_trends": {"note": "Sparse: the title term is ambiguous (common English phrase)."},
        "wikimedia": {"note": "No dedicated page yet."},
        "youtube": {"note": "No trailer published; no engagement data."},
        "anilist": {"note": "Limited metadata."},
    },
    "state_off": 37, "evidence_adj": -14,
    "top_states": {"Maharashtra": 84, "Delhi": 83, "Karnataka": 80, "West Bengal": 78, "Tamil Nadu": 76},
    "dub_languages": ["Hindi", "English"], "platform": "Theatrical (limited)", "theatrical_metros": True,
    "hook": "Strong appetite for mystery and drama animation in arthouse circuits",
    "language_affinity": {"Hindi": (80, 44), "English": (82, 52), "Tamil": (64, 40), "Telugu": (60, 36),
                          "Kannada": (66, 42), "Malayalam": (62, 38), "Bengali": (72, 40),
                          "Marathi": (64, 38), "Gujarati": (48, 30), "Punjabi": (42, 28),
                          "Odia": (30, 20), "Assamese": (26, 18)},
    "content_dna": {
        "genres": [("Mystery", 0.9), ("Psychological", 0.8), ("Drama", 0.7)],
        "themes": [("Memory", 0.9), ("Grief", 0.7), ("Community", 0.5)],
        "archetypes": ["Unreliable witness", "Small-town secret", "Quiet investigator"],
        "audience_fit": {"Youth 16-30": 66, "Fandom intensity": 52, "Mainstream crossover": 44,
                         "Family suitability": 22, "Premium-market suitability": 82},
        "sensitivity_flags": ["Mature psychological themes", "Grief and loss"],
    },
    "drivers": [
        ("Strong mystery-drama affinity", 8.9, "content_fit", ["anilist"],
         "Mystery and psychological films over-index with urban arthouse audiences."),
        ("Comparable film performance", 5.2, "comparable_performance", ["anilist"],
         "Similar animated films performed strongly in metros."),
        ("Premium-market suitability", 3.6, "regional_opportunity", ["census"],
         "Matches a high-spending urban segment."),
        ("Sparse search evidence (ambiguous title)", -6.4, "demand_momentum", ["google_trends"],
         "The title term mixes with unrelated queries; demand signals are unreliable."),
        ("No trailer engagement data", -5.1, "engagement_quality", ["youtube"],
         "No trailer is public, so engagement cannot be estimated."),
        ("Few direct comparables", -3.3, "comparable_performance", ["anilist"],
         "Few titles match the mystery-drama film profile."),
    ],
    "warnings": [
        ("low_confidence", "critical", "Evidence is too thin for a high-investment decision."),
        ("trends_ambiguous", "warning", "Google Trends data is sparse because the title term is ambiguous."),
        ("no_trailer", "warning", "No trailer is available, so engagement is unmeasured."),
        ("regional_sparse", "warning", "Most states have insufficient evidence; only large metros are ranked."),
    ],
    "comparables": [
        ("your_name", "Your Name", 2016, "Animated film", 0.76, "High", "Moderate", "Strong", "Exact", 86,
         "Mystery-tinged drama with a memory theme and broad urban appeal."),
        ("a_silent_voice", "A Silent Voice", 2016, "Animated film", 0.74, "Medium", "Strong", "Moderate", "Exact", 66,
         "Emotional drama about guilt and redemption."),
        ("perfect_blue", "Perfect Blue", 1997, "Animated film", 0.70, "Medium", "Strong", "Moderate", "Exact", 58,
         "Psychological thriller with a cult following."),
        ("paprika", "Paprika", 2006, "Animated film", 0.68, "Medium", "Strong", "Moderate", "Exact", 60,
         "Dreamlike mystery; mostly known through festivals."),
        ("weathering_with_you", "Weathering With You", 2019, "Animated film", 0.64, "High", "Moderate", "Strong", "Exact", 78,
         "Urban teenage drama with a fantastical element."),
        ("suzume", "Suzume", 2022, "Animated film", 0.60, "High", "Weak", "Strong", "Exact", 82,
         "Large-scale film; much bigger marketing than Hollow Tide."),
        ("garden_of_words", "The Garden of Words", 2013, "Animated film", 0.58, "Low", "Moderate", "Moderate", "Exact", 40,
         "Quiet romance; limited reach."),
        ("spirited_away", "Spirited Away", 2001, "Animated film", 0.55, "High", "Weak", "Moderate", "Exact", 90,
         "Landmark film, not a close genre match."),
    ],
    "comp_sets": {
        "expected": ["your_name", "a_silent_voice", "perfect_blue", "paprika", "weathering_with_you"],
        "optimistic": ["your_name", "suzume", "spirited_away", "weathering_with_you", "a_silent_voice"],
        "conservative": ["perfect_blue", "paprika", "garden_of_words", "a_silent_voice", "your_name"],
    },
    "base_levers": {"localization": "subs_hindi", "distribution": "theatrical", "geography": "selected_states",
                    "release_window": "jun_jul", "marketing_budget": "medium"},
    "base_cost": 3.0, "base_reach": 1.0,
    "presets": [
        {"id": "digital_first", "label": "Digital-first test release",
         "levers": {"localization": "subs_hindi", "distribution": "digital_first", "geography": "selected_states",
                    "release_window": "jun_jul", "marketing_budget": "low"},
         "summary": "Test demand on a digital platform with a small budget before any theatrical commitment."},
        {"id": "hybrid_metro", "label": "Hybrid metro release",
         "levers": {"localization": "dub_hindi_subs_regional", "distribution": "hybrid", "geography": "selected_states",
                    "release_window": "oct_nov_festive", "marketing_budget": "medium"},
         "summary": "Limited theatrical in metros plus OTT, timed to the festive season."},
    ],
    "recommendation": {
        "headline": "Do not commit launch investment yet. Collect more evidence first.",
        "platform": "Digital-first test (no theatrical commitment)",
        "priority_markets": ["Maharashtra", "Delhi", "Karnataka"],
        "localization": ["Hindi subtitles", "English subtitles retained"],
        "target_audience": ["Urban adult animation and arthouse viewers"],
        "launch_window": "Decide after the evidence check (earliest June 2027)",
        "positioning": "Quiet, character-led mystery for viewers of emotional adult animation.",
        "campaign": ["Publish a teaser with a distinctive search keyword",
                     "Run a festival or screening test in Mumbai and Delhi",
                     "Re-run the analysis once trailer and search data exist"],
        "risks": [("Ambiguous title term", "Add a distinctive keyword or alternate title to campaign materials."),
                  ("No trailer data", "Publish a teaser and wait two to four weeks for engagement data."),
                  ("Overspending on theatrical", "Defer theatrical spend until confidence reaches at least 60%.")],
        "items": [
            ("Evidence", "Gather trailer, search and comparable data before committing budget.",
             "The potential score is high, but confidence is only 43%.",
             ["Confidence factors: all below 55"], 43,
             "Waiting delays a festive-season window."),
            ("Platform", "Test digitally before theatrical release.",
             "Theatrical shows a lower score and higher cost than digital-first.",
             ["Distribution lever"], 45,
             "A digital test may under-represent arthouse demand."),
        ],
    },
}

TITLES["kitsune_circuit"] = {
    "meta": {
        "title": "Kitsune Circuit", "title_jp": "キツネ・サーキット", "english_title": "Kitsune Circuit",
        "synopsis": "A struggling robotics student discovers her late grandfather's workshop hides a fox spirit "
                    "bound to a prototype racer, and an underground league that wants both.",
        "format": "Anime series", "genres": ["Sci-Fi", "Comedy", "Sports"],
        "age_rating": "10+", "release_period": "November 2027", "source_material": "Manga",
        "episodes": 24, "studio": "Kumo Animation", "franchise_status": "Manga adaptation",
        "themes": ["Family", "Technology", "Competition"], "intended_audience": "Youth and family",
        "target_platform": "OTT", "target_languages": ["Hindi", "Telugu"],
        "target_states": [], "budget_band": "Low", "director": "R. Takeda", "cast": [],
        "accent": "#B5452F", "trailer_url": "https://www.youtube.com/watch?v=mock-kitsune-circuit",
        "completeness": 84,
    },
    "status": "partial", "last_analysis": "2026-10-23",
    "components": {"content_fit": 70, "demand_momentum": 64, "regional_opportunity": 68,
                   "engagement_quality": 58, "comparable_performance": 66, "localization_readiness": 62},
    "factors": {"data_completeness": 70, "source_agreement": 66, "comparable_quality": 62,
                "regional_evidence": 58, "data_freshness": 66},
    "expect": (66, 64),
    "source_overrides": {"youtube": {"status": "unavailable", "mode": "none",
                                     "note": "Quota reached; refresh deferred.", "last_collected": None}},
    "state_off": 32, "evidence_adj": -4,
    "top_states": {"Delhi": 74, "Maharashtra": 72, "Karnataka": 71, "Telangana": 69, "Uttar Pradesh": 66},
    "dub_languages": ["Hindi", "Telugu"], "platform": "OTT", "theatrical_metros": False,
    "hook": "Family-friendly sports-comedy with strong Hindi dub potential",
    "language_affinity": {"Hindi": (80, 70), "English": (62, 66), "Tamil": (58, 56), "Telugu": (72, 64),
                          "Kannada": (60, 58), "Malayalam": (52, 52), "Bengali": (50, 46),
                          "Marathi": (58, 56), "Gujarati": (48, 50), "Punjabi": (46, 46),
                          "Odia": (36, 32), "Assamese": (32, 28)},
    "content_dna": {
        "genres": [("Sci-Fi", 0.7), ("Comedy", 0.85), ("Sports", 0.65)],
        "themes": [("Family", 0.8), ("Technology", 0.7), ("Competition", 0.6)],
        "archetypes": ["Underdog engineer", "Spirit companion", "Underground league"],
        "audience_fit": {"Youth 16-30": 64, "Fandom intensity": 56, "Mainstream crossover": 70,
                         "Family suitability": 82, "Premium-market suitability": 48},
        "sensitivity_flags": ["Competitive/gambling-adjacent league (check platform policy)"],
    },
    "drivers": [
        ("Family-friendly comedy affinity", 7.1, "content_fit", ["anilist", "google_trends"],
         "Comedy anime with family appeal travels well across Hindi-belt audiences."),
        ("Strong Hindi dub potential", 5.0, "regional_opportunity", ["census", "google_trends"],
         "Large Hindi-speaking addressable market."),
        ("Comparable performance", 4.2, "comparable_performance", ["anilist"],
         "Similar sports-comedy titles performed above average."),
        ("Manga source material interest", 3.1, "demand_momentum", ["wikimedia"],
         "Manga page views are growing steadily."),
        ("No trailer engagement data (YouTube unavailable)", -5.7, "engagement_quality", ["youtube"],
         "Engagement is estimated from other signals only."),
        ("Weak regional evidence outside metros", -3.4, "regional_opportunity", ["google_trends", "census"],
         "Sparse regional query data."),
        ("Low budget limits campaign reach", -2.2, "demand_momentum", ["google_trends"],
         "Low marketing band restricts awareness building."),
    ],
    "warnings": [
        ("youtube_unavailable", "warning", "YouTube data is temporarily unavailable. The analysis continued with the remaining sources."),
        ("partial_analysis", "info", "Four of five public sources were available. Confidence has been adjusted."),
        ("regional_sparse", "warning", "Regional evidence is limited for several north-eastern states."),
    ],
    "comparables": [
        ("spy_family", "Spy x Family", 2022, "Anime series", 0.78, "High", "Moderate", "Strong", "Exact", 82,
         "Family-centred comedy with broad crossover appeal."),
        ("dr_stone", "Dr. Stone", 2019, "Anime series", 0.75, "Medium", "Strong", "Strong", "Exact", 72,
         "Science-driven adventure comedy with youth and family fans."),
        ("kaguya_sama", "Kaguya-sama: Love Is War", 2019, "Anime series", 0.68, "Medium", "Moderate", "Strong", "Exact", 66,
         "Competitive comedy built on rivalry."),
        ("one_punch_man", "One-Punch Man", 2015, "Anime series", 0.66, "High", "Moderate", "Strong", "Exact", 78,
         "Parody action comedy with a large global base."),
        ("mob_psycho", "Mob Psycho 100", 2016, "Anime series", 0.62, "Medium", "Moderate", "Moderate", "Exact", 64,
         "Supernatural comedy with a youth following."),
        ("dandadan", "Dandadan", 2024, "Anime series", 0.60, "Medium", "Moderate", "Strong", "Exact", 70,
         "Sci-fi/supernatural comedy; recent release."),
        ("konosuba", "KonoSuba", 2016, "Anime series", 0.54, "Low", "Weak", "Moderate", "Exact", 48,
         "Comedy fantasy; narrower appeal."),
        ("gintama", "Gintama", 2006, "Anime series", 0.52, "Low", "Weak", "Moderate", "Exact", 44,
         "Long-running parody; limited Indian reach."),
    ],
    "comp_sets": {
        "expected": ["spy_family", "dr_stone", "kaguya_sama", "one_punch_man", "mob_psycho"],
        "optimistic": ["spy_family", "one_punch_man", "dr_stone", "dandadan", "mob_psycho"],
        "conservative": ["kaguya_sama", "mob_psycho", "konosuba", "gintama", "dr_stone"],
    },
    "base_levers": {"localization": "subs_hindi", "distribution": "ott", "geography": "national",
                    "release_window": "jan_feb", "marketing_budget": "low"},
    "base_cost": 0.5, "base_reach": 2.5,
    "presets": [
        {"id": "festive_dub", "label": "Hindi dub + festive window",
         "levers": {"localization": "dub_hindi_subs_regional", "distribution": "ott", "geography": "regional_first",
                    "release_window": "oct_nov_festive", "marketing_budget": "low"},
         "summary": "Hindi dub with Telugu subtitles, released in the festive season."},
        {"id": "multilingual_hybrid", "label": "Multilingual dub + hybrid",
         "levers": {"localization": "multilingual_dub", "distribution": "hybrid", "geography": "national",
                    "release_window": "oct_nov_festive", "marketing_budget": "medium"},
         "summary": "Multilingual dubs with a hybrid release and a medium campaign."},
    ],
    "recommendation": {
        "headline": "Proceed with a limited OTT test release in Hindi and Telugu, then refresh the data.",
        "platform": "OTT-first, limited test",
        "priority_markets": ["Delhi", "Maharashtra", "Karnataka", "Telangana", "Uttar Pradesh"],
        "localization": ["Hindi dub", "Telugu subtitles", "English subtitles retained"],
        "target_audience": ["Families and youth aged 10-25", "Sports-anime and robotics fans"],
        "launch_window": "November 2027 (festive season)",
        "positioning": "Warm family comedy about a robotics underdog and her fox spirit.",
        "campaign": ["Refresh YouTube data before finalising the campaign",
                     "Launch a Hindi-dub teaser with family-oriented messaging",
                     "Partner with school robotics clubs and family creators"],
        "risks": [("Missing YouTube engagement data", "Re-run the analysis once the YouTube quota resets."),
                  ("Low marketing budget", "Focus on organic creator partnerships in the top five markets.")],
        "items": [
            ("Localization", "Hindi dub with Telugu subtitles.",
             "Hindi and Telugu show the highest language affinity.",
             ["Language affinity: Hindi 80, Telugu 72"], 68,
             "Dub cost against a low marketing budget."),
            ("Timing", "Release in the festive window.",
             "Festive season adds a positive seasonality effect.",
             ["Release-window lever: +2 score"], 60,
             "Seasonality effect is illustrative."),
        ],
    },
}


# ----------------------------------------------------------------------------
# Builders
# ----------------------------------------------------------------------------
def clamp(v, lo=0, hi=100):
    return max(lo, min(hi, v))


def overall(components):
    return round(sum(c["weight"] / 100 * components[c["id"]] for c in COMPONENTS if c["primary"]))


def confidence(factors):
    return round(sum(f["weight"] * factors[f["id"]] for f in CONFIDENCE_FACTORS))


def momentum_label(score):
    return "Strong" if score >= 72 else "Moderate" if score >= 58 else "Weak"


def audience_for(market_index):
    if market_index >= 75:
        return "Urban 16-30"
    if market_index >= 45:
        return "Young urban 16-26, tier-2 cities"
    return "Emerging OTT-first viewers 16-24"


def build_regions(tid, spec):
    rng = random.Random(f"{tid}-regions")
    metros = {"Maharashtra", "Delhi", "Karnataka", "Tamil Nadu", "West Bengal", "Telangana"}
    top = spec["top_states"]
    title_conf = confidence(spec["factors"])
    cap = min(top.values()) - 1
    regions = []
    for state, (local, market_index, ev_base) in STATES.items():
        evidence = clamp(round(ev_base + spec["evidence_adj"] + rng.uniform(-3, 3)))
        if state in top:
            score = top[state]
        else:
            score = round(spec["state_off"] + 0.42 * market_index + rng.uniform(-3, 3))
            score = min(clamp(score), cap)
        conf = clamp(round(evidence * 0.95 - 2 + (title_conf - 60) * 0.1), 5, 95)
        rec = local if local in spec["dub_languages"] else ("English" if local == "English" else "Hindi")
        secondary = local if rec != local else ("Hindi" if local != "Hindi" else "English")
        reasons = []
        if market_index >= 75:
            reasons.append(f"Large addressable audience (market index {market_index})")
        if score >= 72:
            reasons.append(spec["hook"])
        reasons.append(f"{rec} localization has the strongest affinity here")
        if evidence < CONFIG["regional"]["limited_below_evidence"]:
            reasons.append("Limited regional evidence; interpret with caution")
        platform = spec["platform"]
        if spec["theatrical_metros"] and state not in metros:
            platform = "OTT"
        regions.append({
            "state": state, "score": score, "confidence": conf, "evidence_strength": evidence,
            "demand_momentum": momentum_label(score), "recommended_language": rec,
            "secondary_language": secondary, "preferred_platform": platform,
            "audience_segment": audience_for(market_index), "market_index": market_index,
            "reasons": reasons[:4],
        })
    aff = [{"language": lang, "affinity": a, "confidence": c}
           for lang, (a, c) in spec["language_affinity"].items()]
    return {"regions": regions, "language_affinity": aff}


def build_title(tid, spec):
    c, f = overall(spec["components"]), confidence(spec["factors"])
    assert (c, f) == spec["expect"], (tid, c, f, spec["expect"])
    meta = dict(spec["meta"], title_id=tid)
    analysis = {
        "analysis_id": f"an_{tid}_001", "title_id": tid, "status": spec["status"],
        "result_version": "1.3.0", "scoring_config_version": CONFIG["scoring_config_version"],
        "model_version": "xgb-0.9-r2", "model_used": "primary",
        "feature_snapshot_id": f"fs_{tid}_20261022",
        "created_at": f"{spec['last_analysis']}T14:05:00+05:30",
        "components": spec["components"], "confidence_factors": spec["factors"],
        "content_dna": {
            "genres": [{"name": n, "weight": w} for n, w in spec["content_dna"]["genres"]],
            "themes": [{"name": n, "weight": w} for n, w in spec["content_dna"]["themes"]],
            "archetypes": spec["content_dna"]["archetypes"],
            "audience_fit": spec["content_dna"]["audience_fit"],
            "sensitivity_flags": spec["content_dna"]["sensitivity_flags"],
        },
        "drivers": [{"id": f"d{i + 1}", "label": lbl, "points": pts, "component": comp,
                     "source_ids": srcs, "why": why}
                    for i, (lbl, pts, comp, srcs, why) in enumerate(spec["drivers"])],
        "warnings": [{"code": code, "severity": sev, "message": msg} for code, sev, msg in spec["warnings"]],
        "limitations": ["Public demand proxies only; no revenue or viewership outcomes.",
                        "Scores are a calibrated market-potential estimate, not a revenue forecast."],
    }
    comps = []
    for (cid, name, year, fmt, sim, demand, gm, am, fm, perf, reason) in spec["comparables"]:
        comps.append({"id": cid, "title": name, "year": year, "format": fmt, "similarity": sim,
                      "indian_demand": demand, "genre_match": gm, "audience_match": am,
                      "format_match": fm, "india_performance": perf, "reason": reason})
    comparables = {"comparables": comps, "sets": spec["comp_sets"]}
    scenarios = {"base": {"label": "Base strategy", "levers": spec["base_levers"],
                          "cost_points": spec["base_cost"], "reach_points": spec["base_reach"]},
                 "presets": spec["presets"]}
    rec = spec["recommendation"]
    recommendation = {
        "headline": rec["headline"], "platform": rec["platform"],
        "priority_markets": rec["priority_markets"], "localization": rec["localization"],
        "target_audience": rec["target_audience"], "launch_window": rec["launch_window"],
        "positioning": rec["positioning"], "campaign": rec["campaign"],
        "risks": [{"risk": r, "mitigation": m} for r, m in rec["risks"]],
        "items": [{"id": f"r{i + 1}", "topic": t, "decision": d, "expected_benefit": b,
                   "evidence": ev, "confidence": cf, "principal_risk": pr}
                  for i, (t, d, b, ev, cf, pr) in enumerate(rec["items"])],
    }
    return meta, analysis, build_regions(tid, spec), comparables, {"sources": sources_for(spec["source_overrides"])}, scenarios, recommendation


def write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main():
    geo_names = {f["properties"]["ST_NM"] for f in json.loads(GEO.read_text())["features"]}
    assert set(STATES) == geo_names, (set(STATES) ^ geo_names)
    assert sum(c["weight"] for c in COMPONENTS if c["primary"]) == 100
    assert abs(sum(f["weight"] for f in CONFIDENCE_FACTORS) - 1.0) < 1e-9
    write(OUT / "config.json", CONFIG)
    projects = []
    for tid, spec in TITLES.items():
        meta, analysis, regions, comps, sources, scen, rec = build_title(tid, spec)
        for name, obj in [("title", meta), ("analysis", analysis), ("regions", regions),
                          ("comparables", comps), ("sources", sources),
                          ("scenarios", scen), ("recommendation", rec)]:
            write(OUT / tid / f"{name}.json", obj)
        projects.append({"title_id": tid, "status": spec["status"], "last_analysis": spec["last_analysis"]})
    write(OUT / "projects.json", {"projects": projects})
    print(f"Wrote mock data for {len(TITLES)} titles to {OUT}")


if __name__ == "__main__":
    main()
