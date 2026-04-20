from __future__ import annotations

from typing import Any, Protocol

from brcrawl_embedder.models import ParsedEmbedding, QueryRow


class VectorStore(Protocol):
    def ensure_collection(self) -> None:
        raise NotImplementedError

    def upsert_embeddings(self, embeddings: list[ParsedEmbedding]) -> None:
        raise NotImplementedError

    def query_by_document_id(
        self,
        document_id: str,
        model: str | None = None,
        include_embeddings: bool = True,
    ) -> list[QueryRow]:
        raise NotImplementedError


class ChromaVectorStore:
    def __init__(
        self,
        host: str,
        port: int,
        collection_name: str,
        client: Any | None = None,
    ):
        self._host = host
        self._port = port
        self._collection_name = collection_name
        self._client = client
        self._collection = None

    def ensure_collection(self) -> None:
        collection = self._get_collection()
        if collection is None:
            raise RuntimeError("Unable to initialize Chroma collection")

    def upsert_embeddings(self, embeddings: list[ParsedEmbedding]) -> None:
        if not embeddings:
            return
        collection = self._get_collection()

        ids = [item.custom_id for item in embeddings]
        vectors = [item.embedding for item in embeddings]
        metadatas = []
        for item in embeddings:
            metadata = {
                "document_id": item.document_id,
                "model": item.model,
            }
            if item.source_table:
                metadata["source_table"] = item.source_table
            if item.updated_at:
                metadata["updated_at"] = item.updated_at
            metadatas.append(metadata)

        collection.upsert(ids=ids, embeddings=vectors, metadatas=metadatas)

    def query_by_document_id(
        self,
        document_id: str,
        model: str | None = None,
        include_embeddings: bool = True,
    ) -> list[QueryRow]:
        collection = self._get_collection()

        where: dict[str, Any] = {"document_id": document_id}
        if model:
            where["model"] = model

        include = ["metadatas"]
        if include_embeddings:
            include.append("embeddings")

        payload = collection.get(where=where, include=include)

        ids = payload.get("ids", [])
        metadatas = payload.get("metadatas", [])
        vectors = payload.get("embeddings", [])

        rows: list[QueryRow] = []
        for index, vector_id in enumerate(ids):
            metadata = (
                metadatas[index] if index < len(metadatas) and metadatas[index] else {}
            )
            vector = (
                vectors[index] if include_embeddings and index < len(vectors) else None
            )
            rows.append(
                QueryRow(
                    vector_id=str(vector_id),
                    document_id=str(metadata.get("document_id", document_id)),
                    model=str(metadata.get("model", "")),
                    embedding=vector,
                    metadata=dict(metadata),
                )
            )

        return rows

    def _get_collection(self) -> Any:
        if self._collection is not None:
            return self._collection

        if self._client is None:
            try:
                import chromadb
            except ImportError as exc:  # pragma: no cover
                raise RuntimeError(
                    "chromadb package is required for ChromaVectorStore"
                ) from exc
            self._client = chromadb.HttpClient(host=self._host, port=self._port)

        self._collection = self._client.get_or_create_collection(
            name=self._collection_name
        )
        return self._collection
