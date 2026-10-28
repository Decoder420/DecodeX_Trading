"""Compute detailed per-interval audit table and aggregated intraday vs daily OHLC comparison."""

import os
from datetime import datetime
import pandas as pd
from dotenv import load_dotenv
import pyotp
from SmartApi import SmartConnect

load_dotenv()
client = SmartConnect(api_key=os.getenv("ANGEL_API_KEY"))
orig_rh = client.requestHeaders
client.requestHeaders = lambda: {**orig_rh(), "Content-Type": "application/json"}
totp = pyotp.TOTP(os.getenv("ANGEL_TOTP_SECRET")).now()
client.generateSession(os.getenv("ANGEL_CLIENT_ID"), os.getenv("ANGEL_MPIN"), totp)

from data.rate_limiter import shared_rate_limiter

dates = [
    "2026-10-12", "2026-10-13", "2026-10-14", "2026-10-15",
    "2026-10-16", "2026-10-19", "2026-10-21", "2026-10-22", "2026-10-23"
]

def fetch_bars(interval, from_d, to_d):
    params = {
        "exchange": "NSE",
        "symboltoken": "99926000",
        "interval": interval,
        "fromdate": from_d,
        "todate": to_d,
    }
    res = shared_rate_limiter.execute_with_backoff("getCandleData", client.getCandleData, params)
    data = res.get("data") or []
    df = pd.DataFrame(data, columns=["timestamp", "open", "high", "low", "close", "volume"])
    if not df.empty:
        df["dt"] = pd.to_datetime(df["timestamp"])
        df["date"] = df["dt"].dt.strftime("%Y-%m-%d")
        df["time"] = df["dt"].dt.strftime("%H:%M")
    return df

print("Fetching 1m, 5m, 15m, and 1d bars...")
df_1m = fetch_bars("ONE_MINUTE", "2026-10-12 09:15", "2026-10-23 15:30")
df_5m = fetch_bars("FIVE_MINUTE", "2026-10-12 09:15", "2026-10-23 15:30")
df_15m = fetch_bars("FIFTEEN_MINUTE", "2026-10-12 09:15", "2026-10-23 15:30")
df_1d = fetch_bars("ONE_DAY", "2026-10-12 00:00", "2026-10-23 23:59")

# 1. Per-interval summary table
print("\n" + "=" * 90)
print("TABLE 1: PER-INTERVAL AUDIT SUMMARY (1m, 5m, 15m)")
print("=" * 90)
print(f"{'Date':<12} | {'1m First':<8} {'1m Last':<8} {'1m N':<5} {'1m >=15:15':<10} | {'5m First':<8} {'5m Last':<8} {'5m N':<5} {'5m >=15:15':<10} | {'15m First':<8} {'15m Last':<8} {'15m N':<5} {'15m >=15:15':<10}")
print("-" * 135)

for d in dates:
    sub_1 = df_1m[df_1m["date"] == d]
    sub_5 = df_5m[df_5m["date"] == d]
    sub_15 = df_15m[df_15m["date"] == d]
    
    c1_ge = (sub_1["time"] >= "15:15").sum()
    c5_ge = (sub_5["time"] >= "15:15").sum()
    c15_ge = (sub_15["time"] >= "15:15").sum()

    f1, l1, n1 = sub_1["time"].iloc[0], sub_1["time"].iloc[-1], len(sub_1)
    f5, l5, n5 = sub_5["time"].iloc[0], sub_5["time"].iloc[-1], len(sub_5)
    f15, l15, n15 = sub_15["time"].iloc[0], sub_15["time"].iloc[-1], len(sub_15)

    print(f"{d:<12} | {f1:<8} {l1:<8} {n1:<5} {c1_ge:<10} | {f5:<8} {l5:<8} {n5:<5} {c5_ge:<10} | {f15:<8} {l15:<8} {n15:<5} {c15_ge:<10}")

# 2. Daily vs Aggregated Intraday OHLC comparison
print("\n" + "=" * 90)
print("TABLE 2: AGGREGATED INTRADAY 1m vs DAILY BAR OHLC COMPARISON")
print("=" * 90)
print(f"{'Date':<12} | {'Field':<6} | {'Aggregated 1m':<14} | {'Daily Bar':<14} | {'Diff (Agg - Daily)':<18}")
print("-" * 75)

daily_dict = {r["date"]: r for _, r in df_1d.iterrows()}

for d in dates:
    sub_1 = df_1m[df_1m["date"] == d]
    day_row = daily_dict.get(d)
    if day_row is None:
        continue
    
    agg_open = sub_1.iloc[0]["open"]
    agg_high = sub_1["high"].max()
    agg_low = sub_1["low"].min()
    agg_close = sub_1.iloc[-1]["close"]

    d_open = day_row["open"]
    d_high = day_row["high"]
    d_low = day_row["low"]
    d_close = day_row["close"]

    print(f"{d:<12} | Open   | {agg_open:<14.2f} | {d_open:<14.2f} | {agg_open - d_open:<18.2f}")
    print(f"{'':<12} | High   | {agg_high:<14.2f} | {d_high:<14.2f} | {agg_high - d_high:<18.2f}")
    print(f"{'':<12} | Low    | {agg_low:<14.2f} | {d_low:<14.2f} | {agg_low - d_low:<18.2f}")
    print(f"{'':<12} | Close  | {agg_close:<14.2f} | {d_close:<14.2f} | {agg_close - d_close:<18.2f}")
    print("-" * 75)
