# chromadb-storage-and-id-query Specification

## Purpose
TBD - created by archiving change sqlite-batch-embedding-pipeline. Update Purpose after archive.
## Requirements
### Requirement: Deterministic vector persistence
The application MUST upsert embeddings into ChromaDB using deterministic vector IDs derived from `document_id` and `model`.

#### Scenario: Upsert replaces prior embedding for same identity
- **WHEN** an embedding for an existing `(document_id, model)` pair is persisted again
- **THEN** the system SHALL overwrite the prior vector entry for that deterministic ID rather than creating duplicates

### Requirement: Embedding metadata storage
The application MUST store metadata with each vector that includes relational `document_id` and embedding `model`.

#### Scenario: Persist queryable metadata fields
- **WHEN** an embedding vector is written to ChromaDB
- **THEN** the system SHALL include metadata fields that allow filtering by `document_id` and `model`

### Requirement: Query by relational identifier
The application MUST provide a query operation to retrieve embeddings by relational document identifier.

#### Scenario: Fetch all embeddings for a document
- **WHEN** a caller queries with a known `document_id` and no model filter
- **THEN** the system SHALL return all embeddings stored for that document across configured models

#### Scenario: Fetch embeddings for a document and model
- **WHEN** a caller queries with both `document_id` and `model`
- **THEN** the system SHALL return only the embedding entries matching both metadata values

