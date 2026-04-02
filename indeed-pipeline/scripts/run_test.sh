#!/bin/bash
# Run batch_test.py with real-time log output.
# Usage:
#   bash scripts/run_test.sh "https://www.indeed.com/viewjob?jk=..."
#   bash scripts/run_test.sh "url1" "url2"    # multiple URLs

set -euo pipefail
cd "$(dirname "$0")/.."

LOG="/tmp/run_test.log"

# Kill any zombie batch_test processes
pkill -f "python3.12.*batch_test" 2>/dev/null || true
sleep 1

# Build URL input
URL_INPUT=""
for url in "$@"; do
    URL_INPUT+="$url"$'\n'
done

# Run in background, log to file
echo "$URL_INPUT" | PYTHONUNBUFFERED=1 python3.12 -u scripts/batch_test.py > "$LOG" 2>&1 &
PID=$!
echo "[run_test] PID: $PID → log: $LOG"
echo "[run_test] Watching output (Ctrl+C to detach, test keeps running)..."
echo ""

# Stream log in real time
tail -f "$LOG" --pid=$PID
