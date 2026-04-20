from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timezone
import sqlite3

from brcrawl_embedder.models import BatchItemFailure, BatchJobRecord


TERMINAL_BATCH_STATUSES = {"completed", "failed", "cancelled", "expired"}


class BatchStateStore:
    def __init__(self, db_path: str):
        self._db_path = db_path

    @property
    def db_path(self) -> str:
        return self._db_path

    def migrate(self) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS embedding_batches (
                    batch_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    input_file_id TEXT NOT NULL,
                    output_file_id TEXT,
                    error_file_id TEXT,
                    submitted_at TEXT NOT NULL,
                    completed_at TEXT,
                    processed_at TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS embedding_item_failures (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    batch_id TEXT NOT NULL,
                    custom_id TEXT,
                    error_code TEXT,
                    error_message TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(batch_id) REFERENCES embedding_batches(batch_id)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS indexed_work_items (
                    custom_id TEXT PRIMARY KEY,
                    batch_id TEXT NOT NULL,
                    submitted_at TEXT NOT NULL,
                    FOREIGN KEY(batch_id) REFERENCES embedding_batches(batch_id)
                )
                """
            )
            conn.commit()

    def record_batch_submission(self, batch: BatchJobRecord) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """
                INSERT INTO embedding_batches (
                    batch_id,
                    status,
                    input_file_id,
                    output_file_id,
                    error_file_id,
                    submitted_at,
                    completed_at,
                    processed_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, NULL)
                ON CONFLICT(batch_id) DO UPDATE SET
                    status=excluded.status,
                    input_file_id=excluded.input_file_id,
                    output_file_id=excluded.output_file_id,
                    error_file_id=excluded.error_file_id,
                    submitted_at=excluded.submitted_at,
                    completed_at=excluded.completed_at
                """,
                (
                    batch.batch_id,
                    batch.status,
                    batch.input_file_id,
                    batch.output_file_id,
                    batch.error_file_id,
                    batch.submitted_at,
                    batch.completed_at,
                ),
            )
            conn.commit()

    def update_batch_status(self, batch: BatchJobRecord) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """
                UPDATE embedding_batches
                SET status = ?,
                    output_file_id = ?,
                    error_file_id = ?,
                    completed_at = COALESCE(?, completed_at)
                WHERE batch_id = ?
                """,
                (
                    batch.status,
                    batch.output_file_id,
                    batch.error_file_id,
                    batch.completed_at,
                    batch.batch_id,
                ),
            )
            conn.commit()

    def list_batches(self, limit: int = 100) -> list[BatchJobRecord]:
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT batch_id, status, input_file_id, output_file_id, error_file_id, submitted_at, completed_at
                FROM embedding_batches
                ORDER BY submitted_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        batches = [self._row_to_batch(row) for row in rows]
        return [
            BatchJobRecord(
                batch_id=batch.batch_id,
                status=batch.status,
                input_file_id=batch.input_file_id,
                output_file_id=batch.output_file_id,
                error_file_id=batch.error_file_id,
                submitted_at=batch.submitted_at,
                completed_at=batch.completed_at,
                documents_sent_count=self.get_documents_sent_count(batch.batch_id),
                failed_item_count=self.get_failed_item_count(batch.batch_id),
                failure_error_codes=self.list_failure_error_codes(batch.batch_id),
            )
            for batch in batches
        ]

    def list_incomplete_batches(self) -> list[BatchJobRecord]:
        placeholders = ",".join("?" for _ in TERMINAL_BATCH_STATUSES)
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                f"""
                SELECT batch_id, status, input_file_id, output_file_id, error_file_id, submitted_at, completed_at
                FROM embedding_batches
                WHERE status NOT IN ({placeholders})
                ORDER BY submitted_at ASC
                """,
                tuple(TERMINAL_BATCH_STATUSES),
            ).fetchall()
        return [self._row_to_batch(row) for row in rows]

    def list_unprocessed_terminal_batches(self) -> list[BatchJobRecord]:
        placeholders = ",".join("?" for _ in TERMINAL_BATCH_STATUSES)
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                f"""
                SELECT batch_id, status, input_file_id, output_file_id, error_file_id, submitted_at, completed_at
                FROM embedding_batches
                WHERE status IN ({placeholders})
                  AND processed_at IS NULL
                ORDER BY submitted_at ASC
                """,
                tuple(TERMINAL_BATCH_STATUSES),
            ).fetchall()
        return [self._row_to_batch(row) for row in rows]

    def is_processed(self, batch_id: str) -> bool:
        with sqlite3.connect(self._db_path) as conn:
            row = conn.execute(
                "SELECT processed_at FROM embedding_batches WHERE batch_id = ?",
                (batch_id,),
            ).fetchone()
        return bool(row and row[0])

    def mark_processed(self, batch_id: str) -> None:
        processed_at = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                "UPDATE embedding_batches SET processed_at = ? WHERE batch_id = ?",
                (processed_at, batch_id),
            )
            conn.commit()

    def record_item_failures(
        self, batch_id: str, failures: list[BatchItemFailure]
    ) -> None:
        if not failures:
            return
        created_at = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self._db_path) as conn:
            conn.executemany(
                """
                INSERT INTO embedding_item_failures (
                    batch_id,
                    custom_id,
                    error_code,
                    error_message,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (
                        batch_id,
                        failure.custom_id,
                        failure.error_code,
                        failure.error_message,
                        created_at,
                    )
                    for failure in failures
                ],
            )
            conn.commit()

    def get_failed_item_count(self, batch_id: str) -> int:
        with sqlite3.connect(self._db_path) as conn:
            row = conn.execute(
                """
                SELECT COUNT(*)
                FROM embedding_item_failures
                WHERE batch_id = ?
                """,
                (batch_id,),
            ).fetchone()
        return int(row[0]) if row else 0

    def get_documents_sent_count(self, batch_id: str) -> int:
        with sqlite3.connect(self._db_path) as conn:
            row = conn.execute(
                """
                SELECT COUNT(*)
                FROM indexed_work_items
                WHERE batch_id = ?
                """,
                (batch_id,),
            ).fetchone()
        return int(row[0]) if row else 0

    def list_failure_error_codes(self, batch_id: str) -> list[str]:
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT DISTINCT error_code
                FROM embedding_item_failures
                WHERE batch_id = ?
                  AND error_code IS NOT NULL
                  AND TRIM(error_code) != ''
                ORDER BY error_code ASC
                """,
                (batch_id,),
            ).fetchall()
        return [str(row["error_code"]) for row in rows]

    def list_existing_custom_ids(self, custom_ids: Iterable[str]) -> set[str]:
        unique_ids = [custom_id for custom_id in dict.fromkeys(custom_ids) if custom_id]
        if not unique_ids:
            return set()

        existing: set[str] = set()
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            for start in range(0, len(unique_ids), 900):
                chunk = unique_ids[start : start + 900]
                placeholders = ",".join("?" for _ in chunk)
                rows = conn.execute(
                    f"""
                    SELECT custom_id
                    FROM indexed_work_items
                    WHERE custom_id IN ({placeholders})
                    """,
                    tuple(chunk),
                ).fetchall()
                existing.update(str(row["custom_id"]) for row in rows)
        return existing

    def record_submitted_work_items(
        self, batch_id: str, custom_ids: Iterable[str]
    ) -> None:
        unique_ids = [custom_id for custom_id in dict.fromkeys(custom_ids) if custom_id]
        if not unique_ids:
            return

        submitted_at = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self._db_path) as conn:
            conn.executemany(
                """
                INSERT OR IGNORE INTO indexed_work_items (
                    custom_id,
                    batch_id,
                    submitted_at
                )
                VALUES (?, ?, ?)
                """,
                [
                    (
                        custom_id,
                        batch_id,
                        submitted_at,
                    )
                    for custom_id in unique_ids
                ],
            )
            conn.commit()

    def purge_failures_by_error_code(self, error_code: str) -> tuple[int, int]:
        with sqlite3.connect(self._db_path) as conn:
            released_work_items = conn.execute(
                """
                DELETE FROM indexed_work_items
                WHERE custom_id IN (
                    SELECT DISTINCT custom_id
                    FROM embedding_item_failures
                    WHERE error_code = ?
                      AND custom_id IS NOT NULL
                      AND TRIM(custom_id) != ''
                )
                """,
                (error_code,),
            ).rowcount

            deleted_failures = conn.execute(
                """
                DELETE FROM embedding_item_failures
                WHERE error_code = ?
                """,
                (error_code,),
            ).rowcount
            conn.commit()

        return deleted_failures, released_work_items

    def _row_to_batch(self, row: sqlite3.Row) -> BatchJobRecord:
        return BatchJobRecord(
            batch_id=str(row["batch_id"]),
            status=str(row["status"]),
            input_file_id=str(row["input_file_id"]),
            output_file_id=row["output_file_id"],
            error_file_id=row["error_file_id"],
            submitted_at=str(row["submitted_at"]),
            completed_at=row["completed_at"],
        )
