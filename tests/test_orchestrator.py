from __future__ import annotations

import json
import sqlite3

import pytest

from reltovec.config import (
    AppConfig,
    BatchConfig,
    ChromaConfig,
    SQLiteConfig,
    StateConfig,
)
from reltovec.ids import make_custom_id
from reltovec.models import BatchItemFailure, BatchJobRecord
from reltovec.orchestrator import IndexOrchestrator
from reltovec.sqlite_source import SQLiteDocumentRepository
from reltovec.state_store import BatchStateStore


class FakeBatchClient:
    def __init__(self):
        self.uploaded_payloads: list[str] = []
        self.create_calls = 0
        self._uploaded_files: dict[str, str] = {}
        self._batches: dict[str, BatchJobRecord] = {}
        self._file_contents: dict[str, str] = {}
        self._next_batch_id = 1

    def upload_batch_input(self, jsonl_text: str) -> str:
        self.uploaded_payloads.append(jsonl_text)
        file_id = f"file-{len(self.uploaded_payloads)}"
        self._uploaded_files[file_id] = jsonl_text
        return file_id

    def create_embedding_batch(
        self, input_file_id: str, completion_window: str
    ) -> BatchJobRecord:
        self.create_calls += 1
        batch_id = f"batch-{self._next_batch_id}"
        self._next_batch_id += 1

        created = BatchJobRecord(
            batch_id=batch_id,
            status="in_progress",
            input_file_id=input_file_id,
        )
        self._batches[batch_id] = created
        return created

    def retrieve_batch(self, batch_id: str) -> BatchJobRecord:
        input_file_id = self._batches[batch_id].input_file_id
        payload = self._uploaded_files.get(input_file_id, "")
        first_custom_id = (
            _payload_custom_ids(payload)[0]
            if payload
            else "doc:1|model:text-embedding-3-small"
        )

        output_file_id = f"output-{batch_id}"
        if output_file_id not in self._file_contents:
            self._file_contents[output_file_id] = json.dumps(
                {
                    "custom_id": first_custom_id,
                    "response": {
                        "status_code": 200,
                        "body": {
                            "model": "text-embedding-3-small",
                            "data": [{"embedding": [0.1, 0.2, 0.3]}],
                        },
                    },
                }
            )

        completed = BatchJobRecord(
            batch_id=batch_id,
            status="completed",
            input_file_id=input_file_id,
            output_file_id=output_file_id,
        )
        self._batches[batch_id] = completed
        return completed

    def fetch_file_text(self, file_id: str) -> str:
        return self._file_contents[file_id]


class InMemoryVectorStore:
    def __init__(self):
        self.rows = {}

    def ensure_collection(self) -> None:
        return None

    def upsert_embeddings(self, embeddings):
        for embedding in embeddings:
            self.rows[embedding.custom_id] = embedding

    def query_by_document_id(
        self,
        document_id: str,
        model: str | None = None,
        include_embeddings: bool = True,
    ):
        raise NotImplementedError


def _create_config(
    source_db: str,
    state_db: str,
    *,
    models: list[str] | None = None,
    max_batch_size: int = 100,
) -> AppConfig:
    return AppConfig(
        sqlite=SQLiteConfig(
            path=source_db,
            table="documents",
            id_column="id",
            content_column=["content"],
            updated_at_column="updated_at",
        ),
        batch=BatchConfig(
            models=models or ["text-embedding-3-small"],
            completion_window="24h",
            poll_interval_seconds=1,
            max_batch_size=max_batch_size,
        ),
        chroma=ChromaConfig(
            host="127.0.0.1",
            port=8000,
            collection_name="document_embeddings",
        ),
        state=StateConfig(tracking_db_path=state_db),
    )


def _seed_documents(
    path: str, rows: list[tuple[str | None, str, str]] | None = None
) -> None:
    with sqlite3.connect(path) as conn:
        conn.execute(
            """
            CREATE TABLE documents (
                id TEXT,
                content TEXT,
                updated_at TEXT
            )
            """
        )
        conn.executemany(
            "INSERT INTO documents (id, content, updated_at) VALUES (?, ?, ?)",
            rows
            or [
                ("1", "alpha", "2026-01-01T00:00:00"),
                ("2", " ", "2026-01-01T00:00:00"),
            ],
        )
        conn.commit()


