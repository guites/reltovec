# openai-batch-embedding-pipeline Specification

## Purpose
TBD - created by archiving change sqlite-batch-embedding-pipeline. Update Purpose after archive.
## Requirements
### Requirement: Embedding batch request generation
The application MUST generate JSONL batch input lines targeting the embeddings endpoint and include a deterministic `custom_id` for each work unit.

#### Scenario: Build valid embeddings batch line
- **WHEN** a work unit `(document_id, model, content)` is prepared for submission
- **THEN** the system SHALL write a JSON object with method `POST`, URL `/v1/embeddings`, request body containing `model` and `input`, and the work unit `custom_id`

### Requirement: Batch submission and tracking
The application MUST submit embedding jobs through the OpenAI Batch API and persist batch lifecycle metadata.

#### Scenario: Persist submitted batch metadata
- **WHEN** a batch is created successfully
- **THEN** the system SHALL store `batch_id`, `status`, `input_file_id`, and submission timestamp in SQLite metadata tables

#### Scenario: Track terminal batch status
- **WHEN** polling reaches a terminal state (`completed`, `failed`, or `cancelled`)
- **THEN** the system SHALL persist the terminal status and any output/error file identifiers for later processing

### Requirement: Output parsing and failure handling
The application MUST parse completed batch output files into embedding records and handle per-item failures without corrupting successful results.

#### Scenario: Parse successful embedding output rows
- **WHEN** a completed batch output file includes successful embedding responses
- **THEN** the system SHALL emit normalized records containing `document_id`, `model`, `embedding`, and `custom_id`

#### Scenario: Record failed output items
- **WHEN** a completed batch includes failed items or an error file
- **THEN** the system SHALL record failure details associated with the corresponding `custom_id` while continuing to process successful items

