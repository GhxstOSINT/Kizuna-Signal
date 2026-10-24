"""Versioned weights. Configuration, not code, so prior outputs can be reproduced."""
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class ConfidenceConfig:
    version: str = "confidence-v1"
    completeness: float = 0.25
    comparables: float = 0.25
    interval: float = 0.25
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
