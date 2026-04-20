## ADDED Requirements

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
