from __future__ import annotations

import pytest

from brcrawl_embedder.cli import _build_parser


def test_index_limit_argument_accepts_positive_integer():
    parser = _build_parser()

    args = parser.parse_args(["index", "--limit", "5000"])

    assert args.command == "index"
    assert args.limit == 5000


@pytest.mark.parametrize("invalid", ["0", "-1"])
def test_index_limit_argument_rejects_non_positive_values(invalid):
    parser = _build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["index", "--limit", invalid])
