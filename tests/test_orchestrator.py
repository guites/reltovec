from __future__ import annotations

import json
import sqlite3

from brcrawl_embedder.config import (
    AppConfig,
    BatchConfig,
    ChromaConfig,
    SQLiteConfig,
    StateConfig,
)
from brcrawl_embedder.models import BatchJobRecord
from brcrawl_embedder.orchestrator import IndexOrchestrator
from brcrawl_embedder.sqlite_source import SQLiteDocumentRepository
from brcrawl_embedder.state_store import BatchStateStore


class FakeBatchClient:
    def __init__(self):
        self._uploaded_payloads: list[str] = []
        self._batches: dict[str, BatchJobRecord] = {}
        self._file_contents: dict[str, str] = {}
        self._next_batch_id = 1

    def upload_batch_input(self, jsonl_text: str) -> str:
        self._uploaded_payloads.append(jsonl_text)
        file_id = f"file-{len(self._uploaded_payloads)}"
        return file_id

    def create_embedding_batch(
        self, input_file_id: str, completion_window: str
    ) -> BatchJobRecord:
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
        output_file_id = f"output-{batch_id}"
        if output_file_id not in self._file_contents:
            self._file_contents[output_file_id] = json.dumps(
                {
                    "custom_id": "doc:1|model:text-embedding-3-small",
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
            input_file_id=self._batches[batch_id].input_file_id,
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


def _create_config(source_db: str, state_db: str) -> AppConfig:
    return AppConfig(
        sqlite=SQLiteConfig(
            path=source_db,
            table="documents",
            id_column="id",
            content_column="content",
            updated_at_column="updated_at",
        ),
        batch=BatchConfig(
            models=["text-embedding-3-small"],
            completion_window="24h",
            poll_interval_seconds=1,
            max_batch_size=100,
        ),
        chroma=ChromaConfig(
            host="127.0.0.1",
            port=8000,
            collection_name="document_embeddings",
        ),
        state=StateConfig(tracking_db_path=state_db),
    )


def _seed_documents(path: str) -> None:
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
            [
                ("1", "alpha", "2026-01-01T00:00:00"),
                ("2", " ", "2026-01-01T00:00:00"),
            ],
        )
        conn.commit()


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