def _payload_custom_ids(payload: str) -> list[str]:
    return [
        str(json.loads(line)["custom_id"])
        for line in payload.splitlines()
        if line.strip()
    ]


def test_orchestrator_indexes_and_persists_results(tmp_path):
    source_db = str(tmp_path / "source.db")
    state_db = str(tmp_path / "state.db")
    _seed_documents(source_db)

    config = _create_config(source_db=source_db, state_db=state_db)
    orchestrator = IndexOrchestrator(
        config=config,
        source_repo=SQLiteDocumentRepository(config.sqlite),
        batch_client=FakeBatchClient(),
        state_store=BatchStateStore(state_db),
        vector_store=InMemoryVectorStore(),
        sleep_fn=lambda _: None,
    )

    summary = orchestrator.index(wait_for_completion=True)

    assert summary.total_documents_seen == 2
    assert summary.eligible_documents == 1
    assert summary.selected_documents_for_indexing == 1
    assert summary.skipped_already_indexed_documents == 0
    assert summary.skipped_empty_content == 1
    assert summary.submitted_batches == 1
    assert summary.processed_batches == 1
    assert summary.upserted_embeddings == 1


def test_orchestrator_resumes_incomplete_batches_before_new_submissions(tmp_path):
    source_db = str(tmp_path / "source.db")
    state_db = str(tmp_path / "state.db")
    _seed_documents(source_db)

    config = _create_config(source_db=source_db, state_db=state_db)
    state_store = BatchStateStore(state_db)
    state_store.migrate()
    state_store.record_batch_submission(
        BatchJobRecord(
            batch_id="batch-resume",
            status="in_progress",
            input_file_id="file-resume",
        )
    )

    fake_client = FakeBatchClient()
    fake_client._batches["batch-resume"] = BatchJobRecord(
        batch_id="batch-resume",
        status="in_progress",
        input_file_id="file-resume",
    )

    orchestrator = IndexOrchestrator(
        config=config,
        source_repo=SQLiteDocumentRepository(config.sqlite),
        batch_client=fake_client,
        state_store=state_store,
        vector_store=InMemoryVectorStore(),
        sleep_fn=lambda _: None,
    )

    summary = orchestrator.index(wait_for_completion=True)

    assert summary.processed_batches >= 1


def test_orchestrator_validates_document_limit(tmp_path):
    source_db = str(tmp_path / "source.db")
    state_db = str(tmp_path / "state.db")
    _seed_documents(source_db)

    config = _create_config(source_db=source_db, state_db=state_db)
    orchestrator = IndexOrchestrator(
        config=config,
        source_repo=SQLiteDocumentRepository(config.sqlite),
        batch_client=FakeBatchClient(),
        state_store=BatchStateStore(state_db),
        vector_store=InMemoryVectorStore(),
        sleep_fn=lambda _: None,
    )

    with pytest.raises(ValueError, match="document_limit must be positive"):
        orchestrator.index(wait_for_completion=True, document_limit=0)


def test_orchestrator_applies_document_limit_before_batch_chunking(tmp_path):
    source_db = str(tmp_path / "source.db")
    state_db = str(tmp_path / "state.db")
    _seed_documents(
        source_db,
        rows=[
            ("1", "alpha", "2026-01-01T00:00:00"),
            ("2", "beta", "2026-01-01T00:00:00"),
            ("3", "gamma", "2026-01-01T00:00:00"),
            ("4", "delta", "2026-01-01T00:00:00"),
            ("5", "epsilon", "2026-01-01T00:00:00"),
        ],
    )

    config = _create_config(
        source_db=source_db,
        state_db=state_db,
        max_batch_size=2,
    )
    fake_client = FakeBatchClient()
    orchestrator = IndexOrchestrator(
        config=config,
        source_repo=SQLiteDocumentRepository(config.sqlite),
        batch_client=fake_client,
        state_store=BatchStateStore(state_db),
        vector_store=InMemoryVectorStore(),
        sleep_fn=lambda _: None,
    )

    summary = orchestrator.index(wait_for_completion=True, document_limit=5)

    assert summary.requested_document_limit == 5
    assert summary.selected_documents_for_indexing == 5
    assert summary.submitted_batches == 3
    assert len(fake_client.uploaded_payloads) == 3
    assert (
        sum(
            len(_payload_custom_ids(payload))
            for payload in fake_client.uploaded_payloads
        )
        == 5
    )


