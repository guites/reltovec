## Context

The current batch pipeline tracks submitted work to prevent duplicate enqueue and stores per-item failures for reconciliation and remediation. Operators can currently release work only via `purge --error-code`, which is failure-code scoped and cannot fully remove one specific batch and all associated state.

This change adds an operational delete path by `batch_id` that removes batch-linked rows from `embedding_item_failures` and `indexed_work_items`, then removes the batch record itself.

## Goals / Non-Goals

**Goals:**
- Provide a deterministic CLI command to fully remove one batch by `batch_id`.
- Ensure related state is removed in dependency-safe order: failures, indexed work identities, then batch metadata.
- Keep deletion scoped to the requested batch and report deletion counts.
- Make missing `batch_id` a successful no-op with zero counts.

**Non-Goals:**
- Changing `index`, `status`, or `purge --error-code` semantics.
- Adding broad cleanup policies (age-based retention, automatic pruning).
- Deleting source documents or stored embeddings unrelated to the target batch.

## Decisions

1. Add a new CLI subcommand `delete <batch_id>`
- Rationale: batch deletion is operationally distinct from error-code purge and should be explicit.
- Alternative considered: extending `purge` with `--batch-id`. Rejected to avoid overloading one command with different selection semantics.

2. Resolve batch-linked work identities from persisted submission data and delete scoped rows only
- Rationale: `indexed_work_items` should be released only for work associated with the target batch.
- Alternative considered: deleting all indexed work when deleting a batch. Rejected because it could re-enqueue unrelated work.

3. Execute deletion in one database transaction
- Rationale: avoids partial cleanup states (e.g., failures deleted but batch row kept).
- Alternative considered: sequential best-effort deletes. Rejected due to inconsistent state risk.

4. Return operator-facing counts for each deletion step
- Rationale: confirms what changed and supports auditability during recovery operations.
- Alternative considered: silent success/failure only. Rejected because it obscures operational outcomes.

## Risks / Trade-offs

- [Risk] Ambiguous mapping between batch and indexed work identities could under-delete or over-delete.
  Mitigation: derive identities from batch-associated rows only and add tests for scope boundaries.
- [Risk] Accidental deletion of active batch state.
  Mitigation: command requires explicit `batch_id`; output includes deleted counts for verification.
- [Trade-off] Adding another operational command increases CLI surface area.
  Mitigation: keep semantics narrow and document difference from `purge`.

## Migration Plan

- Add the new command and supporting store operation.
- Add tests for success, scope isolation, no-op, and transactional integrity.
- Deploy with command documentation; no data migration required.

## Open Questions

- Whether a guard should block deletion for non-terminal batch statuses.
- Whether command output should include the deleted `batch_id` even on no-op.
