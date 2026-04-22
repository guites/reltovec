## Context

Today the ingestion mapping reads a single configured `content_column` from each SQLite row and forwards it as document `content`. Some source schemas split meaningful text across multiple columns (for example title, summary, and body), and current behavior cannot combine them without upstream denormalization. This change expands configuration semantics while preserving downstream DTO shape (`content` remains a single string).

## Goals / Non-Goals

**Goals:**
- Accept `content_column` as an ordered array of SQLite column names.
- Produce deterministic document `content` by concatenating configured column values in order.
- Centralize separator behavior in one constant with default `"\n\n"`.
- Keep downstream interfaces unchanged by passing only the final concatenated `content` string.
- Validate mapping against table schema and fail fast when configured columns are missing.

**Non-Goals:**
- User-configurable separator in `config.toml`.
- Changes to embedding request format or ChromaDB persistence shape.
- Backfill/migration tooling for existing indexed content.

## Decisions

### Decision: Model `content_column` as ordered array input
`content_column` will be interpreted as an ordered list of source columns for each table mapping. Order is significant and defines concatenation order.

Alternatives considered:
- Keep single-column-only behavior: rejected because it does not solve the feature request.
- Introduce a new key (`content_columns`) while preserving old key: rejected for now to avoid dual-path parsing complexity in this change scope.

### Decision: Concatenate during ingestion DTO construction
Concatenation will happen at row-to-document mapping time, and the resulting single string is stored in DTO `content`.

Alternatives considered:
- Concatenate later in embedding pipeline: rejected because it spreads source-mapping semantics outside ingestion and complicates test boundaries.

### Decision: Use one hardcoded separator constant
A code-level constant (default `"\n\n"`) will be used between adjacent column values.

Alternatives considered:
- Configurable separator in TOML: rejected to keep scope small and avoid additional validation surface.
- Inline literal everywhere: rejected because a constant enables quick global changes.

### Decision: Validate all configured content columns upfront
Schema validation will ensure every configured content column exists in the target table before document loading proceeds.

Alternatives considered:
- Best-effort ignore missing columns: rejected because silent content degradation is risky and non-deterministic.

## Risks / Trade-offs

- [Risk] Existing configs that still provide a scalar `content_column` may fail parsing after the type change. -> Mitigation: update examples/tests and provide a clear configuration error message.
- [Risk] Concatenating nullable/empty columns may produce unexpected separators. -> Mitigation: define and test explicit concatenation behavior for empty values in ingestion mapping tests.
- [Trade-off] Hardcoded separator is less flexible short term. -> Mitigation: keep it as a single constant to enable low-effort future configurability.