def test_orchestrator_repeated_limit_runs_are_incremental(tmp_path):
    source_db = str(tmp_path / "source.db")
    state_db = str(tmp_path / "state.db")
    _seed_documents(
        source_db,
        rows=[
            ("1", "alpha", "2026-01-01T00:00:00"),
            ("2", "beta", "2026-01-01T00:00:00"),
            ("3", "gamma", "2026-01-01T00:00:00"),
        ],
    )

    config = _create_config(source_db=source_db, state_db=state_db, max_batch_size=10)
    fake_client = FakeBatchClient()
    state_store = BatchStateStore(state_db)
    orchestrator = IndexOrchestrator(
        config=config,
        source_repo=SQLiteDocumentRepository(config.sqlite),
        batch_client=fake_client,
        state_store=state_store,
        vector_store=InMemoryVectorStore(),
        sleep_fn=lambda _: None,
    )

    first = orchestrator.index(wait_for_completion=True, document_limit=2)
    second = orchestrator.index(wait_for_completion=True, document_limit=2)
    third = orchestrator.index(wait_for_completion=True, document_limit=2)

    assert first.selected_documents_for_indexing == 2
    assert first.skipped_already_indexed_documents == 0
    assert second.selected_documents_for_indexing == 1
    assert second.skipped_already_indexed_documents == 2
    assert third.selected_documents_for_indexing == 0
    assert third.skipped_already_indexed_documents == 3
    assert third.submitted_batches == 0

    all_submitted_custom_ids = [
        custom_id
        for payload in fake_client.uploaded_payloads
        for custom_id in _payload_custom_ids(payload)
    ]
    assert len(all_submitted_custom_ids) == 3
    assert len(set(all_submitted_custom_ids)) == 3


def test_orchestrator_skips_documents_with_existing_work_regardless_of_batch_status(
    tmp_path,
):
    source_db = str(tmp_path / "source.db")
    state_db = str(tmp_path / "state.db")
    _seed_documents(
        source_db,
        rows=[
            ("1", "alpha", "2026-01-01T00:00:00"),
            ("2", "beta", "2026-01-01T00:00:00"),
        ],
    )

    config = _create_config(source_db=source_db, state_db=state_db)
    state_store = BatchStateStore(state_db)
    state_store.migrate()

    existing_custom_id = make_custom_id("1", "text-embedding-3-small")
    state_store.record_batch_submission(
        BatchJobRecord(
            batch_id="batch-existing",
            status="in_progress",
            input_file_id="file-existing",
        )
    )
    state_store.record_submitted_work_items(
        batch_id="batch-existing",
        custom_ids=[existing_custom_id],
    )

    fake_client = FakeBatchClient()
    fake_client._batches["batch-existing"] = BatchJobRecord(
        batch_id="batch-existing",
        status="in_progress",
        input_file_id="file-existing",
    )

    orchestrator = IndexOrchestrator(
        config=config,
        source_repo=SQLiteDocumentRepository(config.sqlite),
        batch_client=fake_client,
        state_store=state_store,
        vector_store=InMemoryVectorStore(),
        sleep_fn=lambda _: None,
    )

    summary = orchestrator.index(wait_for_completion=True, document_limit=2)

    assert summary.selected_documents_for_indexing == 1
    assert summary.skipped_already_indexed_documents == 1

    submitted_custom_ids = [
        custom_id
        for payload in fake_client.uploaded_payloads
        for custom_id in _payload_custom_ids(payload)
    ]
    assert make_custom_id("2", "text-embedding-3-small") in submitted_custom_ids
    assert existing_custom_id not in submitted_custom_ids


