## 1. Configuration Surface Simplification

- [x] 1.1 Remove `updated_at_column` from `SQLiteConfig` and config loading/parsing logic.
- [x] 1.2 Remove `updated_at_column` from `config.example.toml` and README configuration guidance.
- [x] 1.3 Ensure configuration validation no longer expects or validates timestamp mapping fields.

## 2. Ingestion and Model Cleanup

- [x] 2.1 Remove `updated_at` fields from ingestion/planning models that only exist for passthrough metadata.
- [x] 2.2 Simplify `SQLiteDocumentRepository` selection and normalization paths to stop reading/propagating source timestamp values.
- [x] 2.3 Confirm indexing orchestration behavior (selection, dedupe, batching) is unchanged after field removal.

## 3. Verification and Regression Coverage

- [x] 3.1 Update unit tests and fixtures that currently construct config with `updated_at_column`.
- [x] 3.2 Update ingestion/planner/vector-store tests to reflect removed timestamp passthrough behavior.
- [x] 3.3 Run lint/test suite and fix regressions introduced by the simplification.
