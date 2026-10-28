"""Audit 1m, 5m, 15m and Daily historical bars from Angel One for NIFTY.
Analyzes timestamps, session start/end, missing minutes histogram, and intraday vs daily comparison.
"""

import os
import sys
import json
import time
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd
import pytz
from dotenv import load_dotenv

WORKSPACE_ENV = Path(".env")
if WORKSPACE_ENV.exists():
    load_dotenv(dotenv_path=WORKSPACE_ENV)

from data.angel_provider import AngelOneProvider
from data.rate_limiter import shared_rate_limiter

provider = AngelOneProvider()
provider.connect()

tz = pytz.timezone("Asia/Kolkata")
token = "99926000"  # NIFTY token
exchange = "NSE"

dates = [
    ("2026-10-12", "2026-10-12"),
    ("2026-10-13", "2026-10-13"),
    ("2026-10-14", "2026-10-14"),
    ("2026-10-15", "2026-10-15"),
    ("2026-10-16", "2026-10-16"),
    ("2026-10-19", "2026-10-19"),
    ("2026-10-21", "2026-10-21"),
    ("2026-10-22", "2026-10-22"),
    ("2026-10-23", "2026-10-23"),
]

def fetch_candle_data(interval, from_dt, to_dt):
    params = {
        "exchange": exchange,
        "symboltoken": token,
        "interval": interval,
        "fromdate": from_dt,
        "todate": to_dt,
    }
    # Rate limited execute
    resp = shared_rate_limiter.execute_with_backoff(
        "getCandleData",
        provider.client.getCandleData,
        params,
    )
    time.sleep(0.6)  # Safe spacing
    if resp and resp.get("status") and resp.get("data"):
        df = pd.DataFrame(resp["data"], columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        return df
    return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])

print("=" * 80)
print("AUDITING 1m, 5m, 15m BARS ACROSS 9 SESSIONS (2026-10-12 to 2026-10-23)")
print("=" * 80)

# 1. 1m Analysis
print("\n--- 1. ONE_MINUTE ANALYSIS ---")
all_1m = []
sessions_1m = {}
for d_str, _ in dates:
    from_s = f"{d_str} 09:00"
    to_s = f"{d_str} 15:45"
    df = fetch_candle_data("ONE_MINUTE", from_s, to_s)
    sessions_1m[d_str] = df
    all_1m.append(df)
    times = df["timestamp"].dt.strftime("%H:%M").tolist()
    first_time = times[0] if times else "None"
    last_time = times[-1] if times else "None"
    second_to_last = times[-2] if len(times) >= 2 else "None"
    print(f"Date {d_str}: {len(df)} rows | First: {first_time} | 2nd-to-last: {second_to_last} | Last: {last_time}")

# Histogram of missing minutes by time of day
print("\n--- 1m MINUTE-BY-MINUTE COVERAGE HISTOGRAM (09:15 to 15:30) ---")
expected_minutes = []
cur_m = datetime.strptime("09:15", "%H:%M")
end_m = datetime.strptime("15:30", "%H:%M")
while cur_m <= end_m:
    expected_minutes.append(cur_m.strftime("%H:%M"))
    cur_m += timedelta(minutes=1)

minute_counts = defaultdict(int)
for d_str, df in sessions_1m.items():
    times_set = set(df["timestamp"].dt.strftime("%H:%M"))
    for m in expected_minutes:
        if m in times_set:
            minute_counts[m] += 1

missing_histogram = {}
for m in expected_minutes:
    present = minute_counts[m]
    if present < 9:
        missing_histogram[m] = 9 - present

print(f"Total expected minutes per session (09:15 to 15:30): {len(expected_minutes)}")
print(f"Minutes present in all 9 sessions (9/9): {sum(1 for v in minute_counts.values() if v == 9)}")
print(f"Minutes missing in at least 1 session: {len(missing_histogram)}")
print("\nDetailed Missing Minutes Histogram (time: missing count out of 9 sessions):")
for m, miss_count in sorted(missing_histogram.items()):
    print(f"  Minute {m} -> Missing in {miss_count}/9 sessions (Present in {minute_counts[m]}/9)")

# Check 5m Bars
print("\n--- 2. FIVE_MINUTE ANALYSIS ---")
sessions_5m = {}
for d_str, _ in dates:
    from_s = f"{d_str} 09:00"
    to_s = f"{d_str} 15:45"
    df = fetch_candle_data("FIVE_MINUTE", from_s, to_s)
    sessions_5m[d_str] = df
    times = df["timestamp"].dt.strftime("%H:%M").tolist()
    first_time = times[0] if times else "None"
    last_time = times[-1] if times else "None"
    print(f"Date {d_str}: {len(df)} rows | First: {first_time} | Last: {last_time} | Last 3: {times[-3:]}")

# Check 15m Bars
print("\n--- 3. FIFTEEN_MINUTE ANALYSIS ---")
sessions_15m = {}
for d_str, _ in dates:
    from_s = f"{d_str} 09:00"
    to_s = f"{d_str} 15:45"
    df = fetch_candle_data("FIFTEEN_MINUTE", from_s, to_s)
    sessions_15m[d_str] = df
    times = df["timestamp"].dt.strftime("%H:%M").tolist()
    first_time = times[0] if times else "None"
    last_time = times[-1] if times else "None"
    print(f"Date {d_str}: {len(df)} rows | First: {first_time} | Last: {last_time} | Last 3: {times[-3:]}")

# Check Daily vs Intraday Close Comparison
print("\n--- 4. DAILY VS INTRADAY CLOSE COMPARISON ---")
df_daily = fetch_candle_data("ONE_DAY", "2026-10-12 00:00", "2026-10-23 23:59")
daily_map = dict(zip(df_daily["timestamp"].dt.strftime("%Y-%m-%d"), df_daily["close"]))

print(f"{'Date':<12} {'1m Last Time':<14} {'1m Last Close':<14} {'15m Last Close':<14} {'Daily Close':<14} {'Diff (1m - Daily)':<18}")
for d_str, _ in dates:
    df_1 = sessions_1m[d_str]
    df_15 = sessions_15m[d_str]
    last_1m_row = df_1.iloc[-1]
    last_1m_time = last_1m_row["timestamp"].strftime("%H:%M")
    last_1m_close = last_1m_row["close"]
    last_15m_close = df_15.iloc[-1]["close"]
    daily_close = daily_map.get(d_str, float("nan"))
    diff = last_1m_close - daily_close
    print(f"{d_str:<12} {last_1m_time:<14} {last_1m_close:<14.2f} {last_15m_close:<14.2f} {daily_close:<14.2f} {diff:<18.2f}")
