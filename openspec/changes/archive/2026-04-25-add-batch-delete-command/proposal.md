## Why

Operators need a targeted way to fully remove a specific batch and all of its related state when a batch is invalid, test-only, or must be replayed cleanly. The existing `purge --error-code` flow does not support removing one batch by `batch_id`.

## What Changes

- Add a `delete` command that accepts a required `batch_id` argument.
- Delete all `embedding_item_failures` rows associated with the specified batch.
- Delete all `indexed_work_items` rows associated with the specified batch's submitted work identities.
- Delete the batch record itself from batch-tracking storage.
- Return command output summarizing deleted failure rows, released work identities, and batch-row deletion.
- Define no-op behavior when `batch_id` does not exist.

## Capabilities

### New Capabilities
- None.

### Modified Capabilities
- `openai-batch-embedding-pipeline`: Extend operational lifecycle management with a batch-scoped `delete` command that removes batch-linked failure and duplicate-prevention state before deleting the batch record.

## Impact

- Affected specs: `openspec/specs/openai-batch-embedding-pipeline/spec.md` (delta).
- Affected CLI surface: new `delete <batch_id>` command.
- Affected persistence flows: batch-scoped deletes in `embedding_item_failures`, `indexed_work_items`, and batch metadata tables.
- Testing impact: new command behavior tests, including successful deletion and no-op for missing `batch_id`.
