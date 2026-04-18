## Why

We need a simple, maintainable pipeline that turns documents stored in SQLite into searchable embeddings in a local vector store. This enables deterministic offline-friendly indexing and retrieval by relational identifiers while supporting multiple embedding models per document.

## What Changes

- Add a Python 3.12 application that reads source documents from SQLite and submits embedding work via the OpenAI Batch API.
- Add ingestion flow that supports generating and storing multiple embeddings per document, one per configured embedding model.
- Add persistence flow that writes embedding vectors and metadata into ChromaDB running in Docker.
- Add query capabilities to retrieve embeddings by relational database document identifier and embedding model.
- Add configuration, test strategy, and operational scripts focused on low complexity, maintainability, and testability.

## Capabilities

### New Capabilities
- `sqlite-document-ingestion`: Read documents from SQLite with stable identifiers and content fields for embedding jobs.
- `openai-batch-embedding-pipeline`: Build, submit, track, and resolve OpenAI Batch API jobs for one or more embedding models per document.
- `chromadb-storage-and-id-query`: Persist vectors and metadata in ChromaDB and query results by SQLite document identifier.

### Modified Capabilities
- None.

## Impact

- New Python modules for configuration, SQLite access, batch orchestration, vector persistence, and query services.
- New Docker Compose setup for local ChromaDB.
- New tests (unit and integration-style with fakes/mocks) for ingestion, batch lifecycle handling, model fan-out, and query semantics.
- Uses OpenAI API and ChromaDB dependencies; no breaking changes to existing capabilities.
