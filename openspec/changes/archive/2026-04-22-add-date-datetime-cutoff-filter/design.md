## Context

`index` currently loads all normalized source rows from SQLite, then applies duplicate-prevention and `--limit` selection in deterministic source order. There is no explicit way to constrain source eligibility by a user-provided temporal field (for example `created_at`/`published_at`), so operators cannot target only newer records without changing source tables externally.

This change introduces an explicit date/datetime cutoff filter that is user-provided at invocation time: a source column name plus a cutoff value. The filter must skip rows where the selected column is missing (`NULL`/undefined) and must integrate cleanly with existing limit semantics.

## Goals / Non-Goals

**Goals:**
- Add index-time filter inputs for cutoff column and cutoff value.
- Accept both date (`YYYY-MM-DD`) and datetime (`YYYY-MM-DDTHH:MM:SS`) cutoff formats.
- Enforce deterministic eligibility order while applying temporal filtering before `--limit`.
- Skip rows with `NULL`/undefined values in the selected cutoff column.
- Keep duplicate-prevention and model fan-out behavior unchanged after filtered selection.

**Non-Goals:**
- Introduce automatic watermark/checkpoint persistence across runs.
- Rework batch submission, reconciliation, purge, or vector-store query behavior.
- Add broad date-expression syntax beyond one explicit cutoff value.

## Decisions

### Decision: Extend `index` CLI with optional cutoff flags
- Add two optional `index` flags:
  - `--cutoff-column <sqlite_column>`
  - `--cutoff-value <date_or_datetime>`
- Rationale: keeps feature invocation-scoped and explicit, matching existing `index --limit` usage.
- Alternative considered: add static config-only fields under `[sqlite]`.
  - Rejected because operators frequently vary incremental windows run-to-run.

### Decision: Validate cutoff inputs as an all-or-nothing pair
- If either `--cutoff-column` or `--cutoff-value` is provided alone, fail fast with CLI validation error.
- Validate cutoff value format to accept only:
  - `YYYY-MM-DD`
  - `YYYY-MM-DDTHH:MM:SS`
- Rationale: prevents ambiguous filtering and avoids silently unbounded indexing.
- Alternative considered: allow one flag and infer defaults.
  - Rejected due hidden behavior and harder operator debugging.

### Decision: Apply cutoff filtering in SQLite query before normalization and limit
- Extend source loading to optionally include:
  - `WHERE "<cutoff_column>" IS NOT NULL`
  - temporal comparison clause against the parsed cutoff
- Keep ordering unchanged (`ORDER BY id ASC, rowid ASC`) so downstream deterministic behavior remains stable.
- Rationale: SQL-level filtering avoids loading irrelevant rows and guarantees `--limit` counts only filtered candidates.
- Alternative considered: filter in Python after full row load.
  - Rejected for unnecessary memory/IO overhead and weaker semantics around pre-limit selection.

### Decision: Preserve existing orchestration semantics after filtered load
- No changes to duplicate-prevention keying, fan-out planning, batch chunking, or reconciliation.
- `--limit` remains a cap on selected unseen documents, but now over the cutoff-filtered source candidate set.
- Rationale: keeps behavior additive and low risk.

## Risks / Trade-offs

- [Risk] SQLite temporal parsing differs across heterogeneous source formats. -> Mitigation: strictly validate cutoff input format and document expectation that source cutoff column contains comparable date/datetime values.
- [Risk] Users may pass a non-existent cutoff column. -> Mitigation: extend schema validation to include cutoff column when provided and fail with explicit missing-column error.
- [Trade-off] Invocation-scoped flags require operators to supply filters on each run. -> Mitigation: document shell alias/automation patterns in README examples.
- [Trade-off] Rows with non-null but invalid temporal values may be excluded by SQL comparison behavior. -> Mitigation: document behavior as non-eligible rows and add tests for predictable handling.

## Migration Plan

1. Add CLI flags and argument validation for cutoff pair requirements.
2. Extend source repository schema validation and query generation to support optional cutoff filtering.
3. Thread cutoff parameters from CLI to orchestrator/repository entry points.
4. Add/adjust tests for parser validation, source selection behavior, and `--limit` interaction.
5. Update README examples with cutoff-enabled `index` invocations.

Rollback: remove the two new `index` flags and restore existing source query path without cutoff predicates.

## Open Questions

- Should invalid/non-parseable non-null source values in cutoff column be counted in explicit skip metrics, or remain implicitly excluded by SQL predicate evaluation?
