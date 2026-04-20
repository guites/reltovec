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
The application MUST submit embedding jobs through the OpenAI Batch API, persist batch lifecycle metadata, and persist submitted work identities so already indexed work cannot be submitted again regardless of current batch status.

#### Scenario: Persist submitted batch metadata
- **WHEN** a batch is created successfully
- **THEN** the system SHALL store `batch_id`, `status`, `input_file_id`, and submission timestamp in SQLite metadata tables

#### Scenario: Persist submitted work identities for duplicate prevention
- **WHEN** a batch input is accepted for submission
- **THEN** the system SHALL record each submitted deterministic work identity (`custom_id`) in state storage for future eligibility checks

#### Scenario: Reject duplicate work identities from later index invocations
- **WHEN** a later `index` invocation produces work that includes any already-recorded `custom_id`
- **THEN** the system SHALL prevent that duplicate work from being included in newly submitted batch payloads, independent of tracked batch lifecycle status

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

### Requirement: Status command reconciles tracked batches
The application SHALL reconcile tracked batch lifecycle state with the OpenAI Batch API when `status` is invoked, and SHALL finalize newly terminal tracked batches before returning status output.

#### Scenario: Refresh status for tracked in-flight batches
- **WHEN** `status` runs and tracked batches exist in non-terminal states
- **THEN** the system SHALL retrieve each tracked in-flight batch from OpenAI and persist the latest `status`, `output_file_id`, `error_file_id`, and completion timestamp in state storage

#### Scenario: Finalize newly terminal batches during status
- **WHEN** reconciliation during `status` detects a tracked batch that is terminal and not yet processed
- **THEN** the system SHALL parse output and error files, upsert successful embeddings, persist item failures, and mark the batch as processed before returning the status response

#### Scenario: Status refresh does not submit new work
- **WHEN** `status` performs reconciliation
- **THEN** the system SHALL NOT read source documents for planning, upload batch input files, or create new OpenAI batch jobs

