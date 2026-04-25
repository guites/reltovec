## 1. CLI Command Surface

- [x] 1.1 Add `delete <batch_id>` command parsing and validation to the CLI entrypoint.
- [x] 1.2 Wire the command to the batch store/service layer and map results to user-facing output.

## 2. Batch-Scoped Delete Implementation

- [x] 2.1 Implement a transactional delete operation that removes batch-linked rows from `embedding_item_failures`, then `indexed_work_items`, then batch metadata.
- [x] 2.2 Ensure scoped identity resolution uses only work associated with the target `batch_id`.
- [x] 2.3 Return structured deletion counts (failures, released work identities, batch rows) including no-op zero-count outcomes.

## 3. Verification

- [x] 3.1 Add tests for successful delete of an existing batch with associated failures and indexed work.
- [x] 3.2 Add tests proving delete scope isolation (other batches remain unchanged).
- [x] 3.3 Add tests for missing `batch_id` no-op behavior with zero counts.
- [x] 3.4 Add tests that verify rollback/atomicity on injected database failure.

## 4. Documentation and Operator Guidance

- [x] 4.1 Document `delete <batch_id>` usage and expected output alongside existing `index`, `status`, and `purge` commands.
- [x] 4.2 Clarify operational distinction between `purge --error-code` and `delete <batch_id>`.
