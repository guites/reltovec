## MODIFIED Requirements

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
