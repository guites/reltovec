## Why

The `status` command currently returns only locally stored batch rows, so it can show stale lifecycle data until `index` runs again. Operators need a way to refresh tracked batches and finalize newly terminal work without submitting new indexing jobs.

## What Changes

- Update `status` to reconcile tracked batches with the OpenAI Batch API before printing results.
- Reuse the existing batch finalization flow so newly terminal batches discovered during `status` are parsed and persisted (embeddings and failures).
- Keep `status` read-only with respect to new work submission: it must not enqueue new source documents or create new batches.

## Capabilities

### New Capabilities
- None.

### Modified Capabilities
- `openai-batch-embedding-pipeline`: extend tracked-batch lifecycle handling so `status` performs remote status refresh and terminal finalization, not only local DB reads.

## Impact

- Affected code: CLI status path, orchestrator batch reconciliation flow, batch client/state/vector interactions reused by status.
- Affected behavior: `status` becomes an active reconciliation command instead of a passive SQLite listing.
- Tests: CLI and orchestrator coverage must assert refreshed statuses and finalized terminal batches during `status`.
