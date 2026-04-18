## ADDED Requirements

### Requirement: SQLite document source loading
The application MUST load source documents from SQLite using configured table and column mappings for document identifier and content.

#### Scenario: Load valid source rows
- **WHEN** the configured SQLite table and columns exist and contain valid rows
- **THEN** the system SHALL return document records with normalized `document_id` and `content` fields for downstream embedding work

#### Scenario: Reject invalid source mapping
- **WHEN** configured table or required columns are missing
- **THEN** the system SHALL fail fast with a clear configuration error describing the missing schema elements

### Requirement: Document eligibility and model fan-out planning
The application MUST create embedding work units by combining each eligible document with every configured embedding model.

#### Scenario: Create model fan-out units
- **WHEN** one document is loaded and three embedding models are configured
- **THEN** the system SHALL produce three distinct work units sharing the same `document_id` and different `model` values

#### Scenario: Skip empty-content rows
- **WHEN** a source row has null or whitespace-only content
- **THEN** the system SHALL exclude the row from embedding work and record the skip reason in run statistics

### Requirement: Stable work identifiers
The application MUST assign deterministic work identifiers derived from `document_id` and `model`.

#### Scenario: Regenerate deterministic identifier
- **WHEN** the same `document_id` and `model` pair is processed in a later run
- **THEN** the system SHALL generate the same identifier value to support idempotent persistence
