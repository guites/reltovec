from __future__ import annotations

import json
import sys

import pytest

from reltovec.config import (
    AppConfig,
    BatchConfig,
    ChromaConfig,
    SQLiteConfig,
    StateConfig,
)
from reltovec.cli import _build_parser
from reltovec.models import BatchJobRecord, IndexSummary, PurgeSummary


def test_index_limit_argument_accepts_positive_integer():
    parser = _build_parser()

    args = parser.parse_args(["index", "--limit", "5000"])

    assert args.command == "index"
    assert args.limit == 5000


def test_index_cutoff_value_argument_accepts_date_and_normalizes_midnight():
    parser = _build_parser()

    args = parser.parse_args(
        ["index", "--cutoff-column", "updated_at", "--cutoff-value", "2026-01-02"]
    )

    assert args.cutoff_column == "updated_at"
    assert args.cutoff_value == "2026-01-02T00:00:00"


def test_index_cutoff_value_argument_accepts_datetime():
    parser = _build_parser()

    args = parser.parse_args(
        [
            "index",
            "--cutoff-column",
            "updated_at",
            "--cutoff-value",
            "2026-01-02T08:55:10",
        ]
    )

    assert args.cutoff_value == "2026-01-02T08:55:10"


@pytest.mark.parametrize("invalid", ["0", "-1"])
def test_index_limit_argument_rejects_non_positive_values(invalid):
    parser = _build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["index", "--limit", invalid])


@pytest.mark.parametrize(
    "invalid",
    [
        "2026/01/02",
        "2026-1-02",
        "2026-01-02 08:55:10",
        "2026-01-02T08:55",
    ],
)
def test_index_cutoff_value_rejects_invalid_formats(invalid):
    parser = _build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["index", "--cutoff-value", invalid])


def test_purge_error_code_argument_accepts_non_empty_string():
    parser = _build_parser()

    args = parser.parse_args(["purge", "--error-code", "timeout"])

    assert args.command == "purge"
    assert args.error_code == "timeout"


def test_purge_error_code_argument_rejects_empty_string():
    parser = _build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["purge", "--error-code", "   "])


def test_index_requires_cutoff_column_and_value_together(monkeypatch):
    from reltovec import cli

    monkeypatch.setattr(
        cli,
        "load_config",
        lambda _: (_ for _ in ()).throw(AssertionError("load_config must not run")),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["reltovec", "index", "--cutoff-column", "updated_at"],
    )

    with pytest.raises(SystemExit):
        cli.main()


def _config_for_cli() -> AppConfig:
    return AppConfig(
        sqlite=SQLiteConfig(
            path="./data/documents.db",
            table="feed_items",
            id_column="id",
            content_column=["content"],
        ),
        batch=BatchConfig(
            models=["text-embedding-3-small"],
            completion_window="24h",
            poll_interval_seconds=2,
            max_batch_size=2000,
        ),
        chroma=ChromaConfig(
            host="127.0.0.1",
            port=8000,
            collection_name="document_embeddings",
        ),
        state=StateConfig(tracking_db_path="./data/pipeline_state.db"),
    )


def test_index_command_passes_cutoff_arguments_to_orchestrator(monkeypatch, capsys):
    from reltovec import cli

    index_calls: list[tuple[bool, int | None, str | None, str | None]] = []

    class FakeStateStore:
        def __init__(self, db_path: str):
            self.db_path = db_path

    class FakeVectorStore:
        def __init__(self, host: str, port: int, collection_name: str):
            self.host = host
            self.port = port
            self.collection_name = collection_name

    class FakeBatchClient:
        def __init__(self, api_key: str | None = None):
            self.api_key = api_key

    class FakeSourceRepository:
        def __init__(self, config):
            self.config = config

    class FakeOrchestrator:
        def __init__(
            self,
            config,
            source_repo,
            batch_client,
            state_store,
            vector_store,
            sleep_fn=None,
        ):
            self.config = config
            self.source_repo = source_repo
            self.batch_client = batch_client
            self.state_store = state_store
            self.vector_store = vector_store
            self.sleep_fn = sleep_fn

        def index(
            self,
            wait_for_completion: bool = True,
            document_limit=None,
            cutoff_column=None,
            cutoff_value=None,
        ):
            index_calls.append(
                (wait_for_completion, document_limit, cutoff_column, cutoff_value)
            )
            return IndexSummary(
                total_documents_seen=0,
                eligible_documents=0,
                skipped_empty_content=0,
                skipped_missing_id=0,
                submitted_batches=0,
                processed_batches=0,
                upserted_embeddings=0,
                item_failures=0,
                requested_document_limit=document_limit,
            )

        def refresh_status(
            self, wait_for_completion: bool = False, batch_list_limit: int = 100
        ):
            raise AssertionError("index command must not call refresh_status()")

        def purge(self, error_code: str):
            raise AssertionError("index command must not call purge()")

    monkeypatch.setattr(cli, "load_config", lambda _: _config_for_cli())
    monkeypatch.setattr(cli, "BatchStateStore", FakeStateStore)
    monkeypatch.setattr(cli, "ChromaVectorStore", FakeVectorStore)
    monkeypatch.setattr(cli, "OpenAIBatchClientAdapter", FakeBatchClient)
    monkeypatch.setattr(cli, "SQLiteDocumentRepository", FakeSourceRepository)
    monkeypatch.setattr(cli, "IndexOrchestrator", FakeOrchestrator)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "reltovec",
            "--config",
            "ignored.toml",
            "index",
            "--no-wait",
            "--limit",
            "5",
            "--cutoff-column",
            "updated_at",
            "--cutoff-value",
            "2026-01-02",
        ],
    )

    exit_code = cli.main()

    assert exit_code == 0
    assert index_calls == [(False, 5, "updated_at", "2026-01-02T00:00:00")]
    payload = json.loads(capsys.readouterr().out)
    assert payload["requested_document_limit"] == 5


