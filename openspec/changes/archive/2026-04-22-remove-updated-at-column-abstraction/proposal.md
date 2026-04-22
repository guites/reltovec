## Why

The `updated_at_column` abstraction currently adds configuration and data-model surface area without influencing indexing control flow. Removing it reduces cognitive load and maintenance overhead while preserving existing indexing behavior.

## What Changes

- Remove `sqlite.updated_at_column` from configuration parsing, validation, and examples.
- Remove timestamp passthrough fields (`updated_at`) from source normalization and embedding planning models.
- Simplify SQLite source schema validation to require only identifier and configured content columns.
- Keep indexing semantics unchanged: document selection order, duplicate prevention, batching, and reconciliation behavior remain the same.
- Update tests and documentation to reflect the reduced configuration and model surface.

## Capabilities

### New Capabilities
- None.

### Modified Capabilities
- `sqlite-document-ingestion`: remove optional timestamp-column abstraction from ingestion requirements and schema validation expectations.

## Impact

- Affected code: configuration loading (`config.py`), source repository (`sqlite_source.py`), data models/planner, tests, and `config.example.toml`/README documentation.
- API/CLI impact: no new commands or flags; one configuration key (`sqlite.updated_at_column`) is removed.
- Behavior impact: indexing control flow and output semantics remain unchanged aside from no longer carrying source timestamp metadata internally.
