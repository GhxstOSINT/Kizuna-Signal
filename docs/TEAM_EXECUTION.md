# Three-person execution plan

## Owner 1 — backend and platform (this repository)

- Maintain request/response contracts and database schema.
- Integrate and normalize evidence sources behind adapters.
- Own scoring, confidence, provenance and scenario behavior.
- Keep tests, Docker deployment, API documentation and demo resilience green.

## Owner 2 — frontend and storytelling

- Implement the intake wizard, job progress, decision dashboard, regional view, evidence drawer and scenario lab.
- Follow `FRONTEND_CONTRACT.md`; never duplicate backend formulas.
- Prepare a pre-seeded golden demo and clear warning/error states.

## Owner 3 — data, validation and pitch

- Curate reference titles and India-facing evidence.
- Document licenses, timestamps, geographic scope and known bias for each source.
- Test outputs against expert expectations and prepare the judging narrative, benchmark sheet and citations.

## Integration checkpoints

1. Contract freeze: title input and analysis output schemas agreed.
2. Vertical slice: one title runs intake → analysis → dashboard.
3. Scenario slice: base and alternative strategy compare successfully.
4. Evidence review: every displayed number has source status and caveat.
5. Demo rehearsal: live path, partial-source path and offline fallback all succeed.

## Definition of done for the hackathon

- A fresh machine can start the stack from the README.
- The API passes automated tests.
- The frontend can render every required state without private credentials.
- One live or recently cached evidence path is demonstrated, with the deterministic fallback ready.
- Judges can trace the final recommendation back to components, drivers and sources.
- The team can clearly distinguish market score, confidence and actual measured accuracy.
