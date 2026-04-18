## Why

Repeated `index` CLI executions currently risk selecting document/model work that was already indexed in earlier runs. This blocks safe incremental processing and makes it hard to process large datasets in predictable chunks.

## What Changes

- Add an `index --limit <n>` CLI argument that controls how many documents are selected in a single `index` invocation, independent of `max_batch_size`.
- Enforce incremental eligibility so each `index` call selects only documents that have never been indexed before.
- Validate that documents already associated with indexing work are excluded from new selections regardless of stored batch lifecycle status.
- Ensure deterministic chunking across repeated runs so calls like `index --limit 5000` can be repeated to process new sets each time.
- Update command output/telemetry to report limit-driven selection counts and skipped already-indexed documents.

## Capabilities

### New Capabilities
- None.

### Modified Capabilities
- `sqlite-document-ingestion`: change eligibility rules so document selection for indexing excludes already-indexed documents and supports invocation-level limits.
- `openai-batch-embedding-pipeline`: change batch planning/validation so new batch input cannot include document/model work that has already been indexed, regardless of current batch status metadata.

## Impact

- Affected code: CLI argument parsing for `index`, document selection query/planning layer, batch request construction, and indexing validation logic.
- Data usage: existing SQLite indexing/batch metadata tables become the source of truth for duplicate-prevention checks.
- Testing: requires coverage for repeated `index --limit` runs, duplicate-prevention across non-terminal/terminal statuses, and limit semantics independent from `max_batch_size`.
