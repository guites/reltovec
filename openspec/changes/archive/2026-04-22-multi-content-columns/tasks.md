## 1. Configuration Model Update

- [x] 1.1 Update configuration schema/types so each table mapping accepts `content_column` as an ordered string array.
- [x] 1.2 Adjust config parsing and validation to reject non-array `content_column` values with clear errors.
- [x] 1.3 Update configuration examples/fixtures to use array syntax for `content_column`.

## 2. Ingestion Content Composition

- [x] 2.1 Add a single code-level content separator constant (default `"\n\n"`) in the ingestion path.
- [x] 2.2 Implement row mapping that concatenates configured content column values in order using the separator.
- [x] 2.3 Ensure DTO construction passes only the final concatenated string as `content` downstream.

## 3. Schema Validation and Tests

- [x] 3.1 Extend SQLite schema validation to fail when any configured content column is missing.
- [x] 3.2 Add/adjust tests for ordered multi-column concatenation and separator behavior.
- [x] 3.3 Add/adjust tests for invalid mapping failures when required content columns do not exist.
