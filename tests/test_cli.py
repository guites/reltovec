from __future__ import annotations

import json
import sys

import pytest

from brcrawl_embedder.config import (
    AppConfig,
    BatchConfig,
    ChromaConfig,
    SQLiteConfig,
    StateConfig,
)
from brcrawl_embedder.cli import _build_parser
from brcrawl_embedder.models import BatchJobRecord, PurgeSummary


def test_index_limit_argument_accepts_positive_integer():
    parser = _build_parser()

    args = parser.parse_args(["index", "--limit", "5000"])

    assert args.command == "index"
    assert args.limit == 5000


@pytest.mark.parametrize("invalid", ["0", "-1"])
def test_index_limit_argument_rejects_non_positive_values(invalid):
    parser = _build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["index", "--limit", invalid])


def test_purge_error_code_argument_accepts_non_empty_string():
    parser = _build_parser()

    args = parser.parse_args(["purge", "--error-code", "timeout"])

    assert args.command == "purge"
    assert args.error_code == "timeout"


def test_purge_error_code_argument_rejects_empty_string():
    parser = _build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["purge", "--error-code", "   "])


def _config_for_cli() -> AppConfig:
    return AppConfig(
        sqlite=SQLiteConfig(
            path="./data/documents.db",
            table="feed_items",
            id_column="id",
            content_column="content",
            updated_at_column="created_at",
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


def test_status_command_refreshes_batches_before_listing(monkeypatch, capsys):
    from brcrawl_embedder import cli

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
        pass

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
        ["brcrawl-embedder", "--config", "ignored.toml", "status", "--limit", "5"],
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
    from brcrawl_embedder import cli

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
        pass

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
            "brcrawl-embedder",
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
