from __future__ import annotations

import sqlite3

from brcrawl_embedder.models import BatchJobRecord
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
        custom_ids=["doc:1|model:text-embedding-3-small", "doc:2|model:text-embedding-3-small"],
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

    with sqlite3.connect(db_path) as conn:
        count = conn.execute("SELECT COUNT(*) FROM indexed_work_items").fetchone()[0]

    assert count == 2
