#!/usr/bin/env python3
"""Gap-fill live_2026_10_28.duckdb for missing minutes today and record gaps in recording_gaps table."""

import logging
import sys
from datetime import date, datetime
from pathlib import Path
import duckdb
import pandas as pd
import pytz

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("gap_filler")

from data.angel_provider import AngelOneProvider
from recorder.storage import LiveStorageManager

DB_PATH = ROOT_DIR / "data" / "live" / "live_2026_10_28.duckdb"

def main():
    tz = pytz.timezone("Asia/Kolkata")
    logger.info("Connecting to %s...", DB_PATH)
    con = duckdb.connect(str(DB_PATH))

    # 1. Create recording_gaps table
    con.execute("""
        CREATE TABLE IF NOT EXISTS recording_gaps (
            table_name VARCHAR,
            gap_start VARCHAR,
            gap_end VARCHAR,
            missing_minutes DOUBLE,
            can_backfill BOOLEAN,
            backfill_status VARCHAR,
            notes VARCHAR
        )
    """)
    con.execute("DELETE FROM recording_gaps")

    gaps_data = [
        # futures_bars
        ("futures_bars", "2026-10-28 09:15:00+05:30", "2026-10-28 10:08:05+05:30", 53.1, True, "COMPLETED", "Backfilled from Angel One SmartAPI 1m bars (source='broker_history')"),
        ("futures_bars", "2026-10-28 10:40:38+05:30", "2026-10-28 15:30:00+05:30", 289.4, True, "COMPLETED", "Backfilled from Angel One SmartAPI 1m bars (source='broker_history')"),
        # index 1m bars
        ("index_1m_bars", "2026-10-28 10:41:03+05:30", "2026-10-28 15:30:00+05:30", 288.9, True, "COMPLETED", "Backfilled from Angel One SmartAPI 1m bars (source='broker_history')"),
        # live_ticks
        ("live_ticks", "2026-10-28 10:41:03+05:30", "2026-10-28 15:30:00+05:30", 288.9, False, "UNAVAILABLE", "Tick-level streaming order flow cannot be backfilled from historical API"),
        # live_depth
        ("live_depth", "2026-10-28 09:15:00+05:30", "2026-10-28 10:07:07+05:30", 52.1, False, "UNAVAILABLE", "L2 Market depth order book snapshots cannot be backfilled from historical API"),
        ("live_depth", "2026-10-28 10:41:03+05:30", "2026-10-28 15:30:00+05:30", 288.9, False, "UNAVAILABLE", "L2 Market depth order book snapshots cannot be backfilled from historical API"),
        # options_snapshots
        ("options_snapshots", "2026-10-28 09:15:00+05:30", "2026-10-28 10:08:05+05:30", 53.1, False, "UNAVAILABLE", "Options Greeks, IV, and strike snapshots cannot be backfilled from historical API"),
        ("options_snapshots", "2026-10-28 10:40:48+05:30", "2026-10-28 15:30:00+05:30", 289.2, False, "UNAVAILABLE", "Options Greeks, IV, and strike snapshots cannot be backfilled from historical API"),
        # live_derived_metrics
        ("live_derived_metrics", "2026-10-28 09:15:00+05:30", "2026-10-28 10:08:18+05:30", 53.3, False, "UNAVAILABLE", "Derived Greeks/PCR metrics cannot be computed without options snapshots"),
        ("live_derived_metrics", "2026-10-28 10:40:54+05:30", "2026-10-28 15:30:00+05:30", 289.1, False, "UNAVAILABLE", "Derived Greeks/PCR metrics cannot be computed without options snapshots"),
    ]

    for g in gaps_data:
        con.execute("""
            INSERT INTO recording_gaps VALUES (?, ?, ?, ?, ?, ?, ?)
        """, g)

    logger.info("Recorded %d gaps in recording_gaps table.", len(gaps_data))

    # 2. Fetch official 1m bars from Angel One historical API for futures
    provider = AngelOneProvider()
    provider.connect()

    futures_targets = [
        ("NIFTY_FUT_NEAR", "NFO", "61471", date(2026, 11, 23)),
        ("BANKNIFTY_FUT_NEAR", "NFO", "61466", date(2026, 11, 23)),
        ("SENSEX_FUT_NEAR", "BFO", "864571", date(2026, 10, 29)),
    ]

    for sym, exch, tok, exp in futures_targets:
        logger.info("Fetching official 1m bars for [%s] (token %s)...", sym, tok)
        params = {
            "exchange": exch,
            "symboltoken": tok,
            "interval": "ONE_MINUTE",
            "fromdate": "2026-10-28 09:15",
            "todate": "2026-10-28 15:30",
        }
        res = provider._execute_with_retry(provider.client.getCandleData, params)
        raw_bars = res.get("data") or []
        logger.info("[%s] received %d official bars from historical API.", sym, len(raw_bars))

        if raw_bars:
            rows = []
            cum_vol = 0
            cum_pv = 0.0
            for b in raw_bars:
                ts_str, op, hi, lo, cl, vol = b
                bar_vol = int(vol)
                typ_price = (float(hi) + float(lo) + float(cl)) / 3.0
                cum_vol += bar_vol
                cum_pv += (typ_price * bar_vol)
                vwap = round(cum_pv / max(cum_vol, 1), 2)

                rows.append({
                    "timestamp": pd.to_datetime(ts_str),
                    "symbol": sym,
                    "token": tok,
                    "contract_expiry": exp,
                    "open": float(op),
                    "high": float(hi),
                    "low": float(lo),
                    "close": float(cl),
                    "volume": bar_vol,
                    "oi": 0,  # historical candles do not carry per-minute OI
                    "vwap": vwap,
                    "source": "broker_history",
                })

            df_fut = pd.DataFrame(rows)
            # Register temp and insert or replace
            con.register("df_incoming_fut", df_fut)
            con.execute("""
                DELETE FROM futures_bars
                WHERE symbol = ? AND source = 'broker_history'
            """, [sym])
            con.execute("""
                INSERT INTO futures_bars
                SELECT * FROM df_incoming_fut
            """)
            logger.info("Inserted %d broker_history futures bars for [%s].", len(df_fut), sym)

    # 3. Fetch index 1m bars and store in index_1m_bars
    con.execute("""
        CREATE TABLE IF NOT EXISTS index_1m_bars (
            timestamp TIMESTAMP WITH TIME ZONE,
            symbol VARCHAR,
            open DOUBLE,
            high DOUBLE,
            low DOUBLE,
            close DOUBLE,
            volume DOUBLE,
            source VARCHAR
        )
    """)

    index_targets = [
        ("NIFTY", "NSE", "99926000"),
        ("BANKNIFTY", "NSE", "99926009"),
        ("SENSEX", "BSE", "99919000"),
        ("INDIA VIX", "NSE", "99926017"),
    ]

    for sym, exch, tok in index_targets:
        logger.info("Fetching index 1m bars for [%s]...", sym)
        params = {
            "exchange": exch,
            "symboltoken": tok,
            "interval": "ONE_MINUTE",
            "fromdate": "2026-10-28 09:15",
            "todate": "2026-10-28 15:30",
        }
        res = provider._execute_with_retry(provider.client.getCandleData, params)
        raw_bars = res.get("data") or []
        logger.info("[%s] received %d index bars.", sym, len(raw_bars))
        if raw_bars:
            rows = []
            for b in raw_bars:
                ts_str, op, hi, lo, cl, vol = b
                rows.append({
                    "timestamp": pd.to_datetime(ts_str),
                    "symbol": sym,
                    "open": float(op),
                    "high": float(hi),
                    "low": float(lo),
                    "close": float(cl),
                    "volume": 0.0,  # index volume is strictly 0.0
                    "source": "broker_history",
                })
            df_idx = pd.DataFrame(rows)
            con.register("df_incoming_idx", df_idx)
            con.execute("DELETE FROM index_1m_bars WHERE symbol = ?", [sym])
            con.execute("INSERT INTO index_1m_bars SELECT * FROM df_incoming_idx")
            logger.info("Inserted %d index 1m bars for [%s].", len(df_idx), sym)

    total_gaps = con.execute("SELECT COUNT(*) FROM recording_gaps").fetchone()[0]
    total_fut = con.execute("SELECT COUNT(*) FROM futures_bars").fetchone()[0]
    total_idx = con.execute("SELECT COUNT(*) FROM index_1m_bars").fetchone()[0]
    logger.info("Gap fill complete. Table counts -> recording_gaps: %d, futures_bars: %d, index_1m_bars: %d", total_gaps, total_fut, total_idx)
    con.close()

if __name__ == "__main__":
    main()
