#!/usr/bin/env python3
"""Watchdog daemon for Live Market Recorder.

Monitors run_live_recorder.py during exchange trading hours (09:15 to 15:35 IST).
If the recorder process crashes, is killed, or stops unexpectedly, restarts it within 15 seconds.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
import pytz

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [RecorderWatchdog]: %(message)s"
)
logger = logging.getLogger("RecorderWatchdog")

from config.loader import config_manager

PID_FILE = ROOT_DIR / "data" / "recorder.pid"
PYTHON_BIN = sys.executable
RECORDER_SCRIPT = ROOT_DIR / "scripts" / "run_live_recorder.py"
LOG_FILE = ROOT_DIR / "logs" / "recorder_daemon.log"


def is_recorder_running() -> bool:
    if not PID_FILE.exists():
        return False
    try:
        pid_str = PID_FILE.read_text().strip()
        if not pid_str or not pid_str.isdigit():
            return False
        pid = int(pid_str)
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def is_active_market_window() -> bool:
    tz = pytz.timezone("Asia/Kolkata")
    now = datetime.now(tz)
    if not config_manager.is_trading_day(now.date()):
        return False
    start = now.replace(hour=9, minute=14, second=0, microsecond=0)
    end = now.replace(hour=15, minute=35, second=0, microsecond=0)
    return start <= now <= end


def run_watchdog():
    logger.info("Live Recorder Watchdog starting...")
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

    while True:
        try:
            in_window = is_active_market_window()
            running = is_recorder_running()

            if in_window and not running:
                logger.warning("ALERT: Recorder is NOT running during active market session! Restarting in 15 seconds...")
                time.sleep(15.0)

                # Double-check before spawning
                if not is_recorder_running():
                    logger.info("Spawning Live Market Recorder via caffeinate...")
                    cmd = [
                        "caffeinate", "-dimsu",
                        PYTHON_BIN, "-u", str(RECORDER_SCRIPT)
                    ]
                    with open(LOG_FILE, "a") as log_f:
                        proc = subprocess.Popen(
                            cmd,
                            stdout=log_f,
                            stderr=subprocess.STDOUT,
                            cwd=str(ROOT_DIR),
                        )
                    logger.info("Spawned recorder process (caffeinate PID %s).", proc.pid)

            time.sleep(10.0)
        except KeyboardInterrupt:
            logger.info("Watchdog terminated by user.")
            break
        except Exception as e:
            logger.error("Error in watchdog loop: %s", e)
            time.sleep(15.0)


if __name__ == "__main__":
    run_watchdog()
