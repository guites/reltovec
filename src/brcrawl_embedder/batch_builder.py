from __future__ import annotations

import json

from brcrawl_embedder.models import EmbeddingWorkItem


def build_batch_jsonl(work_items: list[EmbeddingWorkItem]) -> str:
    lines = []
    for item in work_items:
        payload = {
            "custom_id": item.custom_id,
            "method": "POST",
            "url": "/v1/embeddings",
            "body": {
                "model": item.model,
                "input": item.content,
            },
        }
        lines.append(json.dumps(payload, ensure_ascii=True))
    return "\n".join(lines)
