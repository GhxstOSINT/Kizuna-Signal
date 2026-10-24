# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Delegated: React, TypeScript and Vite for the dedicated `frontend/` website, connected to the existing FastAPI `/api/v1` contract. The local FastAPI service remains the system of record. Ditto's local capture of Octolane is the visual-reference input, not a source of Octolane branding or copy.

## Users

The primary users are media-rights analysts, Japanese studios, Indian distributors, localization teams and launch planners evaluating unreleased Japanese film, anime and series opportunities in India.

Their core job is to decide whether a title merits investment, which states and language audiences to prioritize, which release and localization strategy to test, and what evidence or uncertainty supports that decision.

## Product Purpose

Kizuna Signal is an explainable pre-release intelligence and launch-planning product for Japanese media entering India. It turns title metadata, permitted market signals, model outputs and regional context into a market-potential assessment, confidence statement, state and language priorities, scenario comparisons and an actionable launch playbook.

Success means a user can move from a new-title intake to a reviewable launch recommendation, understand every major driver and data limitation, and compare strategies without changing the frozen base analysis.

## Positioning

Kizuna Signal combines India-specific regional and language planning with evidence provenance, separate opportunity and confidence measures, comparable-title reasoning and saved what-if launch scenarios in one pre-release workflow.

## Operating Context

- Users work title by title inside a project or portfolio.
- They provide creative metadata and launch assumptions, submit an analysis, monitor its job state, review the result, evaluate scenarios and approve or reject a launch playbook.
- The dashboard consumes the versioned FastAPI contract and must preserve queued, running, partial, failed and completed states.
- The application must run locally for the hackathon and support Docker-based shared deployment.

## Capabilities and Constraints

- The authoritative base analysis lives in the backend. The dashboard must not reproduce or silently alter its score.
- Market potential and confidence are distinct concepts. Confidence describes evidence completeness and quality; it is never labelled prediction accuracy.
- Results include component scores, regional rankings, comparables, positive and negative drivers, source status, warnings, recommendation and version metadata.
- Scenarios are evaluated against a frozen analysis and may change localization, platform, budget, languages, target states and simulated source availability.
- SEO assistance may optimize public-facing title, synopsis, keywords and metadata suggestions, but it must never overwrite the submitted canonical title without explicit user acceptance.
- Source evidence must be permitted, timestamped and attributable. Missing sources produce an unavailable state and confidence penalty rather than fabricated live observations.
- Current repository evidence contains deterministic demo adapters and an embedded comparable catalogue. No trained-model artifact, inference module or production dataset connector is currently present in the repository. The website must surface that configuration truth until those assets are supplied.
- Existing Streamlit files remain legacy reference code during the migration; the dedicated React website in `frontend/` is the forward interface.

## Brand Commitments

- Product name: Kizuna Signal.
- Core product language: calm, precise, evidence-aware and decision-oriented.
- The user explicitly selected Octolane.com as the visual and interaction reference: pale editorial surfaces, strong typographic scale, restrained controls, measured motion, luminous spectral accents and confident whitespace.
- Octolane logos, proprietary copy and branded assets must not be reused.

## Evidence on Hand

- A working FastAPI project, title, analysis, job and scenario contract.
- SQLite persistence for local use and PostgreSQL/pgvector configuration for Docker.
- Deterministic demo analysis data and test fixtures.
- A local Ditto capture of Octolane's responsive DOM, styles and screenshots under `.integration-pip-tmp/octolane-reference`.
- No trained-model binary, feature preprocessor, validated historical outcome dataset or live-provider credentials are present in the repository as of this build. Future work must not invent their existence or accuracy.

## Product Principles

1. Explain the decision: every score must connect to evidence, drivers and version metadata.
2. Separate opportunity from certainty: high potential with weak evidence must look and behave differently from a high-confidence result.
3. Preserve human judgment: model and SEO suggestions remain reviewable, editable and explicitly accepted.
4. Fail honestly: unavailable sources and unconfigured models are visible product states.
5. Design for regional action: state, language, platform and localization decisions are first-class outputs.

## Accessibility & Inclusion

The dedicated web interface must support keyboard navigation, visible focus states, readable contrast, reduced motion and responsive layouts from mobile through desktop. Regional and language recommendations must be presented as market evidence, not as personal or protected-attribute profiling.
