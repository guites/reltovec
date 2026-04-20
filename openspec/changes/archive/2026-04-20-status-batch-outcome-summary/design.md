## Context

`status` currently reconciles tracked OpenAI batch lifecycle state and finalizes newly terminal batches, but the returned records are limited to lifecycle metadata (`batch_id`, `status`, file IDs, timestamps). Operators cannot directly see, per batch, how many embedding items failed or which failure categories occurred.

Per-item failures are already persisted in `embedding_item_failures`, but there is no response-level aggregation of failed-item totals and failure code categories in the `status` payload.

## Goals / Non-Goals

**Goals:**
- Add per-batch failure summary data to `status` results:
  - failed embedding item count for the batch
  - unique failure `error_code` values for the batch
- Ensure failure summary values are stable across later `status` calls.
- Preserve current behavior where `status` reconciles/finalizes tracked batches but does not submit new work.

**Non-Goals:**
- Building an automatic retry queue or retry scheduler for failed items.
- Tracking or persisting per-batch successful embedding totals in state DB.
- Changing batch submission/planning or duplicate-prevention semantics.

## Decisions

### 1. Use `embedding_item_failures` as the sole reporting source
- Decision: Derive failed item counts and distinct failure `error_code` values directly from persisted `embedding_item_failures` rows keyed by `batch_id`.
- Rationale: Failure data is already persisted and linked to batches, so no additional table is required.
- Alternative considered: Add new success/failure summary fields on `embedding_batches`. Rejected to avoid unnecessary schema expansion.

### 2. Add aggregation query support in state store
- Decision: Implement state-store helpers that return per-batch failed count plus distinct error-code list.
- Rationale: Centralizes SQL logic and keeps orchestrator/CLI focused on response assembly.
- Alternative considered: Aggregate in orchestrator by loading raw failure rows. Rejected due to duplication and weaker data-layer encapsulation.

### 3. Extend status DTO/CLI serialization with failure summary fields
- Decision: Include failure summary fields in each `status` batch entry (`failed_item_count`, `failure_error_codes`).
- Rationale: Keeps operational triage in one command without adding extra endpoints/commands.
- Alternative considered: Add a separate failure-report command. Rejected as unnecessary for current scope.

## Risks / Trade-offs

- [Partial observability] -> Mitigation: document that reporting is intentionally failure-only for now and does not include successful-item totals.
- [Inconsistent error_code values] -> Mitigation: normalize by de-duplicating and excluding null/empty codes in returned summaries.
- [Aggregation correctness across reconciliation timing] -> Mitigation: compute status output after reconciliation/finalization pass so newly terminal batches include up-to-date failures.

## Migration Plan

1. Add state-store aggregation queries for failed count and distinct error codes per batch.
2. Extend status output model and CLI serialization with failure summary fields.
3. Add/adjust tests for state-store aggregation, orchestrator status output enrichment, and CLI JSON output.

## Open Questions

- None at this time.
