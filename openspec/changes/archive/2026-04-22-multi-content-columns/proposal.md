## Why

The current ingestion config supports only one `content_column`, which prevents composing richer embedding input from multiple fields in the same row. We need to support multi-column content composition now so teams can build higher-quality context without schema migrations.

## What Changes

- Allow `content_column` in `config.toml` to be an ordered array of column names.
- Build document `content` by concatenating configured column values in order.
- Use a fixed separator variable (default `"\n\n"`) between column values during concatenation.
- Pass the fully concatenated value through existing application DTOs as `content`.
- Fail fast when any configured content column is missing from the source table schema.

## Capabilities

### New Capabilities
- None.

### Modified Capabilities
- `sqlite-document-ingestion`: Update source mapping requirements to accept multiple content columns and define deterministic concatenation behavior.

## Impact

- Affected specs: `openspec/specs/sqlite-document-ingestion/spec.md`
- Affected code: configuration parsing/validation, SQLite row-to-document mapping, ingestion DTO construction
- No new external dependencies; no API surface expansion beyond updated config semantics
