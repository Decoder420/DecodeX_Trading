#!/usr/bin/env python3
"""CLI Runner for Stage 2 Historical Downloader.

Enforces:
1. Lock: Downloader and recorder never overlap.
2. Market Hours: Excludes today's active session if executed prior to 15:45 IST.
3. Cross-checks computed and saved to files.
4. Data quality reporting and secrets scanning.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("run_historical_downloader")

from data.historical_downloader import Stage2HistoricalDownloader


def main() -> None:
    parser = argparse.ArgumentParser(description="Stage 2 Historical Market Data Downloader & Cross-Check Engine.")
    parser.add_argument(
        "--symbols",
        nargs="+",
        default=["NIFTY", "BANKNIFTY", "SENSEX"],
        help="Symbols to download and cross-check (default: NIFTY BANKNIFTY SENSEX)",
    )
    parser.add_argument(
        "--start",
        type=str,
        default=None,
        help="Start date YYYY-MM-DD (defaults to 14 days ago)",
    )
    parser.add_argument(
        "--end",
        type=str,
        default=None,
        help="End date YYYY-MM-DD (defaults to today)",
    )
    parser.add_argument(
        "--force-refresh",
        action="store_true",
        help="Force re-check even if recorded in manifest.",
    )

    args = parser.parse_args()

    start_d = datetime.strptime(args.start, "%Y-%m-%d").date() if args.start else None
    end_d = datetime.strptime(args.end, "%Y-%m-%d").date() if args.end else None

    downloader = Stage2HistoricalDownloader()
    try:
        summary = downloader.run(
            symbols=args.symbols,
            start_date=start_d,
            end_date=end_d,
            force_refresh=args.force_refresh,
        )
        logger.info("==================================================")
        logger.info("STAGE 2 DOWNLOADER EXECUTION SUMMARY")
        logger.info("==================================================")
        for k, v in summary.items():
            logger.info("  %s: %s", k, v)
    except Exception as e:
        logger.critical("Stage 2 Downloader halted: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
