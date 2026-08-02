#!/bin/sh
set -eu

PROJECT_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
LOG_DIR="$PROJECT_ROOT/.cache/logs"
LOG_FILE="$LOG_DIR/verify.log"

mkdir -p "$LOG_DIR"
if make -C "$PROJECT_ROOT" verify > "$LOG_FILE" 2>&1; then
    cat "$LOG_FILE"
else
    status=$?
    cat "$LOG_FILE" >&2
    exit "$status"
fi
