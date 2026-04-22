from __future__ import annotations

import json
from typing import Any

from reltovec.ids import CustomIdError, parse_custom_id
from reltovec.models import (
    BatchItemFailure,
    ParsedBatchResults,
    ParsedEmbedding,
)


def parse_batch_results(
    output_text: str, error_text: str | None = None
) -> ParsedBatchResults:
    embeddings: list[ParsedEmbedding] = []
    failures: list[BatchItemFailure] = []

    for line in output_text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError:
            failures.append(
                BatchItemFailure(
                    None, "invalid_json", f"Invalid JSON output line: {stripped}"
                )
            )
            continue

        custom_id = payload.get("custom_id")
        if not isinstance(custom_id, str):
            failures.append(
                BatchItemFailure(
                    None, "missing_custom_id", "Batch output item missing custom_id"
                )
            )
            continue

        try:
            document_id, model_from_custom_id = parse_custom_id(custom_id)
        except CustomIdError as exc:
            failures.append(BatchItemFailure(custom_id, "invalid_custom_id", str(exc)))
            continue

        response = payload.get("response") or {}
        status_code = response.get("status_code")
        body = response.get("body") or {}

        if not isinstance(status_code, int) or status_code < 200 or status_code >= 300:
            failures.append(
                BatchItemFailure(
                    custom_id,
                    _extract_error_code(body),
                    _extract_error_message(
                        body, fallback=f"Request failed with status {status_code}"
                    ),
                )
            )
            continue

        data_rows = body.get("data")
        if not isinstance(data_rows, list) or not data_rows:
            failures.append(
                BatchItemFailure(
                    custom_id,
                    "missing_embedding",
                    "Missing embedding data in response body",
                )
            )
            continue

        embedding = data_rows[0].get("embedding")
        if not isinstance(embedding, list):
            failures.append(
                BatchItemFailure(
                    custom_id, "invalid_embedding", "Embedding payload is not a list"
                )
            )
            continue

        model = (
            body.get("model")
            if isinstance(body.get("model"), str)
            else model_from_custom_id
        )
        numeric_embedding = [float(value) for value in embedding]

        embeddings.append(
            ParsedEmbedding(
                custom_id=custom_id,
                document_id=document_id,
                model=model,
                embedding=numeric_embedding,
            )
        )

    if error_text:
        failures.extend(parse_error_file(error_text))

    return ParsedBatchResults(embeddings=embeddings, item_failures=failures)


def parse_error_file(error_text: str) -> list[BatchItemFailure]:
    failures: list[BatchItemFailure] = []

    for line in error_text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError:
            failures.append(
                BatchItemFailure(
                    None, "invalid_json", f"Invalid JSON error line: {stripped}"
                )
            )
            continue

        custom_id = (
            payload.get("custom_id")
            if isinstance(payload.get("custom_id"), str)
            else None
        )
        error_code = _extract_error_code(payload)
        error_message = _extract_error_message(payload, fallback="Batch item failed")
        failures.append(BatchItemFailure(custom_id, error_code, error_message))

    return failures


def _extract_error_code(payload: Any) -> str | None:
    error_object = _find_error_object(payload)
    code = error_object.get("code") if isinstance(error_object, dict) else None
    return code if isinstance(code, str) and code.strip() else None


def _extract_error_message(payload: Any, fallback: str) -> str:
    error_object = _find_error_object(payload)
    if isinstance(error_object, dict):
        message = error_object.get("message")
        if isinstance(message, str) and message.strip():
            return message

    message = payload.get("message") if isinstance(payload, dict) else None
    if isinstance(message, str) and message.strip():
        return message

    return fallback


def _find_error_object(payload: Any) -> dict:
    if isinstance(payload, dict):
        error = payload.get("error")
        if isinstance(error, dict):
            return error

        response = payload.get("response")
        if isinstance(response, dict):
            body = response.get("body")
            if isinstance(body, dict):
                nested_error = body.get("error")
                if isinstance(nested_error, dict):
                    return nested_error

    return {}
