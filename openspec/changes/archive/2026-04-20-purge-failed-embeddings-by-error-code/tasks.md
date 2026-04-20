## 1. State Purge Semantics

- [x] 1.1 Add a transactional `BatchStateStore` purge method that accepts `error_code` and returns deleted failure-row count plus released work-identity count.
- [x] 1.2 Implement purge SQL to delete matching `embedding_item_failures` rows and remove corresponding `indexed_work_items` entries for distinct non-null `custom_id` values.
- [x] 1.3 Ensure purge behavior is exact-match on `error_code` and is a safe no-op when no rows match.

## 2. Domain and CLI Command Wiring

- [x] 2.1 Add a purge summary model and orchestrator method that delegates to state-store purge behavior.
- [x] 2.2 Extend CLI parser with `purge` subcommand and required `--error-code` argument.
- [x] 2.3 Implement CLI `purge` command handling to initialize dependencies, execute purge, and print JSON summary output.

## 3. Validation

- [x] 3.1 Add state-store tests for scoped deletion, no-match behavior, and release of duplicate-prevention records.
- [x] 3.2 Add orchestrator tests verifying purge summary propagation and no-op handling.
- [x] 3.3 Add CLI tests for `purge --error-code` argument behavior and output structure.