def test_status_command_refreshes_batches_before_listing(monkeypatch, capsys):
    from reltovec import cli

    events: list[str] = []
    class FakeStateStore:
        def __init__(self, db_path: str):
            self.db_path = db_path

    class FakeVectorStore:
        def __init__(self, host: str, port: int, collection_name: str):
            self.host = host
            self.port = port
            self.collection_name = collection_name

    class FakeBatchClient:
        def __init__(self, api_key: str | None = None):
            self.api_key = api_key

    class FakeSourceRepository:
        def __init__(self, config):
            self.config = config

    class FakeOrchestrator:
        def __init__(
            self,
            config,
            source_repo,
            batch_client,
            state_store,
            vector_store,
            sleep_fn=None,
        ):
            self.config = config
            self.source_repo = source_repo
            self.batch_client = batch_client
            self.state_store = state_store
            self.vector_store = vector_store
            self.sleep_fn = sleep_fn

        def refresh_status(
            self, wait_for_completion: bool = False, batch_list_limit: int = 100
        ):
            events.append(f"refresh:{wait_for_completion}:{batch_list_limit}")

            class _Summary:
                batches = [
                    BatchJobRecord(
                        batch_id="batch-1",
                        status="completed",
                        input_file_id="file-1",
                        submitted_at="2026-01-01T00:00:00+00:00",
                        documents_sent_count=5,
                        failed_item_count=2,
                        failure_error_codes=["invalid_request", "timeout"],
                    )
                ]

            return _Summary()

        def index(self, wait_for_completion: bool = True, document_limit=None):
            raise AssertionError("status must not call index()")

    monkeypatch.setattr(cli, "load_config", lambda _: _config_for_cli())
    monkeypatch.setattr(cli, "BatchStateStore", FakeStateStore)
    monkeypatch.setattr(cli, "ChromaVectorStore", FakeVectorStore)
    monkeypatch.setattr(cli, "OpenAIBatchClientAdapter", FakeBatchClient)
    monkeypatch.setattr(cli, "SQLiteDocumentRepository", FakeSourceRepository)
    monkeypatch.setattr(cli, "IndexOrchestrator", FakeOrchestrator)
    monkeypatch.setattr(
        sys,
        "argv",
        ["reltovec", "--config", "ignored.toml", "status", "--limit", "5"],
    )

    exit_code = cli.main()

    assert exit_code == 0
    assert events == ["refresh:False:5"]

    payload = json.loads(capsys.readouterr().out)
    assert isinstance(payload, list)
    assert payload[0]["batch_id"] == "batch-1"
    assert payload[0]["status"] == "completed"
    assert payload[0]["documents_sent_count"] == 5
    assert payload[0]["failed_item_count"] == 2
    assert payload[0]["failure_error_codes"] == ["invalid_request", "timeout"]


def test_purge_command_executes_orchestrator_and_prints_summary(monkeypatch, capsys):
    from reltovec import cli

    events: list[str] = []

    class FakeStateStore:
        def __init__(self, db_path: str):
            self.db_path = db_path

    class FakeVectorStore:
        def __init__(self, host: str, port: int, collection_name: str):
            self.host = host
            self.port = port
            self.collection_name = collection_name

    class FakeBatchClient:
        def __init__(self, api_key: str | None = None):
            self.api_key = api_key

    class FakeSourceRepository:
        def __init__(self, config):
            self.config = config

    class FakeOrchestrator:
        def __init__(
            self,
            config,
            source_repo,
            batch_client,
            state_store,
            vector_store,
            sleep_fn=None,
        ):
            self.config = config
            self.source_repo = source_repo
            self.batch_client = batch_client
            self.state_store = state_store
            self.vector_store = vector_store
            self.sleep_fn = sleep_fn

        def purge(self, error_code: str):
            events.append(f"purge:{error_code}")
            return PurgeSummary(
                error_code=error_code,
                deleted_failures=3,
                released_work_items=2,
            )

        def refresh_status(
            self, wait_for_completion: bool = False, batch_list_limit: int = 100
        ):
            raise AssertionError("purge must not call refresh_status()")

        def index(self, wait_for_completion: bool = True, document_limit=None):
            raise AssertionError("purge must not call index()")

    monkeypatch.setattr(cli, "load_config", lambda _: _config_for_cli())
    monkeypatch.setattr(cli, "BatchStateStore", FakeStateStore)
    monkeypatch.setattr(cli, "ChromaVectorStore", FakeVectorStore)
    monkeypatch.setattr(cli, "OpenAIBatchClientAdapter", FakeBatchClient)
    monkeypatch.setattr(cli, "SQLiteDocumentRepository", FakeSourceRepository)
    monkeypatch.setattr(cli, "IndexOrchestrator", FakeOrchestrator)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "reltovec",
            "--config",
            "ignored.toml",
            "purge",
            "--error-code",
            "timeout",
        ],
    )

    exit_code = cli.main()

    assert exit_code == 0
    assert events == ["purge:timeout"]

    payload = json.loads(capsys.readouterr().out)
    assert payload == {
        "deleted_failures": 3,
        "error_code": "timeout",
        "released_work_items": 2,
    }
