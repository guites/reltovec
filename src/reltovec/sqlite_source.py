from __future__ import annotations

from dataclasses import asdict
import re
import sqlite3

from reltovec.config import SQLiteConfig
from reltovec.models import DocumentRecord, NormalizationStats


_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
CONTENT_COLUMN_SEPARATOR = "\n\n"


class SQLiteSourceError(ValueError):
    pass


class SQLiteDocumentRepository:
    def __init__(self, config: SQLiteConfig):
        self._config = config

    @property
    def config(self) -> SQLiteConfig:
        return self._config

    def validate_schema(self) -> None:
        table = self._safe_identifier(self._config.table, "table")
        id_column = self._safe_identifier(self._config.id_column, "id_column")
        content_columns = self._safe_content_columns()

        required_columns = {id_column, *content_columns}

        with sqlite3.connect(self._config.path) as conn:
            cursor = conn.execute(f'PRAGMA table_info("{table}")')
            existing_columns = {row[1] for row in cursor.fetchall()}

        if not existing_columns:
            raise SQLiteSourceError(f"Configured table not found: {table}")

        missing = sorted(required_columns.difference(existing_columns))
        if missing:
            raise SQLiteSourceError(
                f"Configured columns missing from {table}: {', '.join(missing)}"
            )

    def load_documents(self) -> tuple[list[DocumentRecord], NormalizationStats]:
        self.validate_schema()

        table = self._safe_identifier(self._config.table, "table")
        id_column = self._safe_identifier(self._config.id_column, "id_column")
        content_columns = self._safe_content_columns()
        content_aliases = [
            f"__content_{index}" for index, _ in enumerate(content_columns)
        ]
        content_select = ", ".join(
            f'"{column}" AS "{alias}"'
            for column, alias in zip(content_columns, content_aliases, strict=True)
        )

        query = (
            f'SELECT "{id_column}" AS document_id, {content_select} '
            f'FROM "{table}" ORDER BY "{id_column}" ASC, rowid ASC'
        )

        with sqlite3.connect(self._config.path) as conn:
            conn.row_factory = sqlite3.Row
            rows = [
                {
                    "document_id": row["document_id"],
                    "content": self._compose_content(row, content_aliases),
                }
                for row in conn.execute(query).fetchall()
            ]

        return normalize_rows(rows, source_table=table)

    def _safe_content_columns(self) -> list[str]:
        return [
            self._safe_identifier(column, f"content_column[{index}]")
            for index, column in enumerate(self._config.content_column)
        ]

    def _compose_content(self, row: sqlite3.Row, aliases: list[str]) -> str:
        return CONTENT_COLUMN_SEPARATOR.join(
            "" if row[alias] is None else str(row[alias]) for alias in aliases
        )

    def _safe_identifier(self, raw_value: str | None, field: str) -> str:
        if not raw_value:
            raise SQLiteSourceError(f"Missing required SQLite identifier for {field}")
        if not _IDENTIFIER_RE.match(raw_value):
            raise SQLiteSourceError(
                f"Invalid SQLite identifier for {field}: {raw_value}"
            )
        return raw_value


def normalize_rows(
    rows: list[dict],
    source_table: str,
) -> tuple[list[DocumentRecord], NormalizationStats]:
    documents: list[DocumentRecord] = []
    skipped_empty_content = 0
    skipped_missing_id = 0

    for row in rows:
        raw_document_id = row.get("document_id")
        document_id = "" if raw_document_id is None else str(raw_document_id).strip()
        if document_id == "":
            skipped_missing_id += 1
            continue

        raw_content = row.get("content")
        content = "" if raw_content is None else str(raw_content).strip()
        if content == "":
            skipped_empty_content += 1
            continue

        documents.append(
            DocumentRecord(
                document_id=document_id,
                content=content,
                source_table=source_table,
            )
        )

    stats = NormalizationStats(
        total_rows=len(rows),
        normalized_rows=len(documents),
        skipped_empty_content=skipped_empty_content,
        skipped_missing_id=skipped_missing_id,
    )

    return documents, stats


def as_serializable_documents(documents: list[DocumentRecord]) -> list[dict]:
    return [asdict(document) for document in documents]
