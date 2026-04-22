from __future__ import annotations

from reltovec.ids import make_custom_id
from reltovec.models import DocumentRecord, EmbeddingWorkItem


def plan_work_items(
    documents: list[DocumentRecord], models: list[str]
) -> list[EmbeddingWorkItem]:
    work_items: list[EmbeddingWorkItem] = []
    for document in documents:
        for model in models:
            cleaned_model = model.strip()
            if not cleaned_model:
                continue
            work_items.append(
                EmbeddingWorkItem(
                    document_id=document.document_id,
                    model=cleaned_model,
                    content=document.content,
                    custom_id=make_custom_id(document.document_id, cleaned_model),
                    source_table=document.source_table,
                )
            )
    return work_items


def chunk_work_items(
    work_items: list[EmbeddingWorkItem],
    max_batch_size: int,
) -> list[list[EmbeddingWorkItem]]:
    if max_batch_size <= 0:
        raise ValueError("max_batch_size must be positive")
    return [
        work_items[index : index + max_batch_size]
        for index in range(0, len(work_items), max_batch_size)
    ]
