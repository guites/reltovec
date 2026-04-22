from __future__ import annotations

import json

from reltovec.batch_builder import build_batch_jsonl
from reltovec.batch_result_parser import parse_batch_results
from reltovec.models import EmbeddingWorkItem


def test_batch_jsonl_contains_expected_embedding_request_shape():
    item = EmbeddingWorkItem(
        document_id="42",
        model="text-embedding-3-small",
        content="hello world",
        custom_id="doc:42|model:text-embedding-3-small",
        source_table="documents",
    )

    payload = build_batch_jsonl([item])
    line = json.loads(payload)

    assert line["custom_id"] == item.custom_id
    assert line["method"] == "POST"
    assert line["url"] == "/v1/embeddings"
    assert line["body"]["model"] == "text-embedding-3-small"
    assert line["body"]["input"] == "hello world"


def test_batch_result_parser_handles_success_and_errors():
    output_text = "\n".join(
        [
            json.dumps(
                {
                    "custom_id": "doc:42|model:text-embedding-3-small",
                    "response": {
                        "status_code": 200,
                        "body": {
                            "model": "text-embedding-3-small",
                            "data": [{"embedding": [0.1, 0.2, 0.3]}],
                        },
                    },
                }
            ),
            json.dumps(
                {
                    "custom_id": "doc:99|model:text-embedding-3-small",
                    "response": {
                        "status_code": 400,
                        "body": {
                            "error": {
                                "code": "bad_request",
                                "message": "bad input",
                            }
                        },
                    },
                }
            ),
        ]
    )

    error_text = json.dumps(
        {
            "custom_id": "doc:100|model:text-embedding-3-small",
            "error": {"code": "token_limit", "message": "too large"},
        }
    )

    parsed = parse_batch_results(output_text=output_text, error_text=error_text)

    assert len(parsed.embeddings) == 1
    assert parsed.embeddings[0].document_id == "42"
    assert parsed.embeddings[0].model == "text-embedding-3-small"
    assert parsed.embeddings[0].embedding == [0.1, 0.2, 0.3]

    assert len(parsed.item_failures) == 2
    assert {failure.error_code for failure in parsed.item_failures} == {
        "bad_request",
        "token_limit",
    }
