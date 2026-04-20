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


def test_state_store_purge_by_error_code_scopes_deletion_and_releases_work_items(
    tmp_path,
):
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

    timeout_1 = "doc:1|model:text-embedding-3-small"
    timeout_2 = "doc:3|model:text-embedding-3-small"
    timeout_3 = "doc:5|model:text-embedding-3-small"
    non_timeout_1 = "doc:2|model:text-embedding-3-small"
    non_timeout_2 = "doc:4|model:text-embedding-3-small"

    store.record_submitted_work_items(
        batch_id="batch-1",
        custom_ids=[timeout_1, non_timeout_1, timeout_2, timeout_3],
    )
    store.record_submitted_work_items(
        batch_id="batch-2",
        custom_ids=[non_timeout_2],
    )

    store.record_item_failures(
        "batch-1",
        [
            BatchItemFailure(timeout_1, "timeout", "first timeout"),
            BatchItemFailure(timeout_1, "timeout", "duplicate timeout row"),
            BatchItemFailure(non_timeout_1, "invalid_request", "bad request"),
            BatchItemFailure(timeout_2, "timeout", "another timeout"),
            BatchItemFailure(None, "timeout", "missing custom_id"),
            BatchItemFailure("", "timeout", "blank custom_id"),
        ],
    )
    store.record_item_failures(
        "batch-2",
        [
            BatchItemFailure(non_timeout_2, "rate_limit", "too many requests"),
            BatchItemFailure(timeout_3, "timeout", "cross-batch timeout"),
        ],
    )

    deleted_failures, released_work_items = store.purge_failures_by_error_code(
        "timeout"
    )
    assert deleted_failures == 6
    assert released_work_items == 3

    remaining_custom_ids = store.list_existing_custom_ids(
        [timeout_1, timeout_2, timeout_3, non_timeout_1, non_timeout_2]
    )
    assert remaining_custom_ids == {non_timeout_1, non_timeout_2}

    with sqlite3.connect(db_path) as conn:
        remaining_failure_rows = conn.execute(
            """
            SELECT error_code, COUNT(*)
            FROM embedding_item_failures
            GROUP BY error_code
            ORDER BY error_code
            """
        ).fetchall()

    assert remaining_failure_rows == [("invalid_request", 1), ("rate_limit", 1)]

    no_match_deleted, no_match_released = store.purge_failures_by_error_code(
        "not-a-real-code"
    )
    assert no_match_deleted == 0
    assert no_match_released == 0
