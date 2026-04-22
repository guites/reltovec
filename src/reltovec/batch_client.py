from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
from typing import Any, Protocol

from reltovec.models import BatchJobRecord


class BatchClient(Protocol):
    def upload_batch_input(self, jsonl_text: str) -> str:
        raise NotImplementedError

    def create_embedding_batch(
        self, input_file_id: str, completion_window: str
    ) -> BatchJobRecord:
        raise NotImplementedError

    def retrieve_batch(self, batch_id: str) -> BatchJobRecord:
        raise NotImplementedError

    def fetch_file_text(self, file_id: str) -> str:
        raise NotImplementedError


class OpenAIBatchClientAdapter:
    def __init__(self, api_key: str | None = None):
        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "openai package is required for OpenAIBatchClientAdapter"
            ) from exc

        self._client = OpenAI(api_key=api_key)

    def upload_batch_input(self, jsonl_text: str) -> str:
        payload = BytesIO(jsonl_text.encode("utf-8"))
        payload.name = "embeddings_batch.jsonl"
        uploaded = self._client.files.create(file=payload, purpose="batch")
        return str(uploaded.id)

    def create_embedding_batch(
        self, input_file_id: str, completion_window: str
    ) -> BatchJobRecord:
        created = self._client.batches.create(
            input_file_id=input_file_id,
            endpoint="/v1/embeddings",
            completion_window=completion_window,
        )
        return coerce_batch_record(created)

    def retrieve_batch(self, batch_id: str) -> BatchJobRecord:
        batch = self._client.batches.retrieve(batch_id)
        return coerce_batch_record(batch)

    def fetch_file_text(self, file_id: str) -> str:
        content = self._client.files.content(file_id)

        text_value = getattr(content, "text", None)
        if isinstance(text_value, str):
            return text_value

        read_fn = getattr(content, "read", None)
        if callable(read_fn):
            raw = read_fn()
            if isinstance(raw, bytes):
                return raw.decode("utf-8")
            return str(raw)

        return str(content)


def coerce_batch_record(payload: Any) -> BatchJobRecord:
    batch_id = _pick(payload, "id")
    status = _pick(payload, "status")
    input_file_id = _pick(payload, "input_file_id")
    output_file_id = _pick(payload, "output_file_id")
    error_file_id = _pick(payload, "error_file_id")

    created_at = _pick(payload, "created_at")
    completed_at = _pick(payload, "completed_at")

    submitted_at_iso = _to_iso(created_at) or datetime.now(timezone.utc).isoformat()
    completed_at_iso = _to_iso(completed_at)

    return BatchJobRecord(
        batch_id=str(batch_id),
        status=str(status),
        input_file_id=str(input_file_id),
        output_file_id=_or_none(output_file_id),
        error_file_id=_or_none(error_file_id),
        submitted_at=submitted_at_iso,
        completed_at=completed_at_iso,
    )


def _pick(payload: Any, key: str) -> Any:
    if isinstance(payload, dict):
        return payload.get(key)
    return getattr(payload, key, None)


def _to_iso(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc).isoformat()
    if isinstance(value, str) and value.strip():
        return value
    return None


def _or_none(value: Any) -> str | None:
    if value is None:
        return None
    as_text = str(value).strip()
    return as_text or None
