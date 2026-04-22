## 1. CLI Surface and Validation

- [x] 1.1 Add `index` CLI flags for cutoff column and cutoff value, and thread parsed values into orchestration entry points.
- [x] 1.2 Enforce pairwise validation so cutoff flags must be provided together.
- [x] 1.3 Validate cutoff value format to accept only `YYYY-MM-DD` and `YYYY-MM-DDTHH:MM:SS`, with clear error messages for invalid inputs.

## 2. SQLite Eligibility Filtering

- [x] 2.1 Extend SQLite source schema validation to verify the cutoff column exists when cutoff filtering is requested.
- [x] 2.2 Update SQLite source query generation to apply cutoff predicates and exclude rows with `NULL`/undefined cutoff-column values.
- [x] 2.3 Preserve deterministic ordering and ensure filtered source rows flow into existing duplicate-prevention and fan-out logic without behavioral regressions.

## 3. Limit Semantics, Tests, and Docs

- [x] 3.1 Ensure `--limit` is applied after cutoff filtering and duplicate-prevention so the limit bounds only eligible documents.
- [x] 3.2 Add/update unit tests for CLI validation, cutoff filtering behavior, null-skip behavior, and cutoff-plus-limit interaction.
- [x] 3.3 Update README/config usage examples to document new cutoff flags and expected date/datetime formats.
