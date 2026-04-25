#!/bin/bash

if ! uv --version >/dev/null 2>&1; then
    echo "This script needs uv installed"
    echo "See https://docs.astral.sh/uv/"
    exit 1
fi

if ! jq --version >/dev/null 2>&1; then
    echo "This script needs jq installed"
    echo "See https://jqlang.org/"
    exit 1
fi

echo ".................."

# cleanup failed batches
for failed_batch in $(uv run reltovec status | jq -r '.[] | select(.status == "failed") | .batch_id'); do
    uv run reltovec delete "$failed_batch"
done

# check ongoing batches
ongoing_batches=0
for batch in $(uv run reltovec status | jq '.[] | select(.status != "completed") | .status'); do
    echo "found batch with status <<$batch>>"
    ongoing_batches=$((ongoing_batches+1))
done

echo "Currently processing $ongoing_batches batches."

# try to keep two batches at all times
if [[ "$ongoing_batches" -lt 2 ]]; then
    uv run reltovec index --cutoff-column published_at --cutoff-value 2022-01-01 --limit 2000 --no-wait
fi
