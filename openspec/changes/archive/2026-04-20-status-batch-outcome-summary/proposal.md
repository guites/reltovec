## Why

The `status` command currently returns lifecycle metadata per batch but does not expose failure metrics that operators need to assess indexing quality quickly. We need per-batch visibility into failed embedding count and failure categories so users can triage issues without manual database inspection.

## What Changes

- Extend `status` response entries with per-batch failed embedding item totals.
- Include per-batch failure classification summary as a unique list of encountered `error_code` values.
- Ensure these failure summary fields reflect finalized data persisted in local state, including batches finalized during the same `status` invocation.
- Keep `status` non-submitting (no new index work creation) while enriching response payload only.

## Capabilities

### New Capabilities
- None.

### Modified Capabilities
- `openai-batch-embedding-pipeline`: `status` output requirements are expanded to include batch-level failed-item totals and failure error-code categories.

## Impact

- Affected code:
  - `src/reltovec/cli.py` (`status` output shaping)
  - `src/reltovec/orchestrator.py` (status reconciliation return payload)
  - `src/reltovec/state_store.py` (failure aggregation queries)
  - `src/reltovec/models.py` (status DTO updates)
- Affected tests:
  - `tests/test_orchestrator.py`
  - `tests/test_state_store.py`
  - `tests/test_cli.py`
- No new external dependencies expected.
- No new state DB tables are introduced in this change.
