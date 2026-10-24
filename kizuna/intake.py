"""Title-intake field definitions, validation and completeness (pure, no Streamlit)."""

REQUIRED = [
    ("title", "Title"),
    ("synopsis", "Synopsis"),
    ("format", "Content format"),
    ("primary_genre", "Primary genre"),
    ("source_material", "Source material"),
    ("release_period", "Expected release period"),
    ("target_platform", "Target platform (or Undecided)"),
]

OPTIONAL = [
    ("english_title", "English title"),
    ("poster_name", "Poster"),
    ("trailer_url", "Trailer URL"),
    ("secondary_genres", "Secondary genres"),
    ("themes", "Themes"),
    ("studio", "Studio"),
    ("director", "Director"),
    ("cast", "Cast"),
    ("episodes", "Episode count or duration"),
    ("age_rating", "Age rating"),
    ("franchise_status", "Franchise status"),
    ("target_languages", "Target languages"),
    ("target_states", "Target states"),
    ("budget_band", "Budget band"),
    ("release_month", "Release month"),
    ("intended_audience", "Intended audience"),
]

SOURCE_MATERIAL = ["Original", "Manga", "Novel", "Game", "Existing franchise"]
PLATFORMS = ["OTT", "Theatrical", "Television", "Digital-first", "Undecided"]
AGE_RATINGS = ["All ages", "10+", "13+", "16+", "18+"]
BUDGET_BANDS = ["Low", "Medium", "High"]
GENRES = ["Action", "Adventure", "Comedy", "Coming of Age", "Drama", "Fantasy", "Horror",
          "Mystery", "Psychological", "Romance", "Sci-Fi", "Slice of Life", "Sports", "Supernatural"]
FRANCHISE_STATUS = ["New IP", "Manga adaptation", "Sequel or spin-off", "Existing franchise"]
MAX_TEXT = 4000
MAX_POSTER_BYTES = 5 * 1024 * 1024
POSTER_TYPES = ("png", "jpg", "jpeg", "webp")


def _filled(v):
    if v is None:
        return False
    if isinstance(v, str):
        return bool(v.strip())
    if isinstance(v, (list, tuple, set, dict)):
        return len(v) > 0
    return True


def validate(payload):
    """Return a list of error strings (empty when valid)."""
    errors = []
    for key, label in REQUIRED:
        if not _filled(payload.get(key)):
            errors.append(f"{label} is required.")
    for key in ("title", "synopsis", "english_title", "studio", "director"):
        v = payload.get(key)
        if isinstance(v, str) and len(v) > MAX_TEXT:
            errors.append(f"{key} is too long (max {MAX_TEXT} characters).")
    url = (payload.get("trailer_url") or "").strip()
    if url and not url.lower().startswith(("http://", "https://")):
        errors.append("Trailer URL must start with http:// or https://.")
    return errors


def completeness(payload):
    """(percent filled across required + optional fields, list of missing labels)."""
    fields = REQUIRED + OPTIONAL
    missing = [label for key, label in fields if not _filled(payload.get(key))]
    pct = round(100 * (len(fields) - len(missing)) / len(fields))
    return pct, missing
