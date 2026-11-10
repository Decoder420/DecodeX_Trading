#!/usr/bin/env python3
"""Live Market Recorder Runner.

Executes LiveRecorderEngine until 15:35 IST or SIGINT/SIGTERM.
Prevents computer sleep via caffeinate (when invoked via recorder_daemon.sh).
Enforces kernel-level single-instance file lock (fcntl.flock).
A foreground test run or duplicate invocation must NEVER replace, stop, or conflict with the active daemon.
"""

from __future__ import annotations

import fcntl
import os
import signal
import sys
import time
from datetime import datetime
from pathlib import Path
import pytz
from dotenv import load_dotenv

# Ensure repo root is on sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

load_dotenv(os.path.join(BASE_DIR, ".env"))

import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("recorder_runner")

from recorder.engine import LiveRecorderEngine
from recorder.storage import LiveStorageManager

PID_FILE = Path(BASE_DIR) / "data" / "recorder.pid"


def acquire_single_instance_lock():
    """Acquire exclusive kernel file lock on recorder.pid.
    
    If another process holds the lock, exits cleanly immediately without interrupting the daemon.
    """
    PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    # Open file with 'a+' so it exists
    fd = open(PID_FILE, "a+")
    try:
        fcntl.flock(fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except (BlockingIOError, OSError):
        fd.seek(0)
        holder_pid = fd.read().strip()
        logger.warning(
            "SINGLE-INSTANCE LOCK ENGAGED: Live Market Recorder daemon is already active (PID %s). "
            "A foreground test run or duplicate process must NEVER replace or terminate the running daemon. Exiting cleanly.",
            holder_pid or "unknown",
        )
        fd.close()
        sys.exit(0)

    # Successfully acquired lock: write current PID
    fd.seek(0)
    fd.truncate()
    fd.write(f"{os.getpid()}\n")
    fd.flush()
    logger.info("Acquired single-instance recorder lock (PID %s).", os.getpid())
    return fd


def release_single_instance_lock(fd):
    """Release kernel file lock and clean up pidfile."""
    try:
        fcntl.flock(fd.fileno(), fcntl.LOCK_UN)
        fd.close()
    except Exception as e:
        logger.debug("Error unlocking pidfile: %s", e)

    try:
        if PID_FILE.exists():
            PID_FILE.unlink(missing_ok=True)
    except Exception as e:
        logger.debug("Error removing pidfile: %s", e)
    logger.info("Released single-instance recorder lock.")


def main() -> None:
    # 1. Enforce single-instance lock
    lock_fd = acquire_single_instance_lock()

    logger.info("Initializing LiveRecorderEngine...")
    storage = LiveStorageManager(base_dir=os.path.join(BASE_DIR, "data", "live"))
    engine = LiveRecorderEngine(storage_mgr=storage)

    tz = pytz.timezone("Asia/Kolkata")
    now_ist = datetime.now(tz)
    target = now_ist.replace(hour=15, minute=35, second=0, microsecond=0)

    if now_ist >= target and "--force" not in sys.argv:
        logger.info(
            "Current IST time (%s) is already at or past scheduled stop threshold (15:35 IST). Exiting.",
            now_ist.strftime("%H:%M:%S"),
        )
        release_single_instance_lock(lock_fd)
        sys.exit(0)

    seconds_remaining = max(10, int((target - now_ist).total_seconds())) if "--duration" not in sys.argv else int(sys.argv[sys.argv.index("--duration") + 1])
    logger.info(
        "Recorder starting. Active duration: %d seconds.",
        seconds_remaining,
    )

    def handle_signal(sig, frame):
        logger.info("Received termination signal (%s). Initiating graceful shutdown...", sig)
        engine.stop()

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    try:
        summary = engine.run(duration_seconds=seconds_remaining)
        logger.info("Recorder session summary: %s", summary)
    except Exception as e:
        logger.critical("Error during LiveRecorderEngine run: %s", e, exc_info=True)
    finally:
        logger.info("Consolidating session data to Parquet...")
        try:
            today_str = datetime.now(tz).strftime("%Y%m%d")
            storage.consolidate_day_to_parquet(today_str)
            logger.info("Consolidation to Parquet complete.")
        except Exception as e:
            logger.error("Error during Parquet consolidation: %s", e)

        release_single_instance_lock(lock_fd)
        logger.info("Live Market Recorder finished cleanly.")


if __name__ == "__main__":
    main()
