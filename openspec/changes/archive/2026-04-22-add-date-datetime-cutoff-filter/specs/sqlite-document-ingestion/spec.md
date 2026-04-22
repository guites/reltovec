## MODIFIED Requirements

### Requirement: SQLite document source loading
The application MUST load source documents from SQLite using configured table and column mappings for document identifier and content, where `content_column` is an ordered list of source columns whose values are concatenated into a single `content` string. The application MUST NOT require a separate timestamp column mapping for ingestion. When cutoff filtering is requested, the selected cutoff column MUST exist in the configured source table.

#### Scenario: Load valid source rows with multi-column content
- **WHEN** the configured SQLite table exists and all configured identifier/content columns exist
- **THEN** the system SHALL return document records with normalized `document_id` and a single `content` value produced by concatenating configured `content_column` values in order

#### Scenario: Apply deterministic separator between content columns
- **WHEN** multiple `content_column` values are composed for one row
- **THEN** the system SHALL place the configured code-level separator (default `"\n\n"`) between adjacent column values in the resulting `content`

#### Scenario: Reject invalid source mapping
- **WHEN** the configured table is missing or any required identifier/content column is missing
- **THEN** the system SHALL fail fast with a clear configuration error describing the missing schema elements

#### Scenario: Do not require timestamp mapping for ingestion
- **WHEN** a configuration omits any timestamp-specific source column mapping
- **THEN** the system SHALL still load and normalize documents as long as table, identifier, and content-column mappings are valid

#### Scenario: Reject missing cutoff column when filtering is requested
- **WHEN** `index` is invoked with a cutoff column that does not exist in the configured source table
- **THEN** the system SHALL fail fast with a clear error naming the missing cutoff column

### Requirement: Document eligibility and model fan-out planning
The application MUST create embedding work units by combining each eligible document with every configured embedding model, while selecting only documents that have not been indexed before and respecting the invocation document limit. Eligibility MUST support an optional user-provided cutoff filter defined by `(cutoff_column, cutoff_value)`, and rows with `NULL` or undefined values in `cutoff_column` MUST be excluded before duplicate-prevention and limit selection.

#### Scenario: Create model fan-out units for newly eligible documents
- **WHEN** one unseen document is selected and three embedding models are configured
- **THEN** the system SHALL produce three distinct work units sharing the same `document_id` and different `model` values

#### Scenario: Exclude previously indexed documents regardless of batch status
- **WHEN** a document already has deterministic work identities recorded from any prior batch status (`in_progress`, `finalizing`, `completed`, `failed`, `cancelled`, or `expired`)
- **THEN** the system SHALL exclude that document from the new indexing selection

#### Scenario: Apply invocation limit after cutoff filtering and duplicate prevention
- **WHEN** `index --limit 5000` is executed with an active cutoff filter and more than 5000 unseen, cutoff-eligible documents are available
- **THEN** the system SHALL select exactly 5000 unseen cutoff-eligible documents for this invocation and fan out only those selected documents across configured models

#### Scenario: Select documents in deterministic order across repeated runs
- **WHEN** `index --limit N` is run repeatedly without source data changes
- **THEN** each run SHALL process the next unseen documents in stable source ordering without reselecting already indexed documents

#### Scenario: Apply date-only cutoff value
- **WHEN** `index` is invoked with cutoff value `YYYY-MM-DD`
- **THEN** the system SHALL interpret the cutoff as midnight (`YYYY-MM-DDT00:00:00`) for source eligibility comparison

#### Scenario: Apply datetime cutoff value
- **WHEN** `index` is invoked with cutoff value `YYYY-MM-DDTHH:MM:SS`
- **THEN** the system SHALL include only rows whose selected cutoff-column value is greater than or equal to that datetime

#### Scenario: Skip rows with null or undefined cutoff values
- **WHEN** cutoff filtering is enabled and a row has `NULL` or undefined value in the selected cutoff column
- **THEN** the system SHALL exclude that row from indexing eligibility

#### Scenario: Reject unsupported cutoff format
- **WHEN** `index` is invoked with cutoff value not matching `YYYY-MM-DD` or `YYYY-MM-DDTHH:MM:SS`
- **THEN** the command SHALL fail fast with a validation error describing accepted cutoff formats
