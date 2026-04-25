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
The application MUST submit embedding jobs through the OpenAI Batch API, persist batch lifecycle metadata, and persist submitted work identities so previously submitted work is excluded from later `index` runs until explicitly purged.

#### Scenario: Persist submitted batch metadata
- **WHEN** a batch is created successfully
- **THEN** the system SHALL store `batch_id`, `status`, `input_file_id`, and submission timestamp in SQLite metadata tables

#### Scenario: Persist submitted work identities for duplicate prevention
- **WHEN** a batch input is accepted for submission
- **THEN** the system SHALL record each submitted deterministic work identity (`custom_id`) in state storage for future eligibility checks

#### Scenario: Reject duplicate work identities from later index invocations
- **WHEN** a later `index` invocation produces work that includes any recorded, non-purged `custom_id`
- **THEN** the system SHALL prevent that duplicate work from being included in newly submitted batch payloads, independent of tracked batch lifecycle status

#### Scenario: Purged failed work identities become eligible for re-enqueue
- **WHEN** failures for a `custom_id` are purged using `purge --error-code` and that `custom_id` is removed from `indexed_work_items`
- **THEN** a later `index` invocation SHALL treat that work identity as eligible for submission if source selection criteria still match

#### Scenario: Track terminal batch status
- **WHEN** polling reaches a terminal state (`completed`, `failed`, or `cancelled`)
- **THEN** the system SHALL persist the terminal status and any output/error file identifiers for later processing

### Requirement: Purge command releases failed work by error code
The application MUST provide a `purge` command with required `--error-code` filtering that removes matching failed-item records and releases corresponding work identities for future `index` runs.

#### Scenario: Purge matching failures and release duplicate-prevention state
- **WHEN** an operator runs `purge --error-code <code>` and failed-item rows exist with that exact `error_code`
- **THEN** the system SHALL delete all matching rows from `embedding_item_failures`
- **THEN** the system SHALL delete matching `indexed_work_items` rows for distinct non-null `custom_id` values from those deleted failures
- **THEN** the command output SHALL include counts for deleted failure rows and released work identities

#### Scenario: Purge is scoped to the requested error code
- **WHEN** `purge --error-code <code>` is executed
- **THEN** the system SHALL NOT delete `embedding_item_failures` rows with different `error_code` values
- **THEN** the system SHALL NOT delete `indexed_work_items` rows unrelated to failures matching `<code>`

#### Scenario: Purge handles missing matches as a no-op
- **WHEN** `purge --error-code <code>` is executed and no failures match `<code>`
- **THEN** the command SHALL complete successfully
- **THEN** the reported deleted failure row count and released work identity count SHALL both be `0`

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

#### Scenario: Status includes per-batch failure summary
- **WHEN** `status` returns tracked batch records
- **THEN** each batch record SHALL include failed embedding item count and a list of distinct failure `error_code` values for that batch
- **THEN** failure summary values SHALL reflect finalized state, including batches finalized during the same `status` invocation

### Requirement: Delete command removes batch-scoped state by batch identifier
The application MUST provide a `delete` command that accepts a required `batch_id` argument and removes all persisted state associated with that batch from `embedding_item_failures`, `indexed_work_items`, and batch tracking metadata.

#### Scenario: Delete existing batch and related state
- **WHEN** an operator runs `delete <batch_id>` for a tracked batch that has associated failures and indexed work identities
- **THEN** the system SHALL delete all `embedding_item_failures` rows associated with `<batch_id>`
- **THEN** the system SHALL delete `indexed_work_items` rows associated with work identities submitted in `<batch_id>`
- **THEN** the system SHALL delete the batch metadata row for `<batch_id>`
- **THEN** command output SHALL include counts for deleted failure rows, released work identities, and deleted batch rows

#### Scenario: Delete is scoped to the requested batch only
- **WHEN** `delete <batch_id>` is executed
- **THEN** the system SHALL NOT delete `embedding_item_failures`, `indexed_work_items`, or batch metadata rows that are not associated with `<batch_id>`

#### Scenario: Missing batch identifier is a no-op
- **WHEN** `delete <batch_id>` is executed and `<batch_id>` does not exist in tracked batch metadata
- **THEN** the command SHALL complete successfully
- **THEN** command output SHALL report `0` deleted failure rows, `0` released work identities, and `0` deleted batch rows

#### Scenario: Delete is atomic
- **WHEN** `delete <batch_id>` encounters a database error during any delete step
- **THEN** the system SHALL roll back all changes for that command invocation
- **THEN** no partial deletions SHALL remain persisted

