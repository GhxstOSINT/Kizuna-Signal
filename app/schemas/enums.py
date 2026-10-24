from enum import StrEnum


class ContentFormat(StrEnum):
    ANIME_SERIES = "anime_series"
    ANIME_FILM = "anime_film"
    LIVE_ACTION_SERIES = "live_action_series"
    LIVE_ACTION_FILM = "live_action_film"
    GAME = "game"
    OTHER = "other"


class AssetType(StrEnum):
    POSTER = "poster"
    TRAILER = "trailer"
    SYNOPSIS_DOCUMENT = "synopsis_document"
    SCRIPT = "script"


class DistributionModel(StrEnum):
    OTT = "ott"
    THEATRICAL = "theatrical"
    TELEVISION = "television"
    DIGITAL_FIRST = "digital_first"
    HYBRID = "hybrid"


class LocalizationMode(StrEnum):
    SUBTITLED = "subtitled"
    DUBBED = "dubbed"
    SUBTITLED_AND_DUBBED = "subtitled_and_dubbed"


class LaunchGeography(StrEnum):
    NATIONAL = "national"
    REGIONAL_FIRST = "regional_first"
    SELECTED_STATES = "selected_states"


class BudgetBand(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Positioning(StrEnum):
    MAINSTREAM = "mainstream"
    FAN_COMMUNITY = "fan_community"
    HYBRID = "hybrid"


class JobType(StrEnum):
    COLLECTION = "collection"
    ANALYSIS = "analysis"
    SCENARIO = "scenario"
    REPORT = "report"


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class SourceHealth(StrEnum):
    OK = "ok"
    DEGRADED = "degraded"  # cache or fixture used, or partial data
    UNAVAILABLE = "unavailable"


class RegionType(StrEnum):
    STATE = "state"
    LANGUAGE = "language"


class RecommendationCategory(StrEnum):
    LOCALIZATION = "localization"
    PLATFORM = "platform"
    TIMING = "timing"
    CAMPAIGN = "campaign"


class DecisionStatus(StrEnum):
    DRAFT = "draft"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class ReportFormat(StrEnum):
    PDF = "pdf"
