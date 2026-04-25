# reltovec

Simple Python 3.12 pipeline that:

1. Reads documents from SQLite.
2. Creates embeddings using the OpenAI Batch API.
3. Stores vectors in ChromaDB running in Docker.
4. Queries vectors by relational `document_id` and optional `model`.

## Requirements

- Python 3.12+
- Docker + Docker Compose
- OpenAI API key in environment: `OPENAI_API_KEY`

## Local Setup

### 1. Start ChromaDB

```bash
docker compose up -d chromadb
```

### 2. Create your config from the example

```bash
cp config.example.toml config.toml
```

### 3. Ensure your SQLite source DB exists with expected columns (default)

- table: `documents`
- id column: `id`
- content columns: `["content"]`

### 4. Run indexing

```bash
uv run reltovec --config config.toml index
```

An additional `--no-wait` flag can be passed to return immediately
(instead of waiting for batch processing completion).

To index incrementally in fixed-size document slices:

```bash
uv run reltovec --config config.toml index --limit 5000 --no-wait
uv run reltovec --config config.toml index --limit 5000 --no-wait
```

Each run selects the next unseen document set and does not re-batch previously indexed documents.

To index only rows at or after a specific source date/datetime column:

```bash
uv run reltovec --config config.toml index --cutoff-column updated_at --cutoff-value 2026-01-01
uv run reltovec --config config.toml index --cutoff-column published_at --cutoff-value 2026-01-01T08:55:10 --limit 5000 --no-wait
```

`--cutoff-value` accepts only `YYYY-MM-DD` or `YYYY-MM-DDTHH:MM:SS`. Date-only values are interpreted as midnight (`T00:00:00`).
Rows with `NULL` values in the selected cutoff column are skipped.

## Commands

### Show tracked batch state

```bash
uv run reltovec --config config.toml status
```

Output from `status` can be filtered using `jq`, for example:

```bash
uv run reltovec --config config.toml status | jq '.[] | select(.documents_sent_count != 0)'
uv run reltovec --config config.toml status | jq '.[] | select(.status != "completed")'
```

### Query embeddings by document id

```bash
uv run reltovec --config config.toml get-by-document-id 123
```

Filter by model:

```bash
uv run reltovec --config config.toml get-by-document-id 123 --model text-embedding-3-small
```

Metadata-only output:

```bash
uv run reltovec --config config.toml get-by-document-id 123 --no-embeddings
```

### Purge work itens by error code

```bash
uv run reltovec --config config.toml purge --error-code invalid_request
```

## Notes on Resumability

- Batch lifecycle is tracked in a local SQLite state DB (`[state].tracking_db_path`).
- On each `index` run, the orchestrator first resumes unfinished batches and finalizes unprocessed terminal batches, then submits new work.

## Running Tests

```bash
uv run pytest
```

## Linting and formating

```bash
uv run ruff check --fix
uv run ruff format
```
