# Frontend integration contract

The frontend only needs the HTTP API; it must not reproduce scoring logic. The canonical interactive reference is available at `http://localhost:8000/docs` while the API is running.

## Core screen flow

1. **Workspace** — create or select a project.
2. **Title intake** — submit title metadata and positioning assumptions.
3. **Analysis progress** — start a job and poll its status.
4. **Decision dashboard** — show score, confidence, regional opportunity, drivers and evidence.
5. **Scenario lab** — compare localization, platform, budget and regional strategies.
6. **Launch playbook** — render the recommended rollout and risks.

## Input form

Submit `POST /api/v1/projects/{project_id}/titles` with:

```json
{
  "name": "Project Hikari",
  "english_title": "Project Hikari",
  "synopsis": "A long-form synopsis of at least forty characters for content analysis.",
  "content_format": "series",
  "primary_genre": "fantasy",
  "genres": ["fantasy", "action"],
  "themes": ["friendship", "identity"],
  "source_material": "manga",
  "expected_release_period": "Q2 2027",
  "target_platform": "OTT",
  "target_languages": ["Hindi", "Tamil", "Telugu"],
  "target_states": ["Maharashtra", "Tamil Nadu", "Karnataka"],
  "marketing_budget": "medium",
  "studio": "Example Studio",
  "franchise_status": "original",
  "trailer_url": "https://example.com/trailer"
}
```

Validation errors use FastAPI's standard `422` response. Display field-level messages next to the relevant control.

## Analysis lifecycle

Start with `POST /api/v1/titles/{title_id}/analyses`. The response contains `analysis_id`, `job_id` and `status`. Poll `GET /api/v1/jobs/{job_id}` every 1–2 seconds until the status is `completed`, `partially_completed`, or `failed`.

Progress stages are already user-readable. If status is `partially_completed`, render the dashboard and show its warnings; do not treat it as a hard failure. When complete, fetch `GET /api/v1/analyses/{analysis_id}/result`.

## Dashboard output mapping

- Hero score: `market_potential_score` and `decision_classification`
- Evidence reliability: `confidence_score`, `confidence_level`, `confidence_interval`
- Five score cards: `component_scores`
- India opportunity map/list: `regional_scores`
- Why this score: `positive_drivers` and `negative_drivers`
- Comparable proof: `comparable_titles`
- Evidence health drawer: `source_status` and `data_quality_warnings`
- Recommended rollout: `recommendation`
- Reproducibility footer: `model_version`, `feature_version`, `scoring_version`

Never label confidence as prediction accuracy. It describes evidence coverage, freshness, quality and comparable strength. The market score is a decision-support estimate, not promised revenue.

## Scenario lab

Submit `POST /api/v1/analyses/{analysis_id}/scenarios`:

```json
{
  "name": "Hindi + South India dub",
  "target_platform": "OTT",
  "localization_mode": "multilingual_dub",
  "marketing_budget": "high",
  "target_states": ["Maharashtra", "Tamil Nadu", "Karnataka", "Telangana"],
  "target_languages": ["Hindi", "Tamil", "Telugu"]
}
```

Show `score_delta`, `confidence_delta`, `cost_level`, `reach_level`, and the revised recommendation beside the base result. Preserve all scenarios so judges can compare strategies live.

## UI states that must exist

- Empty workspace
- Intake validation error
- Queued/running with progress and stage
- Completed
- Partially completed with warnings
- Failed with retry action
- No scenarios yet
- Scenario comparison
- API unavailable/offline

## Demo-only control

The optional `disabled_sources` input on analysis/scenario requests deliberately simulates source outages. Use it only for resilience demonstrations, not in the normal user path.
