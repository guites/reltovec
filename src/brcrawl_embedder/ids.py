from __future__ import annotations

from urllib.parse import quote, unquote


class CustomIdError(ValueError):
    pass


def make_custom_id(document_id: str, model: str) -> str:
    encoded_document_id = quote(str(document_id), safe="")
    encoded_model = quote(model, safe="")
    return f"doc:{encoded_document_id}|model:{encoded_model}"


def parse_custom_id(custom_id: str) -> tuple[str, str]:
    if "|" not in custom_id or not custom_id.startswith("doc:"):
        raise CustomIdError(f"Invalid custom_id format: {custom_id}")
    left, right = custom_id.split("|", maxsplit=1)
    if not right.startswith("model:"):
        raise CustomIdError(f"Invalid custom_id format: {custom_id}")

    raw_document_id = left.removeprefix("doc:")
    raw_model = right.removeprefix("model:")
    if raw_document_id == "" or raw_model == "":
        raise CustomIdError(f"Invalid custom_id format: {custom_id}")

    return unquote(raw_document_id), unquote(raw_model)
