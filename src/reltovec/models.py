from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class DocumentRecord:
    document_id: str
    content: str
    source_table: str


@dataclass(frozen=True)
class EmbeddingWorkItem:
    document_id: str
    model: str
    content: str
    custom_id: str
    source_table: str


@dataclass(frozen=True)
class BatchJobRecord:
    batch_id: str
    status: str
    input_file_id: str
    output_file_id: str | None = None
    error_file_id: str | None = None
    submitted_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    completed_at: str | None = None
    documents_sent_count: int = 0
    failed_item_count: int = 0
    failure_error_codes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ParsedEmbedding:
    custom_id: str
    document_id: str
    model: str
    embedding: list[float]
    source_table: str | None = None


@dataclass(frozen=True)
class BatchItemFailure:
    custom_id: str | None
    error_code: str | None
    error_message: str


@dataclass(frozen=True)
class ParsedBatchResults:
    embeddings: list[ParsedEmbedding]
    item_failures: list[BatchItemFailure]


@dataclass(frozen=True)
class NormalizationStats:
    total_rows: int
    normalized_rows: int
    skipped_empty_content: int
    skipped_missing_id: int


@dataclass(frozen=True)
class IndexSummary:
    total_documents_seen: int
    eligible_documents: int
    skipped_empty_content: int
    skipped_missing_id: int
    submitted_batches: int
    processed_batches: int
    upserted_embeddings: int
    item_failures: int
    requested_document_limit: int | None = None
    selected_documents_for_indexing: int = 0
    skipped_already_indexed_documents: int = 0


@dataclass(frozen=True)
class ReconciliationSummary:
    processed_batches: int
    upserted_embeddings: int
    item_failures: int
    batches: list[BatchJobRecord] = field(default_factory=list)


@dataclass(frozen=True)
class PurgeSummary:
    error_code: str
    deleted_failures: int
    released_work_items: int


@dataclass(frozen=True)
class QueryRow:
    vector_id: str
    document_id: str
    model: str
    embedding: list[float] | None
    metadata: dict[str, Any]
