from __future__ import annotations

import time

from brcrawl_embedder.batch_builder import build_batch_jsonl
from brcrawl_embedder.batch_client import BatchClient
from brcrawl_embedder.batch_result_parser import parse_batch_results, parse_error_file
from brcrawl_embedder.config import AppConfig
from brcrawl_embedder.ids import make_custom_id
from brcrawl_embedder.models import (
    BatchItemFailure,
    BatchJobRecord,
    DocumentRecord,
    IndexSummary,
    ReconciliationSummary,
)
from brcrawl_embedder.planner import chunk_work_items, plan_work_items
from brcrawl_embedder.sqlite_source import SQLiteDocumentRepository
from brcrawl_embedder.state_store import BatchStateStore, TERMINAL_BATCH_STATUSES
from brcrawl_embedder.vector_store import VectorStore


class IndexOrchestrator:
    def __init__(
        self,
        config: AppConfig,
        source_repo: SQLiteDocumentRepository,
        batch_client: BatchClient,
        state_store: BatchStateStore,
        vector_store: VectorStore,
        sleep_fn=time.sleep,
    ):
        self._config = config
        self._source_repo = source_repo
        self._batch_client = batch_client
        self._state_store = state_store
        self._vector_store = vector_store
        self._sleep = sleep_fn

    def index(
        self,
        wait_for_completion: bool = True,
        document_limit: int | None = None,
    ) -> IndexSummary:
        if document_limit is not None and document_limit <= 0:
            raise ValueError("document_limit must be positive")

        refreshed = self.refresh_status(wait_for_completion=wait_for_completion)
        processed_batches = refreshed.processed_batches
        upserted_embeddings = refreshed.upserted_embeddings
        item_failures = refreshed.item_failures

        documents, normalization_stats = self._source_repo.load_documents()
        selected_documents, skipped_already_indexed = (
            self._select_documents_for_indexing(
                documents=documents,
                document_limit=document_limit,
            )
        )
        work_items = plan_work_items(selected_documents, self._config.batch.models)

        submitted_batch_ids: list[str] = []
        for chunk in chunk_work_items(work_items, self._config.batch.max_batch_size):
            if not chunk:
                continue
            jsonl_payload = build_batch_jsonl(chunk)
            input_file_id = self._batch_client.upload_batch_input(jsonl_payload)
            created_batch = self._batch_client.create_embedding_batch(
                input_file_id=input_file_id,
                completion_window=self._config.batch.completion_window,
            )
            self._state_store.record_batch_submission(created_batch)
            self._state_store.record_submitted_work_items(
                batch_id=created_batch.batch_id,
                custom_ids=[item.custom_id for item in chunk],
            )
            submitted_batch_ids.append(created_batch.batch_id)

        if submitted_batch_ids:
            submitted = self._poll_batches(
                submitted_batch_ids,
                wait_for_completion=wait_for_completion,
            )
            processed_batches += submitted[0]
            upserted_embeddings += submitted[1]
            item_failures += submitted[2]

        return IndexSummary(
            total_documents_seen=normalization_stats.total_rows,
            eligible_documents=normalization_stats.normalized_rows,
            skipped_empty_content=normalization_stats.skipped_empty_content,
            skipped_missing_id=normalization_stats.skipped_missing_id,
            submitted_batches=len(submitted_batch_ids),
            processed_batches=processed_batches,
            upserted_embeddings=upserted_embeddings,
            item_failures=item_failures,
            requested_document_limit=document_limit,
            selected_documents_for_indexing=len(selected_documents),
            skipped_already_indexed_documents=skipped_already_indexed,
        )

    def refresh_status(
        self,
        wait_for_completion: bool = False,
    ) -> ReconciliationSummary:
        self._state_store.migrate()
        self._vector_store.ensure_collection()

        processed_batches = 0
        upserted_embeddings = 0
        item_failures = 0

        for terminal_batch in self._state_store.list_unprocessed_terminal_batches():
            finalized_embeddings, finalized_failures = self._finalize_batch(
                terminal_batch
            )
            processed_batches += 1
            upserted_embeddings += finalized_embeddings
            item_failures += finalized_failures

        incomplete_batches = self._state_store.list_incomplete_batches()
        if incomplete_batches:
            pending_ids = [batch.batch_id for batch in incomplete_batches]
            resumed = self._poll_batches(
                pending_ids,
                wait_for_completion=wait_for_completion,
            )
            processed_batches += resumed[0]
            upserted_embeddings += resumed[1]
            item_failures += resumed[2]

        return ReconciliationSummary(
            processed_batches=processed_batches,
            upserted_embeddings=upserted_embeddings,
            item_failures=item_failures,
        )

    def _select_documents_for_indexing(
        self,
        documents: list[DocumentRecord],
        document_limit: int | None,
    ) -> tuple[list[DocumentRecord], int]:
        models = [model.strip() for model in self._config.batch.models if model.strip()]

        document_candidates: list[tuple[DocumentRecord, list[str]]] = []
        candidate_custom_ids: list[str] = []
        for document in documents:
            document_custom_ids = [
                make_custom_id(document.document_id, model) for model in models
            ]
            document_candidates.append((document, document_custom_ids))
            candidate_custom_ids.extend(document_custom_ids)

        known_custom_ids = self._state_store.list_existing_custom_ids(
            candidate_custom_ids
        )

        selected_documents: list[DocumentRecord] = []
        skipped_already_indexed = 0
        for document, document_custom_ids in document_candidates:
            if any(custom_id in known_custom_ids for custom_id in document_custom_ids):
                skipped_already_indexed += 1
                continue
            if document_limit is not None and len(selected_documents) >= document_limit:
                continue
            selected_documents.append(document)

        return selected_documents, skipped_already_indexed

    def _poll_batches(
        self, batch_ids: list[str], wait_for_completion: bool
    ) -> tuple[int, int, int]:
        if not batch_ids:
            return 0, 0, 0

        remaining = set(batch_ids)
        processed_batches = 0
        upserted_embeddings = 0
        item_failures = 0

        while remaining:
            for batch_id in list(remaining):
                remote_batch = self._batch_client.retrieve_batch(batch_id)
                self._state_store.update_batch_status(remote_batch)

                if remote_batch.status in TERMINAL_BATCH_STATUSES:
                    remaining.discard(batch_id)
                    if not self._state_store.is_processed(batch_id):
                        finalized_embeddings, finalized_failures = self._finalize_batch(
                            remote_batch
                        )
                        processed_batches += 1
                        upserted_embeddings += finalized_embeddings
                        item_failures += finalized_failures

            if not remaining or not wait_for_completion:
                break
            self._sleep(self._config.batch.poll_interval_seconds)

        return processed_batches, upserted_embeddings, item_failures

    def _finalize_batch(self, batch: BatchJobRecord) -> tuple[int, int]:
        failures: list[BatchItemFailure] = []
        embeddings_count = 0

        if batch.status == "completed":
            if batch.output_file_id:
                output_text = self._batch_client.fetch_file_text(batch.output_file_id)
            else:
                output_text = ""
                failures.append(
                    BatchItemFailure(
                        custom_id=None,
                        error_code="missing_output_file",
                        error_message=f"Completed batch {batch.batch_id} has no output_file_id",
                    )
                )

            error_text = (
                self._batch_client.fetch_file_text(batch.error_file_id)
                if batch.error_file_id
                else None
            )
            parsed = parse_batch_results(output_text=output_text, error_text=error_text)
            self._vector_store.upsert_embeddings(parsed.embeddings)
            embeddings_count = len(parsed.embeddings)
            failures.extend(parsed.item_failures)
        elif batch.error_file_id:
            parsed_failures = parse_error_file(
                self._batch_client.fetch_file_text(batch.error_file_id)
            )
            failures.extend(parsed_failures)

        self._state_store.record_item_failures(batch.batch_id, failures)
        self._state_store.mark_processed(batch.batch_id)
        return embeddings_count, len(failures)
