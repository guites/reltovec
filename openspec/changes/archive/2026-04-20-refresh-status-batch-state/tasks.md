## 1. Orchestrator Reconciliation API

- [x] 1.1 Add a public orchestrator method that executes batch reconciliation/finalization without submission logic.
- [x] 1.2 Ensure the method finalizes unprocessed terminal batches and performs a non-blocking status refresh for tracked incomplete batches.
- [x] 1.3 Return reconciliation counters or outcomes needed by callers while preserving existing `index` behavior.

## 2. CLI Status Integration

- [x] 2.1 Update `status` command wiring to instantiate required dependencies and invoke the orchestrator reconciliation method before listing batches.
- [x] 2.2 Keep `status` output contract stable (batch list format) while ensuring returned rows reflect freshly reconciled state.
- [x] 2.3 Confirm the `status` path does not trigger source loading, work planning, or new batch submissions.

## 3. Test Coverage

- [x] 3.1 Add/adjust orchestrator tests for reconciliation-only execution, including newly terminal batch finalization.
- [x] 3.2 Add/adjust CLI tests to verify `status` refreshes lifecycle state before printing.
- [x] 3.3 Add a regression test proving `status` refresh never submits new batches.
