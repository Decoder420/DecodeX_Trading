import os
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
import pyotp
from SmartApi import SmartConnect
import pandas as pd
from collections import Counter
import time

load_dotenv()
client = SmartConnect(api_key=os.getenv("ANGEL_API_KEY"))
orig_rh = client.requestHeaders
client.requestHeaders = lambda: {**orig_rh(), "Content-Type": "application/json"}
totp = pyotp.TOTP(os.getenv("ANGEL_TOTP_SECRET")).now()
client.generateSession(os.getenv("ANGEL_CLIENT_ID"), os.getenv("ANGEL_MPIN"), totp)

params = {
    "exchange": "NSE",
    "symboltoken": "99926000",
    "interval": "ONE_MINUTE",
    "fromdate": "2026-10-12 09:15",
    "todate": "2026-10-23 15:30",
}

# Fetch with rate limit handling
for _ in range(5):
    try:
        resp = client.getCandleData(params)
        bars = resp.get("data") or []
        if bars:
            break
    except Exception as e:
        time.sleep(2.0)

df = pd.DataFrame(bars, columns=["timestamp", "open", "high", "low", "close", "volume"])
df["dt"] = pd.to_datetime(df["timestamp"])
df["date"] = df["dt"].dt.date
df["time_str"] = df["dt"].dt.strftime("%H:%M")

dates = sorted(df["date"].unique())
print(f"Total bars: {len(df)} across {len(dates)} dates")

# Build all 375 expected minutes
all_expected_mins = [t.strftime("%H:%M") for t in pd.date_range("2026-10-12 09:15", "2026-10-12 15:29", freq="1min")]
print(f"Standard session expected minutes: {len(all_expected_mins)} (09:15 to 15:29)")

missing_counter = Counter()

print("\n--- PER-SESSION MINUTE AUDIT ---")
for d in dates:
    sub = df[df["date"] == d]
    actual_mins = set(sub["time_str"])
    missing = [m for m in all_expected_mins if m not in actual_mins]
    for m in missing:
        missing_counter[m] += 1
    print(f"Date {d}: {len(sub)} bars | Earliest: {sub['time_str'].min()} | Latest: {sub['time_str'].max()} | Missing count: {len(missing)}")
    print(f"   Missing minutes: {missing}")

print("\n--- HISTOGRAM OF MISSING MINUTES (across 9 sessions) ---")
for m, cnt in sorted(missing_counter.items(), key=lambda x: x[0]):
    print(f"  {m}: missing in {cnt}/9 sessions")

from data.rate_limiter import shared_rate_limiter

time.sleep(2.0)
params_5m = {**params, "interval": "FIVE_MINUTE"}
resp_5m = shared_rate_limiter.execute_with_backoff("getCandleData", client.getCandleData, params_5m)
bars_5m = resp_5m.get("data") or []
df_5m = pd.DataFrame(bars_5m, columns=["timestamp", "open", "high", "low", "close", "volume"])
df_5m["dt"] = pd.to_datetime(df_5m["timestamp"])
df_5m["date"] = df_5m["dt"].dt.date
df_5m["time_str"] = df_5m["dt"].dt.strftime("%H:%M")

print("\n--- 5-MINUTE BARS AUDIT ---")
print(f"Total 5m bars: {len(df_5m)} across {df_5m['date'].nunique()} dates (expected 9 x 75 = 675)")
for d in sorted(df_5m["date"].unique()):
    sub = df_5m[df_5m["date"] == d]
    print(f"  {d}: {len(sub)} 5m bars | Earliest: {sub['time_str'].min()} | Latest: {sub['time_str'].max()}")

time.sleep(2.0)
params_15m = {**params, "interval": "FIFTEEN_MINUTE"}
resp_15m = shared_rate_limiter.execute_with_backoff("getCandleData", client.getCandleData, params_15m)
bars_15m = resp_15m.get("data") or []
df_15m = pd.DataFrame(bars_15m, columns=["timestamp", "open", "high", "low", "close", "volume"])
df_15m["dt"] = pd.to_datetime(df_15m["timestamp"])
df_15m["date"] = df_15m["dt"].dt.date
df_15m["time_str"] = df_15m["dt"].dt.strftime("%H:%M")

print("\n--- 15-MINUTE BARS AUDIT ---")
print(f"Total 15m bars: {len(df_15m)} across {df_15m['date'].nunique()} dates (expected 9 x 25 = 225)")
for d in sorted(df_15m["date"].unique()):
    sub = df_15m[df_15m["date"] == d]
    print(f"  {d}: {len(sub)} 15m bars | Earliest: {sub['time_str'].min()} | Latest: {sub['time_str'].max()} | Times: {sub['time_str'].tolist()[-4:]}")

time.sleep(2.0)
params_1d = {**params, "interval": "ONE_DAY", "fromdate": "2026-10-12 00:00", "todate": "2026-10-23 23:59"}
resp_1d = shared_rate_limiter.execute_with_backoff("getCandleData", client.getCandleData, params_1d)
bars_1d = resp_1d.get("data") or []
df_1d = pd.DataFrame(bars_1d, columns=["timestamp", "open", "high", "low", "close", "volume"])
df_1d["dt"] = pd.to_datetime(df_1d["timestamp"])
df_1d["date"] = df_1d["dt"].dt.date
daily_map = dict(zip(df_1d["date"], df_1d["close"]))

print("\n--- DAILY VS INTRADAY CLOSE COMPARISON ---")
print(f"{'Date':<12} {'1m Last Time':<14} {'1m Last Close':<14} {'15m Last Close':<14} {'Daily Close':<14} {'Diff (1m - Daily)':<18}")
for d in sorted(df["date"].unique()):
    sub_1m = df[df["date"] == d]
    sub_15m = df_15m[df_15m["date"] == d]
    last_1m_row = sub_1m.iloc[-1]
    last_15m_close = sub_15m.iloc[-1]["close"] if len(sub_15m) > 0 else float("nan")
    d_close = daily_map.get(d, float("nan"))
    diff = last_1m_row["close"] - d_close
    print(f"{str(d):<12} {last_1m_row['time_str']:<14} {last_1m_row['close']:<14.2f} {last_15m_close:<14.2f} {d_close:<14.2f} {diff:<18.2f}")

