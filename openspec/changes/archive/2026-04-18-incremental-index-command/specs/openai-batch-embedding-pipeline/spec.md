## MODIFIED Requirements

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
