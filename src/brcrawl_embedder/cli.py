from __future__ import annotations

import argparse
import json
import sys

from brcrawl_embedder.batch_client import OpenAIBatchClientAdapter
from brcrawl_embedder.config import ConfigError, load_config
from brcrawl_embedder.orchestrator import IndexOrchestrator
from brcrawl_embedder.sqlite_source import SQLiteDocumentRepository
from brcrawl_embedder.state_store import BatchStateStore
from brcrawl_embedder.vector_store import ChromaVectorStore


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be a positive integer")
    return parsed


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

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
            batch_client = OpenAIBatchClientAdapter()
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
            batch_client = OpenAIBatchClientAdapter()
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

    status_parser = subparsers.add_parser(
        "status", help="Show tracked batch lifecycle state"
    )
    status_parser.add_argument(
        "--limit",
        type=_positive_int,
        default=100,
        help="Maximum number of batches to display",
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
