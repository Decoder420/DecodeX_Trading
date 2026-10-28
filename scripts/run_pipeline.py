"""CLI entry point to fetch data, clean it, build features, and print the data quality report."""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.loader import ConfigManager
from data.provider_factory import DataOrchestrator
from features.pipeline import FeaturePipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("run_pipeline")


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch market data, clean, generate features, and report quality.")
    parser.add_argument(
        "--symbols",
        nargs="+",
        default=["NIFTY", "BANKNIFTY", "SENSEX", "INDIAVIX"],
        help="Instrument symbols to process (default: NIFTY BANKNIFTY SENSEX INDIAVIX)",
    )
    parser.add_argument(
        "--timeframe",
        type=str,
        default=None,
        help="Timeframe ('1d' or '15m'). Defaults to config active_timeframe.",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=None,
        help="Number of historical days to fetch (e.g. 365, 730).",
    )
    parser.add_argument(
        "--start",
        type=str,
        default="2010-01-01",
        help="Start date YYYY-MM-DD (default: 2010-01-01 for maximum daily history).",
    )
    parser.add_argument(
        "--end",
        type=str,
        default=None,
        help="End date YYYY-MM-DD (defaults to current date).",
    )
    parser.add_argument(
        "--provider",
        type=str,
        default=None,
        help="Override data provider ('yfinance', 'angelone', 'upstox').",
    )
    parser.add_argument(
        "--force-refresh",
        action="store_true",
        help="Force full re-fetch rather than incremental update.",
    )
    parser.add_argument(
        "--report-warmup",
        action="store_true",
        default=True,
        help="Print NaN warm-up length table for every engineered feature.",
    )

    args = parser.parse_args()

    cfg = ConfigManager()
    if args.provider:
        cfg.config.setdefault("data", {}).setdefault("provider", {})["primary"] = args.provider

    timeframe = args.timeframe or cfg.get("data.active_timeframe", "1d")

    end_dt = datetime.strptime(args.end, "%Y-%m-%d") if args.end else datetime.now()
    if args.days:
        start_dt = end_dt - timedelta(days=args.days)
    else:
        start_dt = datetime.strptime(args.start, "%Y-%m-%d")

    logger.info("==================================================")
    logger.info("Starting Quantitative Research Pipeline (Part 1)")
    logger.info("Timeframe: %s | Start: %s | End: %s", timeframe, start_dt.strftime("%Y-%m-%d"), end_dt.strftime("%Y-%m-%d"))
    logger.info("==================================================")

    orchestrator = DataOrchestrator(cfg)
    pipeline = FeaturePipeline(cfg)

    # 1. Fetch India VIX first for feature alignment
    logger.info("Fetching India VIX data...")
    vix_df = orchestrator.fetch_vix(start=start_dt, end=end_dt)
    if not vix_df.empty:
        logger.info("Retrieved %d VIX records from %s to %s.", len(vix_df), vix_df["timestamp"].min().date(), vix_df["timestamp"].max().date())
    else:
        logger.warning("No VIX data retrieved; VIX percentile features will be NaN.")

    warmup_df = None

    # 2. Process each instrument
    for sym in args.symbols:
        logger.info("--------------------------------------------------")
        logger.info("Processing instrument: %s [%s]", sym, timeframe)
        try:
            # Handle India VIX as a standalone evaluated instrument
            if sym.upper() in ["INDIAVIX", "VIX", "INDIA VIX"]:
                target_sym = "INDIA VIX"
            else:
                target_sym = sym

            df_cleaned, reporter = orchestrator.fetch_and_store(
                symbol=target_sym,
                timeframe=timeframe,
                start=start_dt,
                end=end_dt,
                force_refresh=args.force_refresh,
            )

            if df_cleaned.empty:
                logger.error("No data available for %s", sym)
                continue

            # Compute features for benchmark indices (VIX itself is a volatility feature)
            if sym.upper() not in ["INDIAVIX", "VIX", "INDIA VIX"]:
                logger.info("Building feature pipeline for %s...", sym)
                df_features = pipeline.compute_all_features(
                    df=df_cleaned,
                    instrument=sym,
                    vix_df=vix_df,
                    include_garch=True,
                    include_regime=True,
                    include_mean_reversion=True,
                )

                logger.info(
                    "Successfully generated %d features across %d rows for %s.",
                    len(df_features.columns),
                    len(df_features),
                    sym,
                )

                if warmup_df is None and args.report_warmup:
                    warmup_df = FeaturePipeline.get_feature_warmup_report(df_features)

                # Sample display of key feature columns
                feature_cols_to_show = [
                    c
                    for c in [
                        "timestamp",
                        "close",
                        "ema_21",
                        "rsi_14",
                        "atr_14",
                        "gap_pct",
                        "is_expiry_day",
                        "days_to_expiry",
                        "regime_label",
                    ]
                    if c in df_features.columns
                ]
                print(f"\n--- Recent Feature Snapshot for {sym} ---")
                print(df_features[feature_cols_to_show].tail(5).to_string(index=False))

        except Exception as e:
            logger.exception("Failed processing %s: %s", sym, e)

    # 3. Print Consolidated Data Quality Report & Gap Audit
    print("\n")
    orchestrator.reporter.print_summary()

    # 4. Print Feature Warmup Report
    if warmup_df is not None:
        print("\n### Feature NaN Warm-Up Length Report\n")
        print("| Feature Name | Leading NaNs (Warm-Up Bars) | Total NaNs | NaN % | Warm-Up Status |")
        print("| :--- | :---: | :---: | :---: | :--- |")
        for _, w in warmup_df.iterrows():
            print(f"| `{w['feature']}` | {w['leading_nans']} | {w['total_nans']} | {w['pct_nans']}% | `{w['status']}` |")

        active_features = warmup_df[~warmup_df["feature"].isin(["vwap", "price_vs_vwap_pct"])]
        max_warmup = int(active_features["leading_nans"].max()) if not active_features.empty else 0
        print(f"\n> **Warm-Up Usability Threshold**: The maximum feature warm-up requirement is **{max_warmup} bars** "
              f"(governed by 252-bar rolling GARCH/HMM windows). "
              f"The first {max_warmup} rows of the dataset are initialization bars and should be pruned before model training in Part 2. "
              f"(Note: VWAP is intentionally NaN for spot index series as they contain no traded volume).\n")

    logger.info("Pipeline run complete.")


if __name__ == "__main__":
    main()
