"""Diagnostic script to test Groww Trade API historical endpoints.

Tests:
1. Authentication via TOTP / Bearer token flow (GROWW_TOTP_TOKEN & GROWW_TOTP_SECRET).
2. get_historical_candles for NIFTY Index across 1m, 5m, 15m intervals for 2020, 2023, and last week.
3. get_historical_candles for NIFTY Nearest Futures across 1m, 5m, 15m for 2020, 2023, and last week.
4. get_expiries for 2021 and 2024.
5. get_contracts for 2021 and 2024.
6. get_historical_candles for an expired futures contract with Open Interest (OI).
Zero secret logging: credentials are never printed.
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pyotp
from dotenv import load_dotenv

# Setup path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from growwapi.groww.client import GrowwAPI
from growwapi.groww.exceptions import GrowwAPIException

load_dotenv(override=True)


def authenticate() -> Tuple[Optional[GrowwAPI], str, Dict[str, Any]]:
    """Authenticate safely using GROWW_TOTP_TOKEN and GROWW_TOTP_SECRET."""
    totp_token = os.getenv("GROWW_TOTP_TOKEN") or os.getenv("GROWW_API_KEY")
    totp_secret = os.getenv("GROWW_TOTP_SECRET")
    api_secret = os.getenv("GROWW_API_SECRET")

    auth_info = {
        "has_totp_token": bool(totp_token),
        "has_totp_secret": bool(totp_secret),
        "has_api_secret": bool(api_secret),
        "method_attempted": "UNKNOWN",
        "session_token_obtained": False,
        "error": None,
    }

    if not totp_token and not totp_secret:
        auth_info["error"] = "Neither GROWW_TOTP_TOKEN nor GROWW_TOTP_SECRET found in .env."
        return None, "NO_CREDENTIALS", auth_info

    # Mode 1: TOTP generation via pyotp (if totp_secret is a base32 string)
    if totp_secret and totp_token:
        try:
            code = pyotp.TOTP(totp_secret.strip()).now()
            sess_token = GrowwAPI.get_access_token(api_key=totp_token.strip(), totp=code)
            auth_info["method_attempted"] = "TOTP Flow (pyotp code generated)"
            auth_info["session_token_obtained"] = True
            return GrowwAPI(sess_token), "TOTP_PYOTP", auth_info
        except Exception as e:
            auth_info["totp_pyotp_error"] = f"{type(e).__name__}: {str(e)[:80]}"

    # Mode 2: If GROWW_TOTP_SECRET is itself a valid JWT Bearer token
    if totp_secret and "." in totp_secret:
        auth_info["method_attempted"] = "Direct Bearer Token (GROWW_TOTP_SECRET)"
        auth_info["session_token_obtained"] = True
        return GrowwAPI(totp_secret.strip()), "DIRECT_BEARER_TOTP_SECRET", auth_info

    # Mode 3: Approval exchange fallback
    if totp_token and api_secret:
        try:
            sess_token = GrowwAPI.get_access_token(api_key=totp_token.strip(), secret=api_secret.strip())
            auth_info["method_attempted"] = "Approval Secret Exchange"
            auth_info["session_token_obtained"] = True
            return GrowwAPI(sess_token), "APPROVAL_EXCHANGE", auth_info
        except Exception as e:
            auth_info["approval_error"] = f"{type(e).__name__}: {str(e)[:80]}"

    # Mode 4: Direct Bearer token with GROWW_TOTP_TOKEN
    if totp_token and "." in totp_token:
        auth_info["method_attempted"] = "Direct Bearer Token (GROWW_TOTP_TOKEN)"
        auth_info["session_token_obtained"] = True
        return GrowwAPI(totp_token.strip()), "DIRECT_BEARER_TOTP_TOKEN", auth_info

    auth_info["error"] = "Could not establish an authenticated GrowwAPI client."
    return None, "AUTH_FAILED", auth_info


def inspect_candle_payload(payload: Any) -> Dict[str, Any]:
    """Inspect candle response payload for row count, earliest date, gaps, volume, and OI."""
    stats = {
        "row_count": 0,
        "earliest_date": None,
        "latest_date": None,
        "has_gaps": False,
        "has_volume": False,
        "volume_sample": None,
        "has_oi": False,
        "oi_sample": None,
        "sample_columns": [],
    }

    if not payload:
        return stats

    candles = None
    if isinstance(payload, dict):
        candles = payload.get("candles") or payload.get("data") or payload.get("candle_data")
        if candles is None and "historical_candles" in payload:
            candles = payload["historical_candles"]
    elif isinstance(payload, list):
        candles = payload

    if not candles or not isinstance(candles, list):
        return stats

    stats["row_count"] = len(candles)
    first_candle = candles[0]
    last_candle = candles[-1]

    # Handle dictionary representation
    if isinstance(first_candle, dict):
        stats["sample_columns"] = list(first_candle.keys())
        stats["earliest_date"] = first_candle.get("time") or first_candle.get("date") or first_candle.get("timestamp")
        stats["latest_date"] = last_candle.get("time") or last_candle.get("date") or last_candle.get("timestamp")
        
        for vol_key in ["volume", "vol", "v", "traded_volume"]:
            if vol_key in first_candle:
                stats["has_volume"] = True
                stats["volume_sample"] = first_candle[vol_key]
                break

        for oi_key in ["oi", "open_interest", "openInterest"]:
            if oi_key in first_candle:
                stats["has_oi"] = True
                stats["oi_sample"] = first_candle[oi_key]
                break

    # Handle list representation: [timestamp, open, high, low, close, volume, oi, ...]
    elif isinstance(first_candle, (list, tuple)):
        stats["sample_columns"] = [f"col_{i}" for i in range(len(first_candle))]
        stats["earliest_date"] = first_candle[0] if len(first_candle) > 0 else None
        stats["latest_date"] = last_candle[0] if len(last_candle) > 0 else None
        if len(first_candle) >= 6:
            stats["has_volume"] = True
            stats["volume_sample"] = first_candle[5]
        if len(first_candle) >= 7:
            stats["has_oi"] = True
            stats["oi_sample"] = first_candle[6]

    return stats


def run_all_checks() -> List[Dict[str, Any]]:
    """Execute all requested checks systematically."""
    api, auth_method, auth_info = authenticate()
    results = []

    print("=" * 80)
    print("GROWW TRADE API HISTORICAL DATA CONNECTION CHECK")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Authentication Method: {auth_method}")
    print(f"Session Token Ready: {auth_info['session_token_obtained']}")
    print("=" * 80)

    if not api:
        print(f"FATAL: Authentication failed. {auth_info.get('error')}")
        return results

    index_cases = [
        {"period": "2020 Date (2020-03-23)", "start": "2020-03-23 09:15:00", "end": "2020-03-23 15:30:00"},
        {"period": "2023 Date (2023-06-15)", "start": "2023-06-15 09:15:00", "end": "2023-06-15 15:30:00"},
        {"period": "Last Week (2026-10-19 to 2026-10-23)", "start": "2026-10-19 09:15:00", "end": "2026-10-23 15:30:00"},
    ]
    intervals = [
        ("1m", GrowwAPI.CANDLE_INTERVAL_MIN_1),
        ("5m", GrowwAPI.CANDLE_INTERVAL_MIN_5),
        ("15m", GrowwAPI.CANDLE_INTERVAL_MIN_15),
    ]

    # 1. NIFTY INDEX (exchange="NSE", segment="CASH", groww_symbol="NSE-NIFTY")
    print("\n--- 1. NIFTY INDEX HISTORICAL CANDLES ---")
    for case in index_cases:
        for int_label, int_val in intervals:
            test_id = f"NIFTY Index | {case['period']} | {int_label}"
            try:
                t0 = time.perf_counter()
                res = api.get_historical_candles(
                    exchange="NSE",
                    segment="CASH",
                    groww_symbol="NSE-NIFTY",
                    start_time=case["start"],
                    end_time=case["end"],
                    candle_interval=int_val,
                )
                dur_ms = (time.perf_counter() - t0) * 1000
                stats = inspect_candle_payload(res)
                r = {
                    "test": test_id,
                    "target": "NIFTY Index (CASH)",
                    "groww_symbol": "NSE-NIFTY",
                    "timeframe": int_label,
                    "status": "SUCCESS (200 OK)",
                    "latency_ms": round(dur_ms, 1),
                    "earliest_date": stats["earliest_date"],
                    "latest_date": stats["latest_date"],
                    "row_count": stats["row_count"],
                    "has_gaps": stats["has_gaps"],
                    "has_volume": stats["has_volume"],
                    "has_oi": stats["has_oi"],
                    "error": None,
                }
            except Exception as e:
                r = {
                    "test": test_id,
                    "target": "NIFTY Index (CASH)",
                    "groww_symbol": "NSE-NIFTY",
                    "timeframe": int_label,
                    "status": f"FAILED ({type(e).__name__})",
                    "latency_ms": None,
                    "earliest_date": None,
                    "latest_date": None,
                    "row_count": 0,
                    "has_gaps": None,
                    "has_volume": None,
                    "has_oi": None,
                    "error": str(e),
                }
            results.append(r)
            status_text = r["error"] if r["error"] else f"rows={r['row_count']}, earliest={r['earliest_date']}, vol={r['has_volume']}, oi={r['has_oi']}"
            print(f"  [{r['status']}] {test_id} -> {status_text}")

    # 2. NIFTY NEAREST FUTURES (groww_symbol="NSE-NIFTY-27Oct26-FUT", exchange="NSE", segment="FNO")
    fut_symbol = "NSE-NIFTY-27Oct26-FUT"
    print(f"\n--- 2. NIFTY NEAREST FUTURES ({fut_symbol}) ---")
    for case in index_cases:
        for int_label, int_val in intervals:
            test_id = f"NIFTY Futures | {case['period']} | {int_label}"
            try:
                t0 = time.perf_counter()
                res = api.get_historical_candles(
                    exchange="NSE",
                    segment="FNO",
                    groww_symbol=fut_symbol,
                    start_time=case["start"],
                    end_time=case["end"],
                    candle_interval=int_val,
                )
                dur_ms = (time.perf_counter() - t0) * 1000
                stats = inspect_candle_payload(res)
                r = {
                    "test": test_id,
                    "target": "NIFTY Futures (FNO)",
                    "groww_symbol": fut_symbol,
                    "timeframe": int_label,
                    "status": "SUCCESS (200 OK)",
                    "latency_ms": round(dur_ms, 1),
                    "earliest_date": stats["earliest_date"],
                    "latest_date": stats["latest_date"],
                    "row_count": stats["row_count"],
                    "has_gaps": stats["has_gaps"],
                    "has_volume": stats["has_volume"],
                    "has_oi": stats["has_oi"],
                    "error": None,
                }
            except Exception as e:
                r = {
                    "test": test_id,
                    "target": "NIFTY Futures (FNO)",
                    "groww_symbol": fut_symbol,
                    "timeframe": int_label,
                    "status": f"FAILED ({type(e).__name__})",
                    "latency_ms": None,
                    "earliest_date": None,
                    "latest_date": None,
                    "row_count": 0,
                    "has_gaps": None,
                    "has_volume": None,
                    "has_oi": None,
                    "error": str(e),
                }
            results.append(r)
            status_text = r["error"] if r["error"] else f"rows={r['row_count']}, earliest={r['earliest_date']}, vol={r['has_volume']}, oi={r['has_oi']}"
            print(f"  [{r['status']}] {test_id} -> {status_text}")

    # 3. get_expiries for 2021 and 2024
    print("\n--- 3. get_expiries (2021 & 2024) ---")
    for yr in [2021, 2024]:
        test_id = f"get_expiries(exchange='NSE', underlying_symbol='NIFTY', year={yr})"
        try:
            t0 = time.perf_counter()
            res = api.get_expiries(exchange="NSE", underlying_symbol="NIFTY", year=yr)
            dur_ms = (time.perf_counter() - t0) * 1000
            exp_list = res.get("expiries") if isinstance(res, dict) else (res if isinstance(res, list) else [])
            r = {
                "test": test_id,
                "target": f"NIFTY Expiries ({yr})",
                "groww_symbol": None,
                "timeframe": None,
                "status": "SUCCESS (200 OK)",
                "latency_ms": round(dur_ms, 1),
                "earliest_date": exp_list[0] if exp_list else None,
                "latest_date": exp_list[-1] if exp_list else None,
                "row_count": len(exp_list),
                "has_gaps": False,
                "has_volume": False,
                "has_oi": False,
                "error": None,
                "raw_payload": str(res)[:100],
            }
        except Exception as e:
            r = {
                "test": test_id,
                "target": f"NIFTY Expiries ({yr})",
                "groww_symbol": None,
                "timeframe": None,
                "status": f"FAILED ({type(e).__name__})",
                "latency_ms": None,
                "earliest_date": None,
                "latest_date": None,
                "row_count": 0,
                "has_gaps": None,
                "has_volume": None,
                "has_oi": None,
                "error": str(e),
            }
        results.append(r)
        status_text = r["error"] if r["error"] else f"{r['row_count']} expiries, earliest={r['earliest_date']}"
        print(f"  [{r['status']}] {test_id} -> {status_text}")

    # 4. get_contracts for 2021 and 2024
    print("\n--- 4. get_contracts (2021 & 2024) ---")
    contract_dates = [
        ("2021-12-30", 2021),
        ("2024-10-31", 2024),
    ]
    for exp_date, yr in contract_dates:
        test_id = f"get_contracts(exchange='NSE', underlying_symbol='NIFTY', expiry_date='{exp_date}')"
        try:
            t0 = time.perf_counter()
            res = api.get_contracts(exchange="NSE", underlying_symbol="NIFTY", expiry_date=exp_date)
            dur_ms = (time.perf_counter() - t0) * 1000
            c_list = res.get("contracts") if isinstance(res, dict) else (res if isinstance(res, list) else [])
            r = {
                "test": test_id,
                "target": f"NIFTY Contracts ({exp_date})",
                "groww_symbol": None,
                "timeframe": None,
                "status": "SUCCESS (200 OK)",
                "latency_ms": round(dur_ms, 1),
                "earliest_date": exp_date,
                "latest_date": exp_date,
                "row_count": len(c_list),
                "has_gaps": False,
                "has_volume": False,
                "has_oi": False,
                "error": None,
                "raw_payload": str(res)[:100],
            }
        except Exception as e:
            r = {
                "test": test_id,
                "target": f"NIFTY Contracts ({exp_date})",
                "groww_symbol": None,
                "timeframe": None,
                "status": f"FAILED ({type(e).__name__})",
                "latency_ms": None,
                "earliest_date": None,
                "latest_date": None,
                "row_count": 0,
                "has_gaps": None,
                "has_volume": None,
                "has_oi": None,
                "error": str(e),
            }
        results.append(r)
        status_text = r["error"] if r["error"] else f"{r['row_count']} contracts"
        print(f"  [{r['status']}] {test_id} -> {status_text}")

    # 5. One expired futures contract with Open Interest (OI)
    print("\n--- 5. Expired Futures Contract with Open Interest (OI) ---")
    expired_fut_symbol = "NSE-NIFTY-31Oct24-FUT"
    test_id = f"get_historical_candles(expired_futures='{expired_fut_symbol}', 2024-10-21 to 2024-10-25, 15m)"
    try:
        t0 = time.perf_counter()
        res = api.get_historical_candles(
            exchange="NSE",
            segment="FNO",
            groww_symbol=expired_fut_symbol,
            start_time="2024-10-21 09:15:00",
            end_time="2024-10-25 15:30:00",
            candle_interval=GrowwAPI.CANDLE_INTERVAL_MIN_15,
        )
        dur_ms = (time.perf_counter() - t0) * 1000
        stats = inspect_candle_payload(res)
        r = {
            "test": test_id,
            "target": f"Expired Futures ({expired_fut_symbol})",
            "groww_symbol": expired_fut_symbol,
            "timeframe": "15m",
            "status": "SUCCESS (200 OK)",
            "latency_ms": round(dur_ms, 1),
            "earliest_date": stats["earliest_date"],
            "latest_date": stats["latest_date"],
            "row_count": stats["row_count"],
            "has_gaps": stats["has_gaps"],
            "has_volume": stats["has_volume"],
            "has_oi": stats["has_oi"],
            "error": None,
        }
    except Exception as e:
        r = {
            "test": test_id,
            "target": f"Expired Futures ({expired_fut_symbol})",
            "groww_symbol": expired_fut_symbol,
            "timeframe": "15m",
            "status": f"FAILED ({type(e).__name__})",
            "latency_ms": None,
            "earliest_date": None,
            "latest_date": None,
            "row_count": 0,
            "has_gaps": None,
            "has_volume": None,
            "has_oi": None,
            "error": str(e),
        }
    results.append(r)
    status_text = r["error"] if r["error"] else f"rows={r['row_count']}, earliest={r['earliest_date']}, vol={r['has_volume']}, oi={r['has_oi']}"
    print(f"  [{r['status']}] {test_id} -> {status_text}")

    # Output json results summary
    out_path = ROOT_DIR / "reports" / "groww_historical_check_results.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(results, indent=2))
    print(f"\nSaved detailed results to {out_path}")

    return results


if __name__ == "__main__":
    run_all_checks()
