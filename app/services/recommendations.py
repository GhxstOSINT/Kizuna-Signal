from __future__ import annotations

from app.db.models import Title
from app.schemas.analysis import LaunchRecommendation, RegionalScore


def build_recommendation(
    title: Title,
    market_score: float,
    confidence: float,
    regions: list[RegionalScore],
    localization_mode: str | None = None,
) -> LaunchRecommendation:
    top_regions = regions[:5]
    priority_markets = [item.state for item in top_regions]
    inferred_languages = list(dict.fromkeys(item.recommended_language for item in top_regions[:3]))
    languages = title.target_languages or inferred_languages

    if market_score >= 80 and confidence >= 70:
        decision = "Proceed with a multilingual regional-first launch."
    elif market_score >= 68:
        decision = "Proceed with a controlled regional pilot before national expansion."
    elif market_score >= 55:
        decision = "Run trailer and localization tests before committing major investment."
    else:
        decision = "Limit investment and collect stronger demand evidence."

    platform = title.target_platform if title.target_platform.lower() != "undecided" else "OTT"
    mode = localization_mode or ("multilingual_dub" if market_score >= 78 else "subtitles")
    if mode == "multilingual_dub":
        localization = [f"Dub in {language}" for language in languages[:2]]
        localization.extend(f"Subtitle in {language}" for language in languages[2:4])
    elif mode == "dub":
        localization = [f"Dub in {languages[0] if languages else 'Hindi'}"]
    else:
        localization = [f"Subtitle in {language}" for language in languages[:4]]

    genre = title.primary_genre.lower()
    audience = ["Urban viewers aged 16-30", f"Existing {genre} and Japanese-content audiences"]
    if genre in {"family", "comedy", "romance"}:
        audience.append("Mainstream crossover audiences")

    risks = []
    if confidence < 60:
        risks.append(
            "Evidence confidence is not yet sufficient for a high-investment national launch."
        )
    if not title.target_languages:
        risks.append(
            "Localization preferences were inferred and should be validated with audience testing."
        )
    risks.append("Public demand proxies do not equal revenue or platform completion outcomes.")

    return LaunchRecommendation(
        decision=decision,
        platform=platform.upper(),
        priority_markets=priority_markets,
        localization=localization,
        target_audience=audience,
        launch_window=title.expected_release_period,
        marketing_positioning=f"Position the title around its {genre} identity, emotional hook and strongest comparable-title audiences.",
        campaign_actions=[
            "Release a localized teaser and compare language-variant engagement.",
            f"Run community and creator activation in {', '.join(priority_markets[:3])}.",
            "Increase campaign investment only after regional engagement validation.",
        ],
        risks=risks,
    )
