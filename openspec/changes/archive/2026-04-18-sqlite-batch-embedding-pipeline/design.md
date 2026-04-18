## Context

The change introduces a Python 3.12 indexing pipeline that reads documents from SQLite, produces embeddings through the OpenAI Batch API, and stores vectors in a local ChromaDB instance running in Docker. The system must remain simple to operate in local/dev workflows while still being resilient enough to resume interrupted indexing runs.

The key functional constraints are:
- Embeddings must be traceable to relational document identifiers.
- A single document may have embeddings from multiple models.
- Batch processing must be the embedding strategy (not synchronous per-document API calls).
- The solution should prioritize maintainability and testability over high operational complexity.

## Goals / Non-Goals

**Goals:**
- Provide a clear ingest → batch → persist flow with minimal moving parts.
- Support configurable embedding model fan-out per document.
- Persist embeddings so they can be retrieved by relational document ID and model.
- Keep components independently testable with mockable boundaries.
- Run ChromaDB locally via Docker for deterministic developer setup.

**Non-Goals:**
- Real-time indexing latency guarantees.
- Distributed workers, queue brokers, or horizontal scaling concerns.
- Automatic schema inference across arbitrary SQLite layouts.
- Hybrid search/reranking features beyond embedding storage and ID-based lookup.

## Decisions

### 1. Use layered modules with explicit ports
- Decision: Split into small modules: `config`, `sqlite_source`, `batch_builder`, `batch_client`, `batch_result_parser`, `vector_store`, and `orchestrator`.
- Rationale: Keeps business rules isolated from external SDK concerns, enabling fast unit tests and easier maintenance.
- Alternative considered: Single script with inline API calls and DB writes. Rejected because it couples concerns and makes testing brittle.

### 2. Represent each embedding unit as `(document_id, model)`
- Decision: For each source document and each configured model, generate one embedding request with deterministic `custom_id` (e.g., `doc:<id>|model:<name>`).
- Rationale: This makes batch outputs directly mappable back to relational identifiers and model variants.
- Alternative considered: One request per document with one model only. Rejected because multi-model support is a hard requirement.

### 3. Use OpenAI Batch API for all embedding generation
- Decision: Build JSONL requests targeting `/v1/embeddings`, upload input file, create batch, poll status, then read output file and parse embeddings.
- Rationale: Aligns directly with requirement and reduces request-level orchestration complexity.
- Alternative considered: Direct synchronous embedding calls. Rejected because it violates required batch strategy.

### 4. Store vectors in one Chroma collection with metadata filters
- Decision: Use one collection (e.g., `document_embeddings`) and store metadata fields: `document_id`, `model`, `source_table`, `updated_at` (if available).
- Rationale: Simplifies query path for “all embeddings for document X” and avoids managing N collections by model.
- Alternative considered: One Chroma collection per model. Rejected because it increases operational branching and query complexity when retrieving all model variants for a document.

### 5. Deterministic vector IDs and idempotent upserts
- Decision: Use vector IDs derived from `(document_id, model)` (e.g., `doc:<id>|model:<name>`) and upsert into Chroma.
- Rationale: Re-runs safely overwrite prior vectors and keep state consistent.
- Alternative considered: Random IDs with dedup logic. Rejected due to unnecessary complexity and weaker repeatability.

### 6. Persist batch run metadata in SQLite
- Decision: Store batch tracking rows (batch_id, status, created_at, completed_at, input_file_id, output_file_id, error_file_id) in a local table.
- Rationale: Enables resume/retry diagnostics without introducing a new state store.
- Alternative considered: In-memory state only. Rejected because interruptions would lose visibility and recovery information.

### 7. Keep local runtime simple with Docker Compose for Chroma
- Decision: Provide `docker compose` service for ChromaDB with a named volume and a small healthcheck script.
- Rationale: Consistent local setup and easy reset while preserving data when needed.
- Alternative considered: Embedded/in-process vector DB mode only. Rejected because requirement explicitly targets ChromaDB in Docker.

## Risks / Trade-offs

- [Batch completion latency can be high] -> Mitigation: document asynchronous operation expectations and provide a status command with batch/job visibility.
- [Large SQLite datasets may produce very large JSONL files] -> Mitigation: support configurable chunking to multiple batches by max request count.
- [Model upgrades may change embedding dimensions] -> Mitigation: keep `model` in metadata and avoid assuming a global dimension across models.
- [Potential mismatch between source row updates and completed batches] -> Mitigation: include source version metadata (`updated_at`/hash) and re-run indexing for changed rows.
- [Local Chroma container downtime] -> Mitigation: fail fast with clear health-check errors and keep batch output parsing/persistence retryable.

## Migration Plan

1. Add Python package structure, dependencies, and configuration scaffolding.
2. Add Docker Compose file and startup docs for local ChromaDB.
3. Implement SQLite source reader and batch request builder.
4. Implement Batch API client and batch status/result retrieval.
5. Implement Chroma upsert/query service with deterministic IDs and metadata.
6. Wire orchestrator CLI commands: `index`, `status`, and `get-by-document-id`.
7. Add tests (unit first, integration second) and sample fixture data.
8. Rollout locally in dry-run mode, then real API mode.

Rollback strategy:
- Stop index runs.
- Clear Chroma collection (or volume) for this app namespace.
- Remove new SQLite metadata tables if needed.
- Revert package/deployment changes via source control.

## Open Questions

- Should the source SQLite schema be fixed (`documents(id, content, updated_at)`) or configurable table/column mappings from config?
- What is the expected behavior for deleted source documents (hard delete vectors vs retain tombstones)?
- Is query output expected to return raw vectors, metadata-only, or both by default?
