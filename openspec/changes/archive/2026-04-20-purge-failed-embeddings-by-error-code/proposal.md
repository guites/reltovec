## Why

Failed embedding work items currently remain recorded as failed, which blocks straightforward retry from normal `index` runs. We need a simple recovery path that avoids introducing a new retry pipeline while still allowing operators to requeue known failure classes.

## What Changes

- Add a `purge` command that removes failed embedding item records from local state.
- Add `--error-code <code>` to `purge` so operators can target failed items by a specific error code.
- Ensure purge only removes failed-item records (not successful embedding vectors or unrelated batch metadata) so deleted work becomes eligible for re-enqueue on the next `index` run.
- Define operator-facing behavior for invalid or unmatched error codes and summarize deleted item counts.

## Capabilities

### New Capabilities
- None.

### Modified Capabilities
- `openai-batch-embedding-pipeline`: Add requirements for purging failed embedding item records by `error_code` so previously failed work can be retried via existing `index` behavior.

## Impact

- Affected spec: `openspec/specs/openai-batch-embedding-pipeline/spec.md` (delta under this change).
- Affected CLI surface: new `purge` command and `--error-code` option.
- Affected state layer: deletion logic for failed embedding item records keyed by stored `error_code`.
- Affected operator workflow: retry now uses `purge --error-code ...` followed by `index`.
