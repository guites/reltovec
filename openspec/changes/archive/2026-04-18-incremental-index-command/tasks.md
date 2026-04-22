## 1. CLI And Contract Updates

- [x] 1.1 Add `index --limit` argument parsing in `src/reltovec/cli.py` with positive-integer validation and pass the value into `IndexOrchestrator.index(...)`.
- [x] 1.2 Extend orchestrator/index method contracts and summary fields as needed to represent invocation limit behavior and skipped already-indexed documents.

## 2. State Tracking For Duplicate Prevention

- [x] 2.1 Add additive SQLite migration in `src/reltovec/state_store.py` for a submitted work-identity ledger keyed by deterministic `custom_id`.
- [x] 2.2 Implement state-store APIs to query known `custom_id` values for candidate work and to persist newly submitted identities during batch submission.
- [x] 2.3 Ensure duplicate identity writes are handled safely (status-agnostic prevention across terminal and non-terminal batch states).

## 3. Incremental Selection And Submission Flow

- [x] 3.1 Update source selection/planning flow so `index` uses deterministic document ordering and applies `--limit` to documents before model fan-out.
- [x] 3.2 Filter candidate work using the state-store identity ledger so previously indexed documents are excluded from new submissions.
- [x] 3.3 Keep `batch.max_batch_size` behavior unchanged for chunking selected work into OpenAI batch payloads after limit/eligibility filtering.
- [x] 3.4 Record submitted work identities alongside batch submissions so repeated invocations progress to new document sets.

## 4. Verification

- [x] 4.1 Add unit tests for CLI/orchestrator limit semantics to confirm `--limit` is per invocation and independent from `max_batch_size`.
- [x] 4.2 Add tests for repeated `index --limit N` runs to confirm no re-batching of already indexed documents, regardless of batch status.
- [x] 4.3 Add/adjust state-store tests covering migration and duplicate-prevention lookup behavior.
- [x] 4.4 Run project test suite and update docs/help text examples to include incremental usage (e.g., repeated `index --limit 5000`).
