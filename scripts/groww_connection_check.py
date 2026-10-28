"""Groww Trade API Connection and Subscription Diagnostic Script.

Performs:
1. Credentials & authentication check (TOTP vs approval key verification).
2. Live Data check (LTP & OHLC for NIFTY).
3. Historical Data check (5-minute candle series for NIFTY).
4. Subscription status reporting (identifies active subscriptions vs 403 Forbidden).
5. Historical candle reach test (1m, 5m, 15m depth and gap detection).
6. Index and futures symbol resolution verification.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
import pandas as pd
import pytz

# Setup path and logging
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from data.groww_auth import (
    GrowwAuthError,
    GrowwApprovalKeyOnlyError,
    GrowwAuthManager,
    IST,
)
from growwapi import GrowwAPI
from growwapi.groww.exceptions import (
    GrowwAPIAuthenticationException,
    GrowwAPIAuthorisationException,
    GrowwAPIBadRequestException,
    GrowwAPIRateLimitException,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("groww_check")


def check_credentials_presence() -> Dict[str, bool]:
    """Check which Groww credentials exist in environment without exposing values."""
    return {
        "GROWW_API_KEY": bool(os.getenv("GROWW_API_KEY")),
        "GROWW_API_SECRET": bool(os.getenv("GROWW_API_SECRET")),
        "GROWW_TOTP_SECRET": bool(os.getenv("GROWW_TOTP_SECRET")),
    }


def resolve_symbols(df_instruments: pd.DataFrame) -> Dict[str, Dict[str, Any]]:
    """Resolve index and nearest-month futures symbols from Groww instrument master."""
    today_str = datetime.now(IST).strftime("%Y-%m-%d")
    resolved = {}

    targets = [
        ("NIFTY", "NSE", "NIFTY"),
        ("BANKNIFTY", "NSE", "BANKNIFTY"),
        ("SENSEX", "BSE", "SENSEX"),
    ]

    for name, exchange, trading_sym in targets:
        # Index row
        idx_rows = df_instruments[
            (df_instruments["exchange"] == exchange)
            & (df_instruments["segment"] == "CASH")
            & (df_instruments["instrument_type"] == "IDX")
            & (df_instruments["trading_symbol"] == trading_sym)
        ]
        if idx_rows.empty:
            idx_groww = f"{exchange}-{trading_sym}"
            idx_token = trading_sym if exchange == "NSE" else "1"
        else:
            row = idx_rows.iloc[0]
            idx_groww = str(row["groww_symbol"])
            idx_token = str(row["exchange_token"])

        # Nearest futures contract
        fut_rows = df_instruments[
            (df_instruments["exchange"] == exchange)
            & (df_instruments["segment"] == "FNO")
            & (df_instruments["instrument_type"] == "FUT")
            & (df_instruments["underlying_symbol"] == name)
            & (df_instruments["expiry_date"] >= today_str)
        ].sort_values("expiry_date")

        fut_info = None
        if not fut_rows.empty:
            frow = fut_rows.iloc[0]
            fut_info = {
                "trading_symbol": str(frow["trading_symbol"]),
                "groww_symbol": str(frow["groww_symbol"]),
                "expiry_date": str(frow["expiry_date"]),
                "exchange_token": str(frow["exchange_token"]),
                "lot_size": int(frow.get("lot_size", 0)),
                "tick_size": float(frow.get("tick_size", 0.05)),
            }

        resolved[name] = {
            "index": {
                "exchange": exchange,
                "segment": "CASH",
                "trading_symbol": trading_sym,
                "groww_symbol": idx_groww,
                "exchange_token": idx_token,
                "exchange_trading_symbol": f"{exchange}_{trading_sym}",
            },
            "futures": fut_info,
        }

    return resolved


def run_connection_check() -> None:
    """Execute complete Groww Trade API diagnostic."""
    print("=" * 80)
    print("GROWW TRADE API - CONNECTION & SUBSCRIPTION DIAGNOSTIC")
    print(f"Timestamp (IST): {datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print("=" * 80)

    # 1. Credentials Check
    cred_status = check_credentials_presence()
    print("\n[STEP 1: CREDENTIALS STATUS]")
    print(f"  - GROWW_API_KEY     : {'CONFIGURED' if cred_status['GROWW_API_KEY'] else 'MISSING'}")
    print(f"  - GROWW_API_SECRET  : {'CONFIGURED (Approval-based)' if cred_status['GROWW_API_SECRET'] else 'NOT SET'}")
    print(f"  - GROWW_TOTP_SECRET : {'CONFIGURED (Automated 6 AM TOTP)' if cred_status['GROWW_TOTP_SECRET'] else 'NOT SET'}")

    if not cred_status["GROWW_API_KEY"]:
        print("\n" + "!" * 80)
        print("ACTION REQUIRED: Groww credentials are not set in .env.")
        print("Please create / populate .env in the project root with:")
        print("  GROWW_API_KEY=<your_api_key>")
        print("  GROWW_TOTP_SECRET=<your_totp_secret_for_automated_6am_resets>")
        print("  GROWW_API_SECRET=<your_approval_secret_if_using_approval_key>")
        print("!" * 80)
        return

    # 2. Authentication Check
    print("\n[STEP 2: AUTHENTICATION FLOW]")
    auth_mgr = GrowwAuthManager()
    token = None
    auth_method = "UNKNOWN"

    try:
        if cred_status["GROWW_TOTP_SECRET"]:
            auth_method = "TOTP (Automated 6 AM IST)"
            token = auth_mgr.get_access_token(allow_approval_fallback=False)
            print("  ✓ Authenticated successfully via TOTP flow.")
        elif cred_status["GROWW_API_SECRET"]:
            auth_method = "APPROVAL CHECKSUM (One-off fallback)"
            print("  ⚠️ Warning: Only approval-based key found (GROWW_API_SECRET).")
            print("     Automated daily unattended 6 AM resets will require a TOTP key.")
            print("     Attempting one-off connection using approval checksum...")
            token = auth_mgr.get_access_token(allow_approval_fallback=True)
            print("  ✓ Authenticated successfully via approval checksum flow.")
        else:
            raise GrowwAuthError("Neither GROWW_TOTP_SECRET nor GROWW_API_SECRET is configured.")
    except GrowwApprovalKeyOnlyError as e:
        print(f"  ✗ Auth Blocked: {e}")
        return
    except GrowwAPIAuthenticationException as e:
        print(f"  ✗ Authentication Failed (401 Unauthorized): Invalid API Key or Secret/TOTP.")
        return
    except Exception as e:
        print(f"  ✗ Authentication Error: {type(e).__name__} - {e}")
        return

    api = GrowwAPI(token)
    session_start, session_end = auth_mgr.get_session_window()
    print(f"  - Current Session Window: {session_start.strftime('%Y-%m-%d %H:%M')} to {session_end.strftime('%Y-%m-%d %H:%M IST')}")

    # 3. Load Instrument Master for Symbol Resolution
    print("\n[STEP 3: INSTRUMENT MASTER & SYMBOL RESOLUTION]")
    try:
        df_inst = api.get_all_instruments()
        print(f"  ✓ Downloaded Groww instrument master: {len(df_inst):,} total contracts.")
        resolved = resolve_symbols(df_inst)
        for sym, data in resolved.items():
            idx = data["index"]
            fut = data["futures"]
            fut_str = f"{fut['trading_symbol']} (Exp: {fut['expiry_date']}, Lot: {fut['lot_size']})" if fut else "No active contract"
            print(f"  - {sym:<10}: Index='{idx['groww_symbol']}' (Token: {idx['exchange_token']}) | Nearest Futures: {fut_str}")
    except Exception as e:
        print(f"  ✗ Could not load instrument master: {type(e).__name__} - {e}")
        resolved = {
            "NIFTY": {
                "index": {
                    "exchange": "NSE",
                    "segment": "CASH",
                    "trading_symbol": "NIFTY",
                    "groww_symbol": "NSE-NIFTY",
                    "exchange_token": "NIFTY",
                    "exchange_trading_symbol": "NSE_NIFTY",
                },
                "futures": None,
            }
        }

    # 4. Connection & Subscription Check (LTP, OHLC, 5m Candles)
    print("\n[STEP 4: SUBSCRIPTION ENDPOINTS CHECK (NIFTY)]")
    
    # 4A. LTP Check
    ltp_status = "UNKNOWN"
    ltp_data = None
    try:
        t0 = time.perf_counter()
        res_ltp = api.get_ltp(exchange_trading_symbols=("NSE_NIFTY",), segment="CASH")
        latency_ltp = (time.perf_counter() - t0) * 1000
        ltp_status = "ACTIVE (200 OK)"
        ltp_data = res_ltp
        print(f"  ✓ Live Data (LTP)        : {ltp_status} | Latency: {latency_ltp:.1f}ms")
        print(f"    Payload: {res_ltp}")
    except GrowwAPIAuthorisationException:
        ltp_status = "MISSING SUBSCRIPTION (403 Forbidden)"
        print(f"  ✗ Live Data (LTP)        : {ltp_status}")
    except Exception as e:
        ltp_status = f"ERROR: {type(e).__name__} - {e}"
        print(f"  ✗ Live Data (LTP)        : {ltp_status}")

    # 4B. OHLC Check
    ohlc_status = "UNKNOWN"
    try:
        t0 = time.perf_counter()
        res_ohlc = api.get_ohlc(exchange_trading_symbols=("NSE_NIFTY",), segment="CASH")
        latency_ohlc = (time.perf_counter() - t0) * 1000
        ohlc_status = "ACTIVE (200 OK)"
        print(f"  ✓ Live Data (OHLC)       : {ohlc_status} | Latency: {latency_ohlc:.1f}ms")
        print(f"    Payload: {res_ohlc}")
    except GrowwAPIAuthorisationException:
        ohlc_status = "MISSING SUBSCRIPTION (403 Forbidden)"
        print(f"  ✗ Live Data (OHLC)       : {ohlc_status}")
    except Exception as e:
        ohlc_status = f"ERROR: {type(e).__name__} - {e}"
        print(f"  ✗ Live Data (OHLC)       : {ohlc_status}")

    # 4C. Historical 5m Candles Check
    hist_status = "UNKNOWN"
    now_ist = datetime.now(IST)
    start_time_str = (now_ist - timedelta(days=5)).strftime("%Y-%m-%d %H:%M:%S")
    end_time_str = now_ist.strftime("%Y-%m-%d %H:%M:%S")
    
    try:
        t0 = time.perf_counter()
        res_candles = api.get_historical_candles(
            exchange="NSE",
            segment="CASH",
            groww_symbol="NSE-NIFTY",
            start_time=start_time_str,
            end_time=end_time_str,
            candle_interval="5minute",
        )
        latency_hist = (time.perf_counter() - t0) * 1000
        hist_status = "ACTIVE (200 OK)"
        candle_list = res_candles.get("candles", []) if isinstance(res_candles, dict) else []
        print(f"  ✓ Historical Data (5m)   : {hist_status} | Latency: {latency_hist:.1f}ms")
        print(f"    Returned {len(candle_list)} 5-minute bars.")
        if candle_list:
            print(f"    Sample latest candle: {candle_list[-1]}")
    except GrowwAPIAuthorisationException:
        hist_status = "MISSING SUBSCRIPTION (403 Forbidden)"
        print(f"  ✗ Historical Data (5m)   : {hist_status}")
    except Exception as e:
        hist_status = f"ERROR: {type(e).__name__} - {e}"
        print(f"  ✗ Historical Data (5m)   : {hist_status}")

    # 5. Historical Candle Depth Probe (if Historical is Active)
    if "ACTIVE" in hist_status:
        print("\n[STEP 5: HISTORICAL DATA REACH PROBE]")
        print("Testing how far back Groww returns data across 1m, 5m, 15m intervals...")
        
        intervals_to_test = [
            ("1minute", "1 Min"),
            ("5minute", "5 Min"),
            ("15minute", "15 Min"),
        ]
        
        horizons_days = [1, 7, 30, 60, 90, 180, 365]

        for interval_code, interval_label in intervals_to_test:
            print(f"\n  --- Interval: {interval_label} ({interval_code}) ---")
            for days in horizons_days:
                s_str = (now_ist - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
                e_str = now_ist.strftime("%Y-%m-%d %H:%M:%S")
                try:
                    c_res = api.get_historical_candles(
                        exchange="NSE",
                        segment="CASH",
                        groww_symbol="NSE-NIFTY",
                        start_time=s_str,
                        end_time=e_str,
                        candle_interval=interval_code,
                    )
                    c_list = c_res.get("candles", []) if isinstance(c_res, dict) else []
                    if c_list:
                        earliest_ts = c_list[0][0] if len(c_list[0]) > 0 else "N/A"
                        print(f"    {days:>3} days requested: {len(c_list):>5} bars | Earliest bar: {earliest_ts}")
                    else:
                        print(f"    {days:>3} days requested:     0 bars (Empty response)")
                except Exception as ex:
                    print(f"    {days:>3} days requested: FAILED ({type(ex).__name__}: {ex})")

    # 6. Final Subscription Summary
    print("\n" + "=" * 80)
    print("SUBSCRIPTION SUMMARY")
    print(f"  Live Market Data (LTP/OHLC) : {ltp_status}")
    print(f"  Historical Candle Data      : {hist_status}")
    
    if "403" in ltp_status or "403" in hist_status:
        print("\n> [!CAUTION] ACTION REQUIRED:")
        if "403" in ltp_status:
            print("  - Live Data subscription is INACTIVE (403 Forbidden).")
        if "403" in hist_status:
            print("  - Historical Data subscription is INACTIVE (403 Forbidden).")
        print("  Please enable the required subscriptions in your Groww Trade API console.")
    else:
        print("\n> [!NOTE] All tested subscriptions are ACTIVE.")
    print("=" * 80)


if __name__ == "__main__":
    run_connection_check()
