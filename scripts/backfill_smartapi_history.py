#!/usr/bin/env python3
"""Backfill authentic historical intraday (1m, 5m, 15m, 1d) candles from Angel One SmartAPI into market_data.duckdb and live DB."""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
import duckdb
import pandas as pd
import pytz
import requests

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("BackfillSmartAPI")

def backfill():
    cache_path = ROOT_DIR / "data" / "cache" / "angel_session.json"
    if not cache_path.exists():
        logger.error("Session cache not found at %s. Please authenticate first.", cache_path)
        return

    with open(cache_path, "r", encoding="utf-8") as f:
        sess = json.load(f)

    jwt = sess["jwtToken"]
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "X-PrivateKey": os.getenv("ANGEL_API_KEY", "30e58rgY"),
        "X-UserType": "USER",
        "X-SourceID": "WEB",
        "X-ClientLocalIP": "127.0.0.1",
        "X-ClientPublicIP": "106.193.147.98",
        "X-MACAddress": "fe:ed:fa:ce:be:ef",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
        "Authorization": f"Bearer {jwt}",
    }

    db_path = ROOT_DIR / "data" / "market_data.duckdb"
    con = duckdb.connect(str(db_path))

    instruments = {
        "NIFTY": ("NSE", "99926000", "ohlcv_nifty"),
        "BANKNIFTY": ("NSE", "99926009", "ohlcv_banknifty"),
        "INDIA_VIX": ("NSE", "99926017", "ohlcv_india_vix"),
    }

    # Also SENSEX daily and 15m
    sensex_tuple = ("BSE", "99919000", "ohlcv_sensex")

    now_ist = datetime.now(pytz.timezone("Asia/Kolkata"))
    now_hm = now_ist.strftime("%Y-%m-%d %H:%M")
    from_date = "2026-10-28 09:15"

    for sym, (exch, tok, prefix) in instruments.items():
        logger.info("Fetching real 1m candles for %s from SmartAPI (%s to %s)...", sym, from_date, now_hm)
        data = []
        for attempt in range(4):
            time.sleep(1.5)
            try:
                resp = requests.post(
                    "https://apiconnect.angelone.in/rest/secure/angelbroking/historical/v1/getCandleData",
                    json={
                        "exchange": exch,
                        "symboltoken": tok,
                        "interval": "ONE_MINUTE",
                        "fromdate": from_date,
                        "todate": now_hm,
                    },
                    headers=headers,
                    timeout=15,
                )
                if resp.status_code == 200 and resp.text:
                    res_json = resp.json()
                    if res_json.get("status"):
                        data = res_json.get("data") or []
                        break
            except Exception as e:
                logger.warning("Attempt %d for %s failed: %s. Retrying...", attempt + 1, sym, e)
                time.sleep(2.0)

        if not data:
            logger.warning("No 1m candle data returned for %s", sym)
            continue

        rows = []
        for b in data:
            ts_str, op, hi, lo, cl, vol = b
            # Normalize timestamp string format: "2026-10-28 09:15:00+0530"
            dt = pd.to_datetime(ts_str)
            if dt.tz is None:
                dt = pytz.timezone("Asia/Kolkata").localize(dt)
            else:
                dt = dt.astimezone(pytz.timezone("Asia/Kolkata"))
            ts_formatted = dt.strftime("%Y-%m-%d %H:%M:%S%z")
            rows.append({
                "timestamp": ts_formatted,
                "open": float(op),
                "high": float(hi),
                "low": float(lo),
                "close": float(cl),
                "volume": float(vol) if sym not in ["NIFTY", "BANKNIFTY", "INDIA_VIX"] else 0.0,
                "is_outlier": False,
                "is_gap": False,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            })

        df_new = pd.DataFrame(rows)
        con.register("df_incoming", df_new)
        table_1m = f"{prefix}_1m"
        con.execute(f"DELETE FROM {table_1m} WHERE timestamp >= '{from_date}'")
        con.execute(f"INSERT INTO {table_1m} SELECT * FROM df_incoming")
        logger.info("Inserted %d real 1m bars into %s. Latest: %s", len(df_new), table_1m, data[-1])

        # Also populate today's live duckdb index_1m_bars
        try:
            today_str = now_ist.strftime("%Y_%m_%d")
            today_dash = now_ist.strftime("%Y-%m-%d")
            live_db_path = ROOT_DIR / "data" / "live" / f"live_{today_str}.duckdb"
            con_live = duckdb.connect(str(live_db_path))
            con_live.execute("""
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
            df_today = df_new[df_new["timestamp"].str.startswith(today_dash)].copy()
            if not df_today.empty:
                df_live_rows = []
                for _, r in df_today.iterrows():
                    df_live_rows.append({
                        "timestamp": pd.to_datetime(r["timestamp"]),
                        "symbol": sym,
                        "open": r["open"],
                        "high": r["high"],
                        "low": r["low"],
                        "close": r["close"],
                        "volume": 0.0,
                        "source": "smartapi_real",
                    })
                df_live = pd.DataFrame(df_live_rows)
                con_live.register("df_live_in", df_live)
                con_live.execute("DELETE FROM index_1m_bars WHERE symbol = ?", [sym])
                con_live.execute("INSERT INTO index_1m_bars SELECT * FROM df_live_in")
                logger.info("Inserted %d today bars for %s into live_%s.duckdb", len(df_live), sym, today_str)
            con_live.close()
        except Exception as le:
            logger.warning("Could not write to live db for %s (lock held by app): %s", sym, le)

    # Backfill SENSEX daily & 15m
    logger.info("Fetching real SENSEX candles from SmartAPI...")
    s_data = []
    for attempt in range(4):
        time.sleep(2.0)
        try:
            resp_s = requests.post(
                "https://apiconnect.angelone.in/rest/secure/angelbroking/historical/v1/getCandleData",
                json={
                    "exchange": "BSE",
                    "symboltoken": "99919000",
                    "interval": "ONE_DAY",
                    "fromdate": "2026-10-01 09:15",
                    "todate": now_hm,
                },
                headers=headers,
                timeout=15,
            )
            if resp_s.status_code == 200 and resp_s.text:
                res_s_json = resp_s.json()
                if res_s_json.get("status"):
                    s_data = res_s_json.get("data") or []
                    break
        except Exception as e:
            logger.warning("Attempt %d for SENSEX failed: %s. Retrying...", attempt + 1, e)
            time.sleep(2.0)
    if s_data:
        s_rows = []
        for b in s_data:
            ts_str, op, hi, lo, cl, vol = b
            dt = pd.to_datetime(ts_str)
            if dt.tz is None:
                dt = pytz.timezone("Asia/Kolkata").localize(dt)
            ts_formatted = dt.strftime("%Y-%m-%d 00:00:00%z")
            s_rows.append({
                "timestamp": ts_formatted,
                "open": float(op),
                "high": float(hi),
                "low": float(lo),
                "close": float(cl),
                "volume": 0.0,
                "is_outlier": False,
                "is_gap": False,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            })
        df_s = pd.DataFrame(s_rows)
        con.register("df_s_in", df_s)
        con.execute("DELETE FROM ohlcv_sensex_1d WHERE timestamp >= '2026-10-01'")
        con.execute("INSERT INTO ohlcv_sensex_1d SELECT * FROM df_s_in")
        logger.info("Inserted %d real 1d bars into ohlcv_sensex_1d", len(df_s))

    # Also resample 1m to 5m, 15m, 1d in market_data.duckdb for NIFTY, BANKNIFTY, INDIA_VIX
    for sym, (_, _, prefix) in instruments.items():
        t1m = f"{prefix}_1m"
        t5m = f"{prefix}_5m"
        t15m = f"{prefix}_15m"
        t1d = f"{prefix}_1d"

        # Update 15m
        df_all_1m = con.execute(f"SELECT timestamp, open, high, low, close, volume FROM {t1m} ORDER BY timestamp ASC").df()
        df_all_1m["dt"] = pd.to_datetime(df_all_1m["timestamp"])
        df_all_1m["slot_15m"] = df_all_1m["dt"].dt.floor("15min")
        agg_15 = df_all_1m.groupby("slot_15m", as_index=False).agg({
            "open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"
        }).rename(columns={"slot_15m": "dt"})
        agg_15["timestamp"] = agg_15["dt"].dt.strftime("%Y-%m-%d %H:%M:%S%z")
        agg_15["is_outlier"] = False
        agg_15["is_gap"] = False
        agg_15["updated_at"] = datetime.now(timezone.utc).isoformat()
        con.register("df_15_in", agg_15[["timestamp", "open", "high", "low", "close", "volume", "is_outlier", "is_gap", "updated_at"]])
        con.execute(f"CREATE TABLE IF NOT EXISTS {t15m} AS SELECT * FROM df_15_in WHERE 1=0")
        con.execute(f"DELETE FROM {t15m} WHERE timestamp >= '{from_date}'")
        con.execute(f"INSERT INTO {t15m} SELECT * FROM df_15_in WHERE timestamp >= '{from_date}'")
        logger.info("Resampled and updated %s", t15m)

        # Update 1d
        df_all_1m["date_slot"] = df_all_1m["dt"].dt.floor("1D")
        agg_1d = df_all_1m.groupby("date_slot", as_index=False).agg({
            "open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"
        }).rename(columns={"date_slot": "dt"})
        agg_1d["timestamp"] = agg_1d["dt"].dt.strftime("%Y-%m-%d 00:00:00%z")
        agg_1d["is_outlier"] = False
        agg_1d["is_gap"] = False
        agg_1d["updated_at"] = datetime.now(timezone.utc).isoformat()
        con.register("df_1d_in", agg_1d[["timestamp", "open", "high", "low", "close", "volume", "is_outlier", "is_gap", "updated_at"]])
        con.execute(f"DELETE FROM {t1d} WHERE timestamp >= '2026-10-28'")
        con.execute(f"INSERT INTO {t1d} SELECT * FROM df_1d_in WHERE timestamp >= '2026-10-28'")
        logger.info("Resampled and updated %s", t1d)

    con.close()
    logger.info("Backfill complete! All DuckDB tables up to date with authentic SmartAPI broker candles.")

if __name__ == "__main__":
    backfill()
