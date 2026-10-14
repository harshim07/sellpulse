#!/bin/bash
set -euo pipefail

SALES_CSV="${SALES_CSV:-/app/data/sales.csv}"
EXPECTED_TRANSACTION_COUNT="$(
    python3 -c 'import csv, sys; source = open(sys.argv[1], newline="", encoding="utf-8-sig"); print(sum(1 for _ in csv.DictReader(source)))' \
        "$SALES_CSV"
)"
export SALES_CSV EXPECTED_TRANSACTION_COUNT

python3 -u /app/consumer/consumer.py &
consumer_pid=$!

/bin/bash /app/scheduler/run.sh &
scheduler_pid=$!

cleanup() {
    kill "$consumer_pid" "$scheduler_pid" 2>/dev/null || true
    wait "$consumer_pid" "$scheduler_pid" 2>/dev/null || true
}
trap cleanup EXIT

python3 -u /app/producer/producer.py

set +e
wait -n "$consumer_pid" "$scheduler_pid"
status=$?
set -e

if [ "$status" -eq 0 ]; then
    echo "A long-running pipeline process exited unexpectedly." >&2
    exit 1
fi
echo "A long-running pipeline process exited with status $status." >&2
exit "$status"
