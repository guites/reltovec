## Context

Failed embedding items are persisted in `embedding_item_failures`, while duplicate-prevention state is persisted in `indexed_work_items`. Current `index` planning excludes any `custom_id` present in `indexed_work_items`, so failed items cannot be retried unless those state records are removed.

The requested approach is to avoid building a new retry pipeline and instead provide an operator command that purges failed state for a specific `error_code`, making those work items eligible for normal `index` re-submission.

## Goals / Non-Goals

**Goals:**
- Add a `purge` CLI command with required `--error-code` targeting.
- Delete failure records for the provided `error_code`.
- Release matching work identities from duplicate-prevention state so `index` can enqueue them again.
- Return deterministic purge summary output (deleted failure rows and released work-item count).

**Non-Goals:**
- Automatic retries, retry scheduling, or backoff policy.
- Deleting vector-store embeddings or batch metadata rows.
- Introducing a new pipeline stage outside existing `index` and `status` flows.

## Decisions

### 1. Purge clears both failure rows and duplicate-prevention work records
- Decision: For a given `error_code`, purge will:
  - delete matching rows in `embedding_item_failures`
  - delete corresponding `indexed_work_items` rows for matched non-null `custom_id` values
- Rationale: Removing only failure rows would not re-enable indexing because duplicate-prevention still blocks already submitted `custom_id` values.
- Alternative considered: Remove failures only and rely on manual DB edits for `indexed_work_items`. Rejected as unsafe and operationally inconsistent.

### 2. Implement purge as a transactional state-store operation
- Decision: Add a single state-store method that performs selection + deletes in one SQLite transaction and returns counts.
- Rationale: Keeps state transitions atomic; avoids partial release where one table is updated without the other.
- Alternative considered: Multi-step deletes in CLI/orchestrator code. Rejected due to higher risk of inconsistent state.

### 3. Route purge through orchestrator and expose JSON summary in CLI
- Decision: Add a focused orchestrator method that calls state-store purge and returns a summary DTO; CLI `purge` prints that summary as JSON.
- Rationale: Maintains existing layering (CLI orchestration through domain service) and keeps tests aligned with current command patterns.
- Alternative considered: CLI invoking state store directly. Rejected to avoid bypassing orchestration boundaries.

## Risks / Trade-offs

- [Accidental over-deletion from broad targeting] -> Mitigation: require explicit `--error-code` and exact-match filtering.
- [Partial state mutation] -> Mitigation: wrap purge logic in a single database transaction.
- [Rows without `custom_id` cannot be re-enqueued] -> Mitigation: still delete matching failure records, but report released work count based only on valid `custom_id` rows.
- [Operator confusion about impact] -> Mitigation: return clear counts for deleted failures and released work identities.

## Migration Plan

1. Extend state-store API with transactional purge-by-error-code behavior and return counts.
2. Add orchestrator/domain summary model for purge results.
3. Add CLI `purge --error-code` parser and command dispatch.
4. Add tests for state-store purge semantics, orchestrator integration, and CLI output.

## Open Questions

- None at this time.
