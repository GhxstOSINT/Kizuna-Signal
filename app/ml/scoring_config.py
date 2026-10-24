"""Versioned weights. Configuration, not code, so prior outputs can be reproduced."""

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class ConfidenceConfig:
    version: str = "confidence-v2"
    completeness: float = 0.25  # how much of the title's own information was supplied
    comparables: float = 0.25
    agreement: float = 0.15  # ridge and XGBoost give similar lifts for this title
    interval: float = 0.10  # width of the calibrated interval (the same for every title)
    out_of_distribution: float = 0.25


@dataclass(frozen=True)
class MarketPotentialConfig:
    """The architecture's illustrative weights. Engagement quality needs YouTube data, which is
    not collected yet, so its weight is reported as unavailable rather than imputed."""

    version: str = "market-potential-v1"
    content_fit: float = 0.25
    demand_momentum: float = 0.25
    regional_opportunity: float = 0.20
    engagement_quality: float = 0.15
    comparable_performance: float = 0.15


def as_dict(cfg) -> dict:
    return asdict(cfg)