def test_orchestrator_uses_deterministic_document_order_for_incremental_runs(tmp_path):
    source_db = str(tmp_path / "source.db")
    state_db = str(tmp_path / "state.db")
    _seed_documents(
        source_db,
        rows=[
            ("3", "gamma", "2026-01-01T00:00:00"),
            ("1", "alpha", "2026-01-01T00:00:00"),
            ("2", "beta", "2026-01-01T00:00:00"),
        ],
    )

    config = _create_config(source_db=source_db, state_db=state_db)
    fake_client = FakeBatchClient()
    orchestrator = IndexOrchestrator(
        config=config,
        source_repo=SQLiteDocumentRepository(config.sqlite),
        batch_client=fake_client,
        state_store=BatchStateStore(state_db),
        vector_store=InMemoryVectorStore(),
        sleep_fn=lambda _: None,
    )

    orchestrator.index(wait_for_completion=True, document_limit=1)
    orchestrator.index(wait_for_completion=True, document_limit=1)
    orchestrator.index(wait_for_completion=True, document_limit=1)

    first_custom_id_per_run = [
        _payload_custom_ids(payload)[0] for payload in fake_client.uploaded_payloads
    ]
    assert first_custom_id_per_run == [
        make_custom_id("1", "text-embedding-3-small"),
        make_custom_id("2", "text-embedding-3-small"),
        make_custom_id("3", "text-embedding-3-small"),
    ]


def test_orchestrator_refresh_status_finalizes_terminal_and_incomplete_batches(
    tmp_path,
):
    source_db = str(tmp_path / "source.db")
    state_db = str(tmp_path / "state.db")
    _seed_documents(source_db)

    config = _create_config(source_db=source_db, state_db=state_db)
    state_store = BatchStateStore(state_db)
    state_store.migrate()

    state_store.record_batch_submission(
        BatchJobRecord(
            batch_id="batch-terminal",
            status="completed",
            input_file_id="file-terminal",
            output_file_id="output-terminal",
        )
    )
    state_store.record_batch_submission(
        BatchJobRecord(
            batch_id="batch-in-progress",
            status="in_progress",
            input_file_id="file-in-progress",
        )
    )

    fake_client = FakeBatchClient()
    fake_client._file_contents["output-terminal"] = json.dumps(
        {
            "custom_id": make_custom_id("1", "text-embedding-3-small"),
            "response": {
                "status_code": 200,
                "body": {
                    "model": "text-embedding-3-small",
                    "data": [{"embedding": [0.1, 0.2, 0.3]}],
                },
            },
        }
    )
    fake_client._batches["batch-in-progress"] = BatchJobRecord(
        batch_id="batch-in-progress",
        status="in_progress",
        input_file_id="file-in-progress",
    )

    vector_store = InMemoryVectorStore()
    orchestrator = IndexOrchestrator(
        config=config,
        source_repo=SQLiteDocumentRepository(config.sqlite),
        batch_client=fake_client,
        state_store=state_store,
        vector_store=vector_store,
        sleep_fn=lambda _: None,
    )

    summary = orchestrator.refresh_status(wait_for_completion=False)

    assert summary.processed_batches == 2
    assert summary.upserted_embeddings == 2
    assert summary.item_failures == 0
    assert state_store.is_processed("batch-terminal")
    assert state_store.is_processed("batch-in-progress")
    assert len(vector_store.rows) == 1

    batches = {batch.batch_id: batch for batch in state_store.list_batches(limit=10)}
    assert batches["batch-in-progress"].status == "completed"


def test_orchestrator_refresh_status_never_submits_new_batches(tmp_path):
    source_db = str(tmp_path / "source.db")
    state_db = str(tmp_path / "state.db")
    _seed_documents(source_db)

    config = _create_config(source_db=source_db, state_db=state_db)
    state_store = BatchStateStore(state_db)
    state_store.migrate()
    state_store.record_batch_submission(
        BatchJobRecord(
            batch_id="batch-still-running",
            status="in_progress",
            input_file_id="file-still-running",
        )
    )

    class NonTerminalBatchClient(FakeBatchClient):
        def retrieve_batch(self, batch_id: str) -> BatchJobRecord:
            return BatchJobRecord(
                batch_id=batch_id,
                status="in_progress",
                input_file_id="file-still-running",
            )

    fake_client = NonTerminalBatchClient()
    fake_client._batches["batch-still-running"] = BatchJobRecord(
        batch_id="batch-still-running",
        status="in_progress",
        input_file_id="file-still-running",
    )

    class FailingSourceRepository:
        def load_documents(self):
            raise AssertionError("status refresh must not load source documents")

    orchestrator = IndexOrchestrator(
        config=config,
        source_repo=FailingSourceRepository(),
        batch_client=fake_client,
        state_store=state_store,
        vector_store=InMemoryVectorStore(),
        sleep_fn=lambda _: None,
    )

    summary = orchestrator.refresh_status(wait_for_completion=False)

    assert summary.processed_batches == 0
    assert summary.upserted_embeddings == 0
    assert summary.item_failures == 0
    assert fake_client.uploaded_payloads == []
    assert fake_client.create_calls == 0


