#!/usr/bin/env bash
# recorder_daemon.sh - Production Daemon Wrapper for Live Market Recorder
# Manages recorder lifecycle, macOS sleep prevention via caffeinate, and status telemetry.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
PID_FILE="$PROJECT_ROOT/data/recorder.pid"
LOG_FILE="$PROJECT_ROOT/logs/recorder_daemon.log"
PYTHON_BIN="$PROJECT_ROOT/.venv/bin/python"

if [ ! -f "$PYTHON_BIN" ]; then
    PYTHON_BIN="python3"
fi

check_sleep_and_power() {
    echo "=== Power & Sleep Configuration Check ==="
    if command -v pmset >/dev/null 2>&1; then
        local batt_status
        batt_status=$(pmset -g batt 2>/dev/null || true)
        if echo "$batt_status" | grep -qi "Battery Power"; then
            echo "⚠️  [WARNING] Mac is currently running on BATTERY power!"
            echo "    Connect to AC power immediately to prevent OS throttling and sleep."
        else
            echo "✓  Power source: AC Power connected."
        fi

        local sleep_val
        sleep_val=$(pmset -g custom 2>/dev/null | grep -E "^[[:space:]]*sleep" | awk '{print $2}' | head -n 1 || true)
        if [ -n "$sleep_val" ] && [ "$sleep_val" -eq "$sleep_val" ] 2>/dev/null && [ "$sleep_val" -gt 0 ]; then
            echo "ℹ️  System sleep is set to $sleep_val minutes. Caffeinate (-dimsu) will actively override this assertion."
        fi
    else
        echo "ℹ️  pmset not available on this platform."
    fi
}

start_recorder() {
    if [ -f "$PID_FILE" ]; then
        local old_pid
        old_pid=$(cat "$PID_FILE")
        if kill -0 "$old_pid" 2>/dev/null; then
            echo "Recorder is ALREADY RUNNING with PID $old_pid."
            exit 0
        else
            echo "Stale PID file found. Removing..."
            rm -f "$PID_FILE"
        fi
    fi

    check_sleep_and_power

    echo "Starting Live Market Recorder under caffeinate (-dimsu)..."
    cd "$PROJECT_ROOT"

    # Launch with caffeinate to prevent display, system, idle, and disk sleep
    caffeinate -dimsu "$PYTHON_BIN" -u "$PROJECT_ROOT/scripts/run_live_recorder.py" >> "$LOG_FILE" 2>&1 &
    local new_pid=$!

    echo "$new_pid" > "$PID_FILE"
    sleep 2

    if kill -0 "$new_pid" 2>/dev/null; then
        echo "✓ Recorder started successfully with PID: $new_pid"
        echo "✓ Output log: $LOG_FILE"
    else
        echo "❌ Failed to start recorder. Check log for details: $LOG_FILE"
        rm -f "$PID_FILE"
        exit 1
    fi
}

stop_recorder() {
    if [ ! -f "$PID_FILE" ]; then
        echo "Recorder PID file not found. Process may not be running."
        local orphaned_pids
        orphaned_pids=$(pgrep -f "run_live_recorder.py" || true)
        if [ -n "$orphaned_pids" ]; then
            echo "Found orphaned recorder process(es): $orphaned_pids. Stopping..."
            # shellcheck disable=SC2086
            kill -TERM $orphaned_pids 2>/dev/null || true
            sleep 3
            # shellcheck disable=SC2086
            kill -9 $orphaned_pids 2>/dev/null || true
            echo "✓ Orphaned processes terminated."
        fi
        exit 0
    fi

    local target_pid
    target_pid=$(cat "$PID_FILE")

    if kill -0 "$target_pid" 2>/dev/null; then
        echo "Stopping Live Recorder (PID $target_pid)..."
        kill -TERM "$target_pid" 2>/dev/null || true

        # Wait up to 10 seconds for graceful shutdown and Parquet consolidation
        for i in {1..10}; do
            if ! kill -0 "$target_pid" 2>/dev/null; then
                echo "✓ Recorder stopped gracefully."
                rm -f "$PID_FILE"
                exit 0
            fi
            sleep 1
        done

        echo "Recorder did not exit gracefully within 10s. Forcing SIGKILL..."
        kill -9 "$target_pid" 2>/dev/null || true
        rm -f "$PID_FILE"
        echo "✓ Recorder killed."
    else
        echo "Process $target_pid was not running. Cleaning PID file..."
        rm -f "$PID_FILE"
    fi
}

