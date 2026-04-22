## Context

`index` currently loads all normalized SQLite documents, fans out work items per configured model, and submits all resulting work in chunks of `batch.max_batch_size`. There is no invocation-level document cap and no persistent ledger of submitted work-item identities, so repeated `index` calls can re-submit already-indexed documents.

The code path is:
- CLI argument parsing in `src/reltovec/cli.py`
- orchestration and batch submission in `src/reltovec/orchestrator.py`
- work-item fan-out/chunking in `src/reltovec/planner.py`
- batch state persistence in `src/reltovec/state_store.py`

## Goals / Non-Goals

**Goals:**
- Allow `index --limit <n>` to cap the number of source documents processed in that invocation.
- Keep `--limit` semantics independent from `batch.max_batch_size` (documents vs. per-batch work-item chunk size).
- Prevent duplicate batching by excluding already-indexed work from new submissions regardless of batch status.
- Keep repeated runs incremental and deterministic (e.g., repeated `index --limit 5000` progresses to unseen documents).

**Non-Goals:**
- Rebuild or reindex previously indexed documents as part of this change.
- Change OpenAI Batch API payload format or Chroma persistence behavior.
- Introduce distributed locking across multiple concurrent processes.

## Decisions

### 1. Add invocation-level limit to the `index` command
`index` will accept `--limit` as a positive integer for source documents to process in that run. The parsed value is passed into orchestrator logic.

Rationale:
- Matches user intent for repeated incremental indexing in fixed-size chunks.
- Decouples operator control (`--limit`) from transport chunking (`max_batch_size`).

Alternatives considered:
- Reusing `max_batch_size` for both purposes. Rejected because batch sizing and per-run scope are separate concerns.

### 2. Track indexed work identities in state DB and use them as eligibility guard
Add a persisted work-item ledger in state storage keyed by deterministic `custom_id` (`document_id + model`). This ledger records work that has already been submitted at least once. New runs check this ledger before submission and skip known items regardless of batch lifecycle status.

Rationale:
- The current `embedding_batches` table tracks batch lifecycle but not which items were included.
- `custom_id` is deterministic and already the pipeline identity key.
- Status-agnostic exclusion directly satisfies the requirement.

Alternatives considered:
- Filtering only by terminal statuses. Rejected because requirement explicitly includes non-terminal statuses.
- Querying ChromaDB for existing vectors only. Rejected because items may already be submitted but not yet materialized in Chroma.

### 3. Apply limit at document-selection stage, before model fan-out
Selection algorithm:
1. Load and normalize source documents.
2. Build candidate work identities per configured model.
3. Exclude documents whose generated work identities are already known in the ledger.
4. Take the first `limit` eligible documents in deterministic source order.
5. Fan out selected documents to work items and chunk by `max_batch_size` for batch submissions.

Rationale:
- Preserves user-facing meaning of `--limit` as number of documents, not work items.
- Retains existing batch chunking behavior after selection.

Alternatives considered:
- Limiting post fan-out work-item count. Rejected because it yields variable document counts and violates the requested semantics.

### 4. Deterministic ordering for incremental runs
Document loading should use a stable ordering (by configured ID column ascending) so repeated calls select the next unseen slice predictably.

Rationale:
- Without ordering, SQLite row return order can vary and produce unstable incremental windows.

Alternatives considered:
- Relying on implicit table order. Rejected due nondeterministic behavior.

## Risks / Trade-offs

- [Large ledgers can grow over time] -> Mitigation: index `custom_id` as primary key and keep lookup queries set-based.
- [Existing deployments need schema migration] -> Mitigation: add additive migration only (`CREATE TABLE IF NOT EXISTS`), no destructive changes.
- [Concurrent `index` invocations can race] -> Mitigation: enforce uniqueness at persistence layer (`custom_id` unique) and skip duplicates when conflict is detected.
- [Model list changes across runs alter eligibility] -> Mitigation: base eligibility on `custom_id` so new model combinations remain indexable when their identity is new.

## Migration Plan

1. Extend CLI parser to support `index --limit`.
2. Add state-store migration for indexed work ledger table.
3. Add state-store APIs for querying known identities and recording newly submitted identities.
4. Update orchestrator selection flow to filter/limit documents incrementally and record submitted identities.
5. Add/adjust tests for limit semantics, duplicate prevention, deterministic selection, and status-agnostic exclusion.
6. Rollback path: code rollback is safe because migration is additive; legacy code can ignore the extra table.

## Open Questions

- Should `--limit` have a default (e.g., unlimited) or require explicit user input?
- If a document has mixed identity state (some models already seen, some new), should the run skip the full document or submit only unseen model identities?
