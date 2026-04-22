from __future__ import annotations

import sqlite3

import pytest

from reltovec.config import ConfigError, load_config
from reltovec.ids import make_custom_id, parse_custom_id
from reltovec.planner import plan_work_items
from reltovec.sqlite_source import SQLiteDocumentRepository, SQLiteSourceError


def test_load_config_validates_models(tmp_path):
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        """
[sqlite]
path = "./docs.db"
table = "documents"
id_column = "id"
content_column = ["content"]
updated_at_column = "updated_at"

[batch]
models = []
completion_window = "24h"
poll_interval_seconds = 2
max_batch_size = 100

[chroma]
host = "127.0.0.1"
port = 8000
collection_name = "document_embeddings"

[state]
tracking_db_path = "./state.db"
""",
        encoding="utf-8",
    )

    with pytest.raises(ConfigError):
        load_config(config_path)


def test_load_config_rejects_scalar_content_column(tmp_path):
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        """
[sqlite]
path = "./docs.db"
table = "documents"
id_column = "id"
content_column = "content"
updated_at_column = "updated_at"

[batch]
models = ["text-embedding-3-small"]
completion_window = "24h"
poll_interval_seconds = 2
max_batch_size = 100

[chroma]
host = "127.0.0.1"
port = 8000
collection_name = "document_embeddings"

[state]
tracking_db_path = "./state.db"
""",
        encoding="utf-8",
    )

    with pytest.raises(
        ConfigError, match="content_column must be an array of non-empty strings"
    ):
        load_config(config_path)


def test_sqlite_repository_normalizes_and_filters_documents(tmp_path):
    db_path = tmp_path / "documents.db"
    with sqlite3.connect(db_path) as conn:
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
                ("2", "   ", "2026-01-01T00:00:00"),
                (None, "missing id", "2026-01-01T00:00:00"),
            ],
        )
        conn.commit()

    config_path = tmp_path / "config.toml"
    config_path.write_text(
        f"""
[sqlite]
path = "{db_path}"
table = "documents"
id_column = "id"
content_column = ["content"]
updated_at_column = "updated_at"

[batch]
models = ["text-embedding-3-small", "text-embedding-3-large"]
completion_window = "24h"
poll_interval_seconds = 2
max_batch_size = 100

[chroma]
host = "127.0.0.1"
port = 8000
collection_name = "document_embeddings"

[state]
tracking_db_path = "{tmp_path / "state.db"}"
""",
        encoding="utf-8",
    )

    app_config = load_config(config_path)
    repo = SQLiteDocumentRepository(app_config.sqlite)

    documents, stats = repo.load_documents()

    assert stats.total_rows == 3
    assert stats.normalized_rows == 1
    assert stats.skipped_empty_content == 1
    assert stats.skipped_missing_id == 1
    assert len(documents) == 1
    assert documents[0].document_id == "1"
    assert documents[0].content == "alpha"

    work_items = plan_work_items(documents, app_config.batch.models)
    assert len(work_items) == 2
    assert {item.model for item in work_items} == {
        "text-embedding-3-small",
        "text-embedding-3-large",
    }


def test_sqlite_repository_concatenates_multiple_content_columns_in_order(tmp_path):
    db_path = tmp_path / "documents.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE documents (
                id TEXT,
                title TEXT,
                body TEXT,
                updated_at TEXT
            )
            """
        )
        conn.executemany(
            "INSERT INTO documents (id, title, body, updated_at) VALUES (?, ?, ?, ?)",
            [
                ("1", "Alpha", "Beta", "2026-01-01T00:00:00"),
                ("2", "Gamma", "Delta", "2026-01-01T00:00:00"),
            ],
        )
        conn.commit()

    config_path = tmp_path / "config.toml"
    config_path.write_text(
        f"""
[sqlite]
path = "{db_path}"
table = "documents"
id_column = "id"
content_column = ["title", "body"]
updated_at_column = "updated_at"

[batch]
models = ["text-embedding-3-small"]
completion_window = "24h"
poll_interval_seconds = 2
max_batch_size = 100

[chroma]
host = "127.0.0.1"
port = 8000
collection_name = "document_embeddings"

[state]
tracking_db_path = "{tmp_path / "state.db"}"
""",
        encoding="utf-8",
    )

    app_config = load_config(config_path)
    repo = SQLiteDocumentRepository(app_config.sqlite)

    documents, _ = repo.load_documents()

    assert [document.content for document in documents] == [
        "Alpha\n\nBeta",
        "Gamma\n\nDelta",
    ]


def test_custom_id_generation_is_deterministic_and_parseable():
    first = make_custom_id("doc-1", "text-embedding-3-small")
    second = make_custom_id("doc-1", "text-embedding-3-small")

    assert first == second
    assert parse_custom_id(first) == ("doc-1", "text-embedding-3-small")


def test_sqlite_repository_loads_documents_in_deterministic_id_order(tmp_path):
    db_path = tmp_path / "documents.db"
    with sqlite3.connect(db_path) as conn:
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
                ("3", "gamma", "2026-01-01T00:00:00"),
                ("1", "alpha", "2026-01-01T00:00:00"),
                ("2", "beta", "2026-01-01T00:00:00"),
            ],
        )
        conn.commit()

    config_path = tmp_path / "config.toml"
    config_path.write_text(
        f"""
[sqlite]
path = "{db_path}"
table = "documents"
id_column = "id"
content_column = ["content"]
updated_at_column = "updated_at"

[batch]
models = ["text-embedding-3-small"]
completion_window = "24h"
poll_interval_seconds = 2
max_batch_size = 100

[chroma]
host = "127.0.0.1"
port = 8000
collection_name = "document_embeddings"

[state]
tracking_db_path = "{tmp_path / "state.db"}"
""",
        encoding="utf-8",
    )

    app_config = load_config(config_path)
    repo = SQLiteDocumentRepository(app_config.sqlite)

    documents, _ = repo.load_documents()

    assert [document.document_id for document in documents] == ["1", "2", "3"]


def test_sqlite_repository_rejects_missing_content_column_from_mapping(tmp_path):
    db_path = tmp_path / "documents.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE documents (
                id TEXT,
                title TEXT,
                updated_at TEXT
            )
            """
        )
        conn.executemany(
            "INSERT INTO documents (id, title, updated_at) VALUES (?, ?, ?)",
            [("1", "alpha", "2026-01-01T00:00:00")],
        )
        conn.commit()

    config_path = tmp_path / "config.toml"
    config_path.write_text(
        f"""
[sqlite]
path = "{db_path}"
table = "documents"
id_column = "id"
content_column = ["title", "body"]
updated_at_column = "updated_at"

[batch]
models = ["text-embedding-3-small"]
completion_window = "24h"
poll_interval_seconds = 2
max_batch_size = 100

[chroma]
host = "127.0.0.1"
port = 8000
collection_name = "document_embeddings"

[state]
tracking_db_path = "{tmp_path / "state.db"}"
""",
        encoding="utf-8",
    )

    app_config = load_config(config_path)
    repo = SQLiteDocumentRepository(app_config.sqlite)

    with pytest.raises(
        SQLiteSourceError,
        match="Configured columns missing from documents: body",
    ):
        repo.load_documents()