status_recorder() {
    echo "=== Live Market Recorder Status ==="
    local is_running=false
    local running_pid=""

    if [ -f "$PID_FILE" ]; then
        local pid
        pid=$(cat "$PID_FILE")
        if kill -0 "$pid" 2>/dev/null; then
            is_running=true
            running_pid="$pid"
        fi
    fi

    if [ "$is_running" = true ]; then
        echo "Status: RUNNING (PID $running_pid)"
        # Query latest health telemetry from DuckDB
        "$PYTHON_BIN" - << 'EOF'
import os
import duckdb
from datetime import datetime

today = datetime.now().strftime("%Y_%m_%d")
db_path = os.path.join("data", "live", f"live_{today}.duckdb")

if os.path.exists(db_path):
    con = None
    import time
    for _ in range(10):
        try:
            con = duckdb.connect(db_path, read_only=True)
            break
        except Exception:
            time.sleep(0.2)
    if con is not None:
        try:
            # Check health
            health = con.execute("SELECT * FROM recorder_health ORDER BY timestamp DESC LIMIT 1").fetchdf()
            if not health.empty:
                row = health.iloc[0]
                print(f"Health Timestamp: {row['timestamp']}")
                print(f"Uptime:           {row['uptime_seconds']}s")
                print(f"Ticks Received:   {row['ticks_received']}")
                print(f"Tick Rate:        {row['tick_rate_per_sec']} ticks/sec")
                print(f"Active Source:    {row['active_source']}")
                print(f"Memory RSS:       {row['memory_mb']} MB")
                print(f"Disconnects:      {row['disconnect_count']}")
                print(f"Last Tick Age:    {row['last_tick_age_seconds']}s")

            # Counts
            ticks_cnt = con.execute("SELECT count(*) FROM live_ticks").fetchone()[0]
            depth_cnt = con.execute("SELECT count(*) FROM live_depth").fetchone()[0]
            fut_cnt = con.execute("SELECT count(*) FROM futures_bars").fetchone()[0]
            opt_cnt = con.execute("SELECT count(*) FROM options_snapshots").fetchone()[0]
            metrics_cnt = con.execute("SELECT count(*) FROM live_derived_metrics").fetchone()[0]
            size_bytes = os.path.getsize(db_path)
            print(f"DB File Size:     {size_bytes / 1024:.1f} KB ({size_bytes / (1024*1024):.2f} MB)")
            print(f"Stored Ticks:     {ticks_cnt}")
            print(f"Depth Quotes:     {depth_cnt}")
            print(f"Futures Bars:     {fut_cnt}")
            print(f"Option Snapshots: {opt_cnt}")
            print(f"Derived Metrics:  {metrics_cnt}")
            con.close()
        except Exception as e:
            print(f"Error querying live database: {e}")
    else:
        print("Database locked by recorder. Telemetry updating...")
else:
    print(f"Live database for today ({db_path}) not yet found.")
EOF
    else
        echo "Status: STOPPED (Not running)"
    fi
}

case "${1:-}" in
    start)
        start_recorder
        ;;
    stop)
        stop_recorder
        ;;
    status)
        status_recorder
        ;;
    restart)
        stop_recorder
        sleep 2
        start_recorder
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status}"
        exit 1
        ;;
esac
