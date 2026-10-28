#!/usr/bin/env python3
"""Live Market Recorder Runner.

Executes LiveRecorderEngine until 15:35 IST or SIGINT/SIGTERM.
Prevents computer sleep via caffeinate (when invoked via recorder_daemon.sh).
"""

from __future__ import annotations

import os
import signal
import sys
import time
from datetime import datetime
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



def main() -> None:
    logger.info("Initializing LiveRecorderEngine...")
    storage = LiveStorageManager(base_dir=os.path.join(BASE_DIR, "data", "live"))
    engine = LiveRecorderEngine(storage_mgr=storage)

    tz = pytz.timezone("Asia/Kolkata")
    now_ist = datetime.now(tz)
    target = now_ist.replace(hour=15, minute=35, second=0, microsecond=0)

    if now_ist >= target:
        logger.info(
            "Current IST time (%s) is already at or past scheduled stop threshold (15:35 IST). Exiting.",
            now_ist.strftime("%H:%M:%S"),
        )
        sys.exit(0)

    seconds_remaining = max(10, int((target - now_ist).total_seconds()))
    logger.info(
        "Recorder starting. Active duration: %d seconds until 15:35:00 IST.",
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

        logger.info("Live Market Recorder finished cleanly.")


if __name__ == "__main__":
    main()

