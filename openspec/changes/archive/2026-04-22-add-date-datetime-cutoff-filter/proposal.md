## Why

Operators need a way to index only newer source rows from SQLite without relying on implicit timestamp abstractions. A user-selected date/datetime cutoff filter enables controlled incremental ingestion while keeping source selection explicit and predictable.

## What Changes

- Add a user-configurable source column selector for date/datetime filtering (for example `created_at` or `published_at`).
- Add a user-provided cutoff value that accepts either date (`YYYY-MM-DD`) or datetime (`YYYY-MM-DDTHH:MM:SS`) formats.
- Exclude rows where the selected date/datetime column is `NULL`/undefined before document eligibility and fan-out.
- Apply cutoff filtering before `--limit` so invocation limits continue to bound only rows that pass filter criteria.
- Update CLI/config validation, ingestion selection logic, and tests/documentation to reflect the new filter behavior.

## Capabilities

### New Capabilities
- None.

### Modified Capabilities
- `sqlite-document-ingestion`: extend source eligibility rules to support explicit date/datetime cutoff filtering with null-skip behavior and deterministic interaction with `index --limit`.

## Impact

- Affected code: CLI/config parsing, SQLite document selection query/filter pipeline, ingestion planning, and tests around source eligibility and limit handling.
- API/CLI impact: adds date-filtering inputs for index invocation/configuration (column + cutoff value).
- Behavior impact: rows with missing values in the selected column are skipped; only rows meeting cutoff constraints are considered for downstream eligibility and `--limit` application.
