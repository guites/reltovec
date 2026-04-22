from __future__ import annotations

import argparse
from datetime import datetime
import json
import sys

from reltovec.batch_client import OpenAIBatchClientAdapter
from reltovec.config import ConfigError, load_config
from reltovec.orchestrator import IndexOrchestrator
from reltovec.sqlite_source import SQLiteDocumentRepository
from reltovec.state_store import BatchStateStore
from reltovec.vector_store import ChromaVectorStore


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be a positive integer")
    return parsed


def _non_empty_string(value: str) -> str:
    parsed = value.strip()
    if not parsed:
        raise argparse.ArgumentTypeError("value must be a non-empty string")
    return parsed


def _cutoff_value(value: str) -> str:
    parsed = value.strip()
    if not parsed:
        raise argparse.ArgumentTypeError("value must be a non-empty string")

    try:
        date_value = datetime.strptime(parsed, "%Y-%m-%d")
        if date_value.strftime("%Y-%m-%d") == parsed:
            return f"{parsed}T00:00:00"
    except ValueError:
        pass

    try:
        datetime_value = datetime.strptime(parsed, "%Y-%m-%dT%H:%M:%S")
        if datetime_value.strftime("%Y-%m-%dT%H:%M:%S") == parsed:
            return parsed
    except ValueError:
        pass

    raise argparse.ArgumentTypeError(
        "value must match YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS"
    )


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    if args.command == "index":
        has_cutoff_column = args.cutoff_column is not None
        has_cutoff_value = args.cutoff_value is not None
        if has_cutoff_column != has_cutoff_value:
            parser.error("index requires both --cutoff-column and --cutoff-value together")

    try:
        config = load_config(args.config)

        if args.command == "index":
            source_repo = SQLiteDocumentRepository(config.sqlite)
            state_store = BatchStateStore(config.state.tracking_db_path)
            vector_store = ChromaVectorStore(
                host=config.chroma.host,
                port=config.chroma.port,
                collection_name=config.chroma.collection_name,
            )
            batch_client = OpenAIBatchClientAdapter(api_key=config.batch.api_key)
            orchestrator = IndexOrchestrator(
                config=config,
                source_repo=source_repo,
                batch_client=batch_client,
                state_store=state_store,
                vector_store=vector_store,
            )
            summary = orchestrator.index(
                wait_for_completion=not args.no_wait,
                document_limit=args.limit,
                cutoff_column=args.cutoff_column,
                cutoff_value=args.cutoff_value,
            )
            print(json.dumps(summary.__dict__, indent=2, sort_keys=True))
            return 0

        if args.command == "status":
            source_repo = SQLiteDocumentRepository(config.sqlite)
            state_store = BatchStateStore(config.state.tracking_db_path)
            vector_store = ChromaVectorStore(
                host=config.chroma.host,
                port=config.chroma.port,
                collection_name=config.chroma.collection_name,
            )
            batch_client = OpenAIBatchClientAdapter(api_key=config.batch.api_key)
            orchestrator = IndexOrchestrator(
                config=config,
                source_repo=source_repo,
                batch_client=batch_client,
                state_store=state_store,
                vector_store=vector_store,
            )
            reconciliation = orchestrator.refresh_status(
                wait_for_completion=False,
                batch_list_limit=args.limit,
            )
            batches = [batch.__dict__ for batch in reconciliation.batches]
            print(json.dumps(batches, indent=2, sort_keys=True))
            return 0

        if args.command == "purge":
            state_store = BatchStateStore(config.state.tracking_db_path)
            orchestrator = IndexOrchestrator(
                config=config,
                source_repo=None,
                batch_client=None,
                state_store=state_store,
                vector_store=None,
            )
            summary = orchestrator.purge(error_code=args.error_code)
            print(json.dumps(summary.__dict__, indent=2, sort_keys=True))
            return 0

        if args.command == "get-by-document-id":
            vector_store = ChromaVectorStore(
                host=config.chroma.host,
                port=config.chroma.port,
                collection_name=config.chroma.collection_name,
            )
            vector_store.ensure_collection()
            rows = vector_store.query_by_document_id(
                document_id=args.document_id,
                model=args.model,
                include_embeddings=not args.no_embeddings,
            )
            print(json.dumps([row.__dict__ for row in rows], indent=2, sort_keys=True))
            return 0

        parser.print_help()
        return 1
    except ConfigError as exc:
        print(f"Config error: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # pragma: no cover
        print(f"Error: {exc}", file=sys.stderr)
        return 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="SQLite -> OpenAI Batch -> Chroma embeddings pipeline"
    )
    parser.add_argument(
        "--config", default="config.toml", help="Path to TOML config file"
    )

    subparsers = parser.add_subparsers(dest="command")

    index_parser = subparsers.add_parser(
        "index", help="Submit and process embedding batches"
    )
    index_parser.add_argument(
        "--no-wait", action="store_true", help="Submit jobs and return without waiting"
    )
    index_parser.add_argument(
        "--limit",
        type=_positive_int,
        default=None,
        help="Maximum number of source documents to index in this run",
    )
    index_parser.add_argument(
        "--cutoff-column",
        type=_non_empty_string,
        default=None,
        help="Optional SQLite date/datetime column used for source filtering",
    )
    index_parser.add_argument(
        "--cutoff-value",
        type=_cutoff_value,
        default=None,
        help="Optional cutoff value (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)",
    )

    status_parser = subparsers.add_parser(
        "status", help="Show tracked batch lifecycle state"
    )
    status_parser.add_argument(
        "--limit",
        type=_positive_int,
        default=100,
        help="Maximum number of batches to display",
    )

    purge_parser = subparsers.add_parser(
        "purge", help="Delete failed work items by failure error code"
    )
    purge_parser.add_argument(
        "--error-code",
        required=True,
        type=_non_empty_string,
        help="Exact failure error code to purge from local state",
    )

    query_parser = subparsers.add_parser(
        "get-by-document-id", help="Query embeddings by relational document id"
    )
    query_parser.add_argument("document_id", help="Relational document identifier")
    query_parser.add_argument(
        "--model", default=None, help="Optional embedding model filter"
    )
    query_parser.add_argument(
        "--no-embeddings",
        action="store_true",
        help="Return metadata only, omit vector payload",
    )

    return parser


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
