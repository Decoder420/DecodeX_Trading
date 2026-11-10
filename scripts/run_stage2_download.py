#!/usr/bin/env python3
"""Execute full Stage 2 historical download (2020 to 2026-10-28) for NIFTY, BANKNIFTY, SENSEX, and INDIA VIX."""

import logging
import sys
from datetime import date
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("run_stage2")

from data.historical_downloader import Stage2HistoricalDownloader

def main():
    downloader = Stage2HistoricalDownloader()
    symbols = ["NIFTY", "BANKNIFTY", "SENSEX", "INDIA VIX"]
    timeframes = ["1d", "15m", "5m", "1m"]
    
    logger.info("Starting Full Stage 2 Historical Download (2020 to today: 2026-10-28)...")
    res = downloader.download_all(
        symbols=symbols,
        timeframes=timeframes,
        start_year=2020,
        end_date=date(2026, 10, 28),
        force_refresh=False,
    )
    logger.info("Stage 2 Historical Ingestion & Audit Complete!")
    logger.info("Summary: %s", res)

if __name__ == "__main__":
    main()