def test_orchestrator_refresh_status_returns_batch_failure_summaries(tmp_path):
    source_db = str(tmp_path / "source.db")
    state_db = str(tmp_path / "state.db")
    _seed_documents(source_db)

    config = _create_config(source_db=source_db, state_db=state_db)
    state_store = BatchStateStore(state_db)
    state_store.migrate()
    state_store.record_batch_submission(
        BatchJobRecord(
            batch_id="batch-with-failure",
            status="completed",
            input_file_id="file-with-failure",
            output_file_id="output-with-failure",
        )
    )
    state_store.record_submitted_work_items(
        batch_id="batch-with-failure",
        custom_ids=[
            make_custom_id("1", "text-embedding-3-small"),
            make_custom_id("2", "text-embedding-3-small"),
        ],
    )

    fake_client = FakeBatchClient()
    fake_client._file_contents["output-with-failure"] = json.dumps(
        {
            "custom_id": make_custom_id("1", "text-embedding-3-small"),
            "response": {
                "status_code": 400,
                "body": {
                    "error": {
                        "code": "invalid_request",
                        "message": "invalid input",
                    }
                },
            },
        }
    )

    orchestrator = IndexOrchestrator(
        config=config,
        source_repo=SQLiteDocumentRepository(config.sqlite),
        batch_client=fake_client,
        state_store=state_store,
        vector_store=InMemoryVectorStore(),
        sleep_fn=lambda _: None,
    )

    summary = orchestrator.refresh_status(wait_for_completion=False, batch_list_limit=10)

    assert summary.processed_batches == 1
    assert summary.upserted_embeddings == 0
    assert summary.item_failures == 1
    assert len(summary.batches) == 1
    assert summary.batches[0].batch_id == "batch-with-failure"
    assert summary.batches[0].documents_sent_count == 2
    assert summary.batches[0].failed_item_count == 1
    assert summary.batches[0].failure_error_codes == ["invalid_request"]


def test_orchestrator_purge_propagates_summary_and_handles_noop(tmp_path):
    source_db = str(tmp_path / "source.db")
    state_db = str(tmp_path / "state.db")
    _seed_documents(source_db)

    config = _create_config(source_db=source_db, state_db=state_db)
    state_store = BatchStateStore(state_db)
    state_store.migrate()
    state_store.record_batch_submission(
        BatchJobRecord(
            batch_id="batch-1",
            status="completed",
            input_file_id="file-1",
        )
    )

    timeout_custom_id = make_custom_id("1", "text-embedding-3-small")
    non_timeout_custom_id = make_custom_id("2", "text-embedding-3-small")
    state_store.record_submitted_work_items(
        batch_id="batch-1",
        custom_ids=[timeout_custom_id, non_timeout_custom_id],
    )
    state_store.record_item_failures(
        "batch-1",
        [
            BatchItemFailure(
                custom_id=timeout_custom_id,
                error_code="timeout",
                error_message="request timed out",
            ),
            BatchItemFailure(
                custom_id=non_timeout_custom_id,
                error_code="invalid_request",
                error_message="invalid input",
            ),
        ],
    )

    orchestrator = IndexOrchestrator(
        config=config,
        source_repo=SQLiteDocumentRepository(config.sqlite),
        batch_client=FakeBatchClient(),
        state_store=state_store,
        vector_store=InMemoryVectorStore(),
        sleep_fn=lambda _: None,
    )

    first = orchestrator.purge("timeout")
    second = orchestrator.purge("timeout")

    assert first.error_code == "timeout"
    assert first.deleted_failures == 1
    assert first.released_work_items == 1
    assert second.error_code == "timeout"
    assert second.deleted_failures == 0
    assert second.released_work_items == 0

    remaining_custom_ids = state_store.list_existing_custom_ids(
        [timeout_custom_id, non_timeout_custom_id]
    )
    assert remaining_custom_ids == {non_timeout_custom_id}
