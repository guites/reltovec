## Context

`index` already contains the lifecycle reconciliation needed to keep tracked batch state accurate: it updates remote statuses for incomplete batches and runs `_finalize_batch` for newly terminal batches. In contrast, `status` only reads `embedding_batches` from local SQLite, which can be stale when batch states have changed remotely since the last `index` run.

This creates an operational blind spot: users cannot trust `status` to reflect real progress, and they must run `index` (which also performs submission logic) just to refresh lifecycle state.

## Goals / Non-Goals

**Goals:**
- Make `status` reconcile tracked batches with remote batch state before output.
- Ensure newly terminal batches discovered during `status` are finalized through the same path used by `index` (parse outputs/errors, upsert embeddings, persist failures, mark processed).
- Avoid introducing duplicate reconciliation logic in CLI.

**Non-Goals:**
- Changing how new work is selected or submitted.
- Changing batch payload schema or vector metadata format.
- Adding new user-facing batch storage backends beyond existing SQLite + Chroma integration.

## Decisions

1. Add a public orchestrator reconciliation entry point for status usage.
   - Decision: introduce a method (for example `refresh_status`) that runs only reconciliation/finalization steps and returns a compact summary.
   - Rationale: CLI should orchestrate commands, while reconciliation rules stay centralized in `IndexOrchestrator`.
   - Alternative considered: implement refresh directly in CLI by calling state/batch/vector components inline. Rejected due to duplicated lifecycle logic and higher regression risk.

2. Reuse existing private flows `_poll_batches(..., wait_for_completion=False)` and `_finalize_batch(...)`.
   - Decision: status-triggered refresh should perform one non-blocking reconciliation pass over known incomplete batches and finalize any newly terminal batches.
   - Rationale: user asked to detect status changes without running `index` again; a non-blocking pass updates what changed now without turning `status` into a long-running poll loop.
   - Alternative considered: always wait until all pending batches finish. Rejected because status should remain quick and observational.

3. Keep `status` non-submitting by construction.
   - Decision: status path must not call source loading, planning, JSONL building, upload, or batch creation.
   - Rationale: command intent is operational visibility; submission belongs to `index`.

4. Preserve current status output shape, with refreshed underlying data.
   - Decision: keep the existing list of batch records output format so tooling compatibility remains intact.
   - Rationale: behavioral improvement without forcing consumers to update parsers.

## Risks / Trade-offs

- [Risk] Reconciliation in `status` now touches external systems (OpenAI, Chroma), so command failures can increase.
  - Mitigation: use existing error propagation and add tests for failure surfaces.
- [Risk] Shared reconciliation code between `index` and `status` could introduce coupling.
  - Mitigation: keep shared logic in orchestrator methods with explicit command-specific entry points.
- [Trade-off] One-pass non-blocking refresh may still show in-progress batches after command returns.
  - Mitigation: this is intentional for responsiveness; repeated `status` calls continue to refresh state.

## Migration Plan

1. Implement orchestrator refresh method and wire CLI `status` to call it before listing batches.
2. Add/adjust tests for CLI and orchestrator status-refresh behavior.
3. No data migration required; existing state tables and records remain valid.

Rollback strategy: revert CLI wiring to direct DB listing and remove the refresh method if issues are found.

## Open Questions

- Should `status` expose refresh summary counters (e.g., refreshed batches, finalized embeddings) in addition to current batch list, or keep output unchanged for now?
