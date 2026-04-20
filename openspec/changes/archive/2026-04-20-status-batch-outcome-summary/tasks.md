## 1. Failure Aggregation

- [x] 1.1 Add state-store query support to return failed embedding count per `batch_id` from `embedding_item_failures`.
- [x] 1.2 Add state-store query support to return distinct failure `error_code` values per `batch_id` (deduplicated, stable ordering).

## 2. Status Domain and Serialization

- [x] 2.1 Extend batch/status models to include failure summary fields only (`failed_item_count`, `failure_error_codes`).
- [x] 2.2 Update orchestrator status reconciliation output to attach per-batch failure summaries after finalization.
- [x] 2.3 Update CLI `status` JSON output to include the new failure summary fields for every returned batch.

## 3. Validation

- [x] 3.1 Add state-store tests covering failed-count aggregation and distinct error-code aggregation.
- [x] 3.2 Add orchestrator tests verifying batches finalized during `status` include updated failure summaries.
- [x] 3.3 Add CLI tests asserting `status` output contains `failed_item_count` and `failure_error_codes`.
