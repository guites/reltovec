# sqlite-document-ingestion Specification

## Purpose
TBD - created by archiving change sqlite-batch-embedding-pipeline. Update Purpose after archive.
## Requirements
### Requirement: SQLite document source loading
The application MUST load source documents from SQLite using configured table and column mappings for document identifier and content, where `content_column` is an ordered list of source columns whose values are concatenated into a single `content` string.

#### Scenario: Load valid source rows with multi-column content
- **WHEN** the configured SQLite table exists and all configured identifier/content columns exist
- **THEN** the system SHALL return document records with normalized `document_id` and a single `content` value produced by concatenating configured `content_column` values in order

#### Scenario: Apply deterministic separator between content columns
- **WHEN** multiple `content_column` values are composed for one row
- **THEN** the system SHALL place the configured code-level separator (default `"\n\n"`) between adjacent column values in the resulting `content`

#### Scenario: Reject invalid source mapping
- **WHEN** the configured table is missing or any required identifier/content column is missing
- **THEN** the system SHALL fail fast with a clear configuration error describing the missing schema elements

### Requirement: Document eligibility and model fan-out planning
The application MUST create embedding work units by combining each eligible document with every configured embedding model, while selecting only documents that have not been indexed before and respecting the invocation document limit.

#### Scenario: Create model fan-out units for newly eligible documents
- **WHEN** one unseen document is selected and three embedding models are configured
- **THEN** the system SHALL produce three distinct work units sharing the same `document_id` and different `model` values

#### Scenario: Exclude previously indexed documents regardless of batch status
- **WHEN** a document already has deterministic work identities recorded from any prior batch status (`in_progress`, `finalizing`, `completed`, `failed`, `cancelled`, or `expired`)
- **THEN** the system SHALL exclude that document from the new indexing selection

#### Scenario: Apply invocation limit to documents before fan-out
- **WHEN** `index --limit 5000` is executed and more than 5000 unseen documents are available
- **THEN** the system SHALL select exactly 5000 unseen documents for this invocation and fan out only those selected documents across configured models

#### Scenario: Select documents in deterministic order across repeated runs
- **WHEN** `index --limit N` is run repeatedly without source data changes
- **THEN** each run SHALL process the next unseen documents in stable source ordering without reselecting already indexed documents

### Requirement: Stable work identifiers
The application MUST assign deterministic work identifiers derived from `document_id` and `model`.

#### Scenario: Regenerate deterministic identifier
- **WHEN** the same `document_id` and `model` pair is processed in a later run
- **THEN** the system SHALL generate the same identifier value to support idempotent persistence

