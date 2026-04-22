## Context

The current ingestion path accepts an optional `sqlite.updated_at_column`, validates that column in the source schema, and propagates its value across in-memory models. The value does not influence indexing eligibility, deterministic ordering, duplicate prevention, batching, or reconciliation. This creates extra configuration and model fields without corresponding control-flow value.

## Goals / Non-Goals

**Goals:**
- Remove `updated_at_column` from configuration and ingestion abstractions.
- Simplify source schema validation to only require `id_column` and `content_column` mappings.
- Preserve indexing behavior and output semantics for existing commands.
- Keep migration straightforward for existing users with minimal required config edits.

**Non-Goals:**
- Introduce date-based source filtering in this change.
- Alter batch payload shape, Chroma query semantics, or duplicate-prevention logic.
- Rework unrelated configuration surfaces.

## Decisions

### Decision: Remove `updated_at_column` from config and models
- Rationale: It is unused in decision-making paths and increases maintenance burden.
- Alternative considered: Keep it for possible future features.
  - Rejected because future features can add targeted fields when requirements exist; speculative abstraction has current cost.

### Decision: Keep ingestion requirements centered on ID/content mapping only
- Rationale: Existing normative behavior is based on valid table/id/content mappings and deterministic ordering.
- Alternative considered: Keep optional timestamp validation for "data quality" checks.
  - Rejected because this couples ingestion to unrelated source columns and causes avoidable configuration failures.

### Decision: Treat removal as a narrow config migration
- Rationale: Users only need to delete one key (`sqlite.updated_at_column`) from config files.
- Alternative considered: Support deprecated key for one release.
  - Rejected to avoid carrying compatibility complexity for a non-essential field.

## Risks / Trade-offs

- [Risk] Existing configs containing `sqlite.updated_at_column` will fail after removal if parser becomes strict. -> Mitigation: document explicit migration step and update example config/README in the same change.
- [Risk] Future date-filtering work may need a new source timestamp abstraction. -> Mitigation: introduce purpose-built filtering fields when requirements are accepted, rather than retaining unused generic fields now.
- [Trade-off] Slightly less source metadata preserved in internal objects. -> Mitigation: no current control-flow or spec requirement depends on it.

## Migration Plan

1. Remove `updated_at_column` from `config.example.toml` and docs.
2. Update config parsing and source model code to drop the field.
3. Update tests/fixtures that currently include `updated_at_column` in generated config.
4. Communicate operator action: delete `sqlite.updated_at_column` from existing config files.

Rollback: reintroduce the config key and model passthrough if unexpected integrations depend on it.

## Open Questions

- Should config loading ignore unknown keys (for softer migration) or fail on stale `updated_at_column` (for stricter hygiene)?
- Should a follow-up change immediately introduce a generic `--since`/date filter abstraction, or keep this change isolated to simplification?
