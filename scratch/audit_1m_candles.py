import os
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
import pyotp
from SmartApi import SmartConnect
import pandas as pd

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
import time

def call_candle_with_backoff(params):
    backoff = 2.0
    while True:
        try:
            time.sleep(1.0)
            return client.getCandleData(params)
        except Exception as e:
            if "Access denied because of exceeding access rate" in str(e) or "exceeding rate limit" in str(e) or "exceeding access rate" in str(e):
                print(f"Rate limited. Sleeping {backoff}s...")
                time.sleep(backoff)
                backoff = min(backoff * 2.0, 60.0)
            else:
                raise

resp = call_candle_with_backoff(params)
bars = resp.get("data") or []
print(f"Total rows returned: {len(bars)}")

df = pd.DataFrame(bars, columns=["timestamp", "open", "high", "low", "close", "volume"])
df["dt"] = pd.to_datetime(df["timestamp"])
df["date"] = df["dt"].dt.date
df["time"] = df["dt"].dt.time

# Check sessions
sessions = df["date"].unique()
print(f"Unique trading dates ({len(sessions)}): {sorted(list(sessions))}")
for d in sorted(sessions):
    sub = df[df["date"] == d]
    print(f"  {d}: {len(sub)} rows, earliest={sub['time'].min()}, latest={sub['time'].max()}")

# Check duplicates
duplicates = df[df.duplicated(subset=["timestamp"], keep=False)]
print(f"Duplicate timestamp count: {len(duplicates)}")

# Check off-session
t_start = datetime.strptime("09:15", "%H:%M").time()
t_end = datetime.strptime("15:29", "%H:%M").time()
off_session = df[(df["time"] < t_start) | (df["time"] > t_end)]
print(f"Off-session bars (before 09:15 or after 15:29): {len(off_session)}")
if len(off_session) > 0:
    print(off_session[["timestamp", "open", "close"]].head(10))

# Expected sessions x 375
# Between 2026-10-12 (Monday) and 2026-10-23 (Friday) is exactly 10 weekdays.
# Were there any holidays?
print(f"Expected 10 sessions x 375 = 3750 bars.")
print(f"Actual returned: {len(df)} bars across {len(sessions)} sessions.")
print(f"Difference: 3750 - {len(df)} = {3750 - len(df)} missing bars.")
