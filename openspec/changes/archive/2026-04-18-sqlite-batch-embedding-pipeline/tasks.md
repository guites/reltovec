## 1. Project Setup

- [x] 1.1 Initialize Python 3.12 project structure and dependency management for `openai`, `chromadb`, and testing libraries
- [x] 1.2 Add configuration loading for SQLite path, source table/column mapping, embedding model list, and Chroma connection settings
- [x] 1.3 Add Docker Compose configuration for local ChromaDB with persistent volume and a basic health-check command

## 2. SQLite Ingestion Capability

- [x] 2.1 Implement SQLite document repository that validates configured table/columns before reading rows
- [x] 2.2 Implement document normalization and empty-content filtering with skip-reason counters
- [x] 2.3 Implement model fan-out planner that expands each eligible document into `(document_id, model, content)` work units
- [x] 2.4 Implement deterministic work/custom ID generation from `document_id` and `model`

## 3. OpenAI Batch Embedding Capability

- [x] 3.1 Implement JSONL batch input builder for `/v1/embeddings` requests with deterministic `custom_id`
- [x] 3.2 Implement Batch API client adapter for input file upload, batch creation, and status polling
- [x] 3.3 Implement SQLite metadata table migrations for batch job tracking and run status persistence
- [x] 3.4 Implement batch terminal-state handling that stores output/error file identifiers
- [x] 3.5 Implement batch output parser that maps successful results back to `document_id` and `model`
- [x] 3.6 Implement per-item failure capture from error outputs without blocking successful result processing

## 4. Chroma Storage and ID Query Capability

- [x] 4.1 Implement Chroma collection initialization for `document_embeddings`
- [x] 4.2 Implement idempotent upsert with deterministic vector IDs and metadata (`document_id`, `model`, source metadata)
- [x] 4.3 Implement query service to fetch all embeddings by `document_id`
- [x] 4.4 Implement query service filtering by `document_id` and `model`

## 5. Orchestration and CLI

- [x] 5.1 Implement `index` command to run ingest -> batch submit/poll -> parse -> Chroma upsert flow
- [x] 5.2 Implement `status` command to display tracked batch job lifecycle from SQLite metadata
- [x] 5.3 Implement `get-by-document-id` command to return stored embeddings (all models or filtered model)
- [x] 5.4 Implement resumable execution behavior for interrupted runs using persisted batch metadata

## 6. Tests and Documentation

- [x] 6.1 Add unit tests for schema validation, fan-out planning, and deterministic ID generation
- [x] 6.2 Add unit tests for JSONL request construction and batch output parsing
- [x] 6.3 Add tests for Chroma upsert idempotency and metadata-based query behavior
- [x] 6.4 Add orchestrator tests using mocked OpenAI and Chroma adapters
- [x] 6.5 Add developer documentation for local setup, environment variables, and end-to-end indexing/query workflow
