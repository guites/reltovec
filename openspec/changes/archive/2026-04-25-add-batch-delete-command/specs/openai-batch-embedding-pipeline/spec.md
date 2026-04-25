## ADDED Requirements

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
