from __future__ import annotations

import sqlite3

from brcrawl_embedder.models import BatchItemFailure, BatchJobRecord
from brcrawl_embedder.state_store import BatchStateStore


def test_state_store_migration_creates_indexed_work_items_table(tmp_path):
    db_path = str(tmp_path / "state.db")
    store = BatchStateStore(db_path)

    store.migrate()

    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table' AND name = 'indexed_work_items'
            """
        ).fetchone()

    assert row is not None


def test_state_store_records_and_queries_submitted_work_items(tmp_path):
    db_path = str(tmp_path / "state.db")
    store = BatchStateStore(db_path)
    store.migrate()

    store.record_batch_submission(
        BatchJobRecord(
            batch_id="batch-1",
            status="in_progress",
            input_file_id="file-1",
        )
    )

    store.record_submitted_work_items(
        batch_id="batch-1",
        custom_ids=[
            "doc:1|model:text-embedding-3-small",
            "doc:2|model:text-embedding-3-small",
        ],
    )
    store.record_submitted_work_items(
        batch_id="batch-1",
        custom_ids=["doc:1|model:text-embedding-3-small"],
    )

    existing = store.list_existing_custom_ids(
        [
            "doc:1|model:text-embedding-3-small",
            "doc:3|model:text-embedding-3-small",
        ]
    )

    assert existing == {"doc:1|model:text-embedding-3-small"}
    assert store.get_documents_sent_count("batch-1") == 2

    with sqlite3.connect(db_path) as conn:
        count = conn.execute("SELECT COUNT(*) FROM indexed_work_items").fetchone()[0]

    assert count == 2


def test_state_store_aggregates_batch_failure_counts_and_error_codes(tmp_path):
    db_path = str(tmp_path / "state.db")
    store = BatchStateStore(db_path)
    store.migrate()

    store.record_batch_submission(
        BatchJobRecord(
            batch_id="batch-1",
            status="completed",
            input_file_id="file-1",
        )
    )
    store.record_batch_submission(
        BatchJobRecord(
            batch_id="batch-2",
            status="completed",
            input_file_id="file-2",
        )
    )

    store.record_item_failures(
        "batch-1",
        [
            BatchItemFailure(
                custom_id="doc:1|model:text-embedding-3-small",
                error_code="timeout",
                error_message="request timed out",
            ),
            BatchItemFailure(
                custom_id="doc:2|model:text-embedding-3-small",
                error_code="invalid_request",
                error_message="invalid payload",
            ),
            BatchItemFailure(
                custom_id="doc:3|model:text-embedding-3-small",
                error_code="timeout",
                error_message="request timed out again",
            ),
            BatchItemFailure(
                custom_id="doc:4|model:text-embedding-3-small",
                error_code="",
                error_message="empty code should be ignored in code list",
            ),
        ],
    )
    store.record_submitted_work_items(
        batch_id="batch-1",
        custom_ids=[
            "doc:1|model:text-embedding-3-small",
            "doc:2|model:text-embedding-3-small",
            "doc:3|model:text-embedding-3-small",
        ],
    )
    store.record_submitted_work_items(
        batch_id="batch-2",
        custom_ids=["doc:4|model:text-embedding-3-small"],
    )

    assert store.get_failed_item_count("batch-1") == 4
    assert store.get_failed_item_count("batch-2") == 0
    assert store.get_documents_sent_count("batch-1") == 3
    assert store.get_documents_sent_count("batch-2") == 1
    assert store.list_failure_error_codes("batch-1") == ["invalid_request", "timeout"]
    assert store.list_failure_error_codes("batch-2") == []

    batches = {batch.batch_id: batch for batch in store.list_batches(limit=10)}
    assert batches["batch-1"].documents_sent_count == 3
    assert batches["batch-2"].documents_sent_count == 1
    assert batches["batch-1"].failed_item_count == 4
    assert batches["batch-1"].failure_error_codes == ["invalid_request", "timeout"]
    assert batches["batch-2"].failed_item_count == 0
    assert batches["batch-2"].failure_error_codes == []
