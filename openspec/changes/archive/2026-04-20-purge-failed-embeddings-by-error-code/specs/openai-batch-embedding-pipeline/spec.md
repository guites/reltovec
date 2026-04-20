## ADDED Requirements

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

## MODIFIED Requirements

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
