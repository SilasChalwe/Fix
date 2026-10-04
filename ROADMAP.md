# FIX Contributor Roadmap

This roadmap reflects the current repository implementation and defines the order in which contributor work should progress.

## Current implementation

The repository already contains:

- GTK 4 desktop application shell;
- shared `Selection` application state;
- plugin registry and adapter/operation-plan architecture;
- Remove Watermark plugin;
- Add / Replace Watermark plugin;
- Thumbnail / Cover plugin;
- shared FFmpeg and FFprobe services;
- output validation;
- unit tests for current plugins/media helpers;
- a GitHub Actions test workflow.

The active Trim contribution is being reviewed separately in PR #1 and is not considered implemented on `main` yet.

## Phase gate

Development proceeds in order:

**M1 → M2 → M3 → M4 → M5**

Only the first incomplete milestone is active for implementation. Later milestones are visible for planning but remain blocked until the previous milestone satisfies its exit criteria.

## M1 — Reliability & Independent Validation — ACTIVE

Tracker: #4

Work items:

- #9 — Restore GitHub Actions hosted-runner execution
- #10 — Add generated media fixtures for integration testing
- #11 — Add real FFmpeg integration tests for current media operations
- #12 — Prove source integrity and rollback for in-place watermark overlay
- #13 — Strengthen output validation for processed media
- #14 — Expand contributor workflow and issue-claiming guide

M1 closes only after independent tests can exercise real media behavior and the current operations are proven safe.

## M2 — Trim Feature Completion — BLOCKED

Tracker: #5

PR #1 is the current implementation candidate. Before Trim is considered complete it must have a clear accuracy contract, real-media tests for non-keyframe cuts, consistent range behavior, GTK UI access, and verified metadata/stream preservation.

## M3 — Editing UX & Operational Safety — BLOCKED

Tracker: #6

Planned work includes selection editing improvements, meaningful processing progress, cancellation support, conflict-free processing state, and consistent completion/failure behavior.

## M4 — Media Compatibility & Performance — BLOCKED

Tracker: #7

This phase proves supported containers/codecs/streams with a maintained compatibility matrix and avoids unnecessary re-encoding where practical.

## M5 — Packaging & Release 1.0 — BLOCKED

Tracker: #8

This phase covers Ubuntu-focused packaging, dependency diagnostics, versioning, release notes, installation documentation, and final regression validation.

## Contributor rule

Before starting work:

1. Open the active milestone tracker.
2. Pick an open issue from that milestone.
3. Comment on the issue to show that you are working on it.
4. Keep the pull request scoped to that issue.
5. Follow the architecture contract in `README.md` and `docs/ARCHITECTURE.md`.
6. Add tests for changed behavior.
7. Do not commit client/private media, credentials, tokens, or confidential assets.

A contributor's local test report is useful, but merge approval requires independent maintainer/CI validation.
