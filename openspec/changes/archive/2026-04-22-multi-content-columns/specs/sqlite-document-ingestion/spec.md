## MODIFIED Requirements

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
