#!/bin/sh
set -eu

if [ "$#" -ne 2 ]; then
    echo "usage: $0 ROM.lnx SYMBOLS.lbl" >&2
    exit 2
fi

ROM=$1
SYMBOLS=$2
GEARLYNX=${GEARLYNX:-/Applications/Gearlynx.app/Contents/MacOS/gearlynx}
PORT=${GEARLYNX_DEBUG_PORT:-16502}
LOG=${TMPDIR:-/tmp}/asteroid-patrol-gearlynx-smoke.$$.log
PID=

cleanup() {
    if [ -n "$PID" ] && kill -0 "$PID" 2>/dev/null; then
        kill "$PID" 2>/dev/null || true
        wait "$PID" 2>/dev/null || true
    fi
    rm -f "$LOG"
}
trap cleanup EXIT HUP INT TERM

listener_pids() {
    lsof -nP -t -iTCP:"$PORT" -sTCP:LISTEN 2>/dev/null || true
}

is_gearlynx_process() {
    candidate=$1

    while [ "$candidate" -gt 1 ] 2>/dev/null; do
        if [ "$candidate" -eq "$PID" ]; then
            return 0
        fi
        candidate=$(ps -o ppid= -p "$candidate" 2>/dev/null | tr -d ' ')
        if [ -z "$candidate" ]; then
            return 1
        fi
    done
    return 1
}

if [ ! -x "$GEARLYNX" ]; then
    echo "Gearlynx not found or not executable: $GEARLYNX" >&2
    exit 3
fi
if [ ! -f "$ROM" ] || [ ! -f "$SYMBOLS" ]; then
    echo "ROM or symbol file is missing; build with make rom first" >&2
    exit 2
fi

if [ -n "$(listener_pids)" ]; then
    echo "Gearlynx debug monitor port $PORT is already in use; refusing to misattribute its listener to this launch:" >&2
    lsof -nP -iTCP:"$PORT" -sTCP:LISTEN >&2 || true
    exit 1
fi

"$GEARLYNX" --headless --debug-monitor --debug-monitor-port "$PORT" \
    "$ROM" "$SYMBOLS" >"$LOG" 2>&1 &
PID=$!

attempt=0
while [ "$attempt" -lt 20 ]; do
    if ! kill -0 "$PID" 2>/dev/null; then
        wait "$PID" || status=$?
        echo "Gearlynx exited during headless ROM launch (status ${status:-0}):" >&2
        cat "$LOG" >&2
        exit 1
    fi
    if nc -z 127.0.0.1 "$PORT" 2>/dev/null; then
        listener_pids=$(listener_pids)
        owned=1
        if [ -z "$listener_pids" ]; then
            owned=0
        fi
        for listener_pid in $listener_pids; do
            if ! is_gearlynx_process "$listener_pid"; then
                owned=0
            fi
        done
        if [ "$owned" -eq 1 ]; then
            echo "Gearlynx headless ROM launch OK: debug monitor 127.0.0.1:$PORT is listening"
            echo "UNVERIFIED: this Gearlynx debug-monitor interface has no documented input/state protocol in this repository."
            echo "Run 'make smoke-host' for the deterministic Stage 1 NORMAL, movement, fire, and GAME OVER checks."
            exit 3
        fi
        echo "Gearlynx debug monitor port $PORT is not owned by this Gearlynx launch:" >&2
        lsof -nP -iTCP:"$PORT" -sTCP:LISTEN >&2 || true
        cat "$LOG" >&2
        exit 1
    fi
    attempt=$((attempt + 1))
    sleep 1
done

echo "Gearlynx did not open debug monitor port $PORT within 20 seconds:" >&2
cat "$LOG" >&2
exit 1
