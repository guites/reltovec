from __future__ import annotations

from brcrawl_embedder.models import ParsedEmbedding
from brcrawl_embedder.vector_store import ChromaVectorStore


class FakeCollection:
    def __init__(self):
        self._rows: dict[str, tuple[list[float], dict]] = {}

    def upsert(self, ids, embeddings, metadatas):
        for index, vector_id in enumerate(ids):
            self._rows[vector_id] = (embeddings[index], metadatas[index])

    def get(self, where, include):
        matches = []
        for vector_id, (embedding, metadata) in self._rows.items():
            if all(metadata.get(key) == value for key, value in where.items()):
                matches.append((vector_id, embedding, metadata))

        ids = [row[0] for row in matches]
        metadatas = [row[2] for row in matches]
        payload = {"ids": ids, "metadatas": metadatas}
        if "embeddings" in include:
            payload["embeddings"] = [row[1] for row in matches]
        return payload


class FakeChromaClient:
    def __init__(self):
        self.collection = FakeCollection()

    def get_or_create_collection(self, name):
        return self.collection


def test_upsert_is_idempotent_and_query_filters_by_document_and_model():
    store = ChromaVectorStore(
        host="127.0.0.1",
        port=8000,
        collection_name="document_embeddings",
        client=FakeChromaClient(),
    )
    store.ensure_collection()

    store.upsert_embeddings(
        [
            ParsedEmbedding(
                custom_id="doc:1|model:text-embedding-3-small",
                document_id="1",
                model="text-embedding-3-small",
                embedding=[0.1, 0.2],
            ),
            ParsedEmbedding(
                custom_id="doc:1|model:text-embedding-3-large",
                document_id="1",
                model="text-embedding-3-large",
                embedding=[0.9, 0.8],
            ),
        ]
    )

    store.upsert_embeddings(
        [
            ParsedEmbedding(
                custom_id="doc:1|model:text-embedding-3-small",
                document_id="1",
                model="text-embedding-3-small",
                embedding=[1.0, 1.1],
            )
        ]
    )

    all_rows = store.query_by_document_id(document_id="1")
    assert len(all_rows) == 2

    filtered_rows = store.query_by_document_id(
        document_id="1", model="text-embedding-3-small"
    )
    assert len(filtered_rows) == 1
    assert filtered_rows[0].embedding == [1.0, 1.1]
