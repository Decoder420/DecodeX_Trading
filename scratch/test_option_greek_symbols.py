import os
from pathlib import Path
from dotenv import load_dotenv
import pyotp
from SmartApi import SmartConnect

load_dotenv()
client = SmartConnect(api_key=os.getenv("ANGEL_API_KEY"))
orig_rh = client.requestHeaders
client.requestHeaders = lambda: {**orig_rh(), "Content-Type": "application/json"}
totp = pyotp.TOTP(os.getenv("ANGEL_TOTP_SECRET")).now()
client.generateSession(os.getenv("ANGEL_CLIENT_ID"), os.getenv("ANGEL_MPIN"), totp)

symbols_to_test = [
    ("NIFTY", "27OCT2026"),
    ("BANKNIFTY", "27OCT2026"),
    ("SENSEX", "29OCT2026"),
    ("BSESENSEX", "29OCT2026"),
    ("SENSEX50", "29OCT2026"),
    ("BFO:SENSEX", "29OCT2026"),
]

import time

for sym, exp in symbols_to_test:
    time.sleep(2.0)
    try:
        res = client.optionGreek({"name": sym, "expirydate": exp})
        status = res.get("status")
        msg = res.get("message")
        cnt = len(res.get("data") or [])
        print(f"optionGreek name={sym:10} expiry={exp}: status={status}, msg={msg}, strikes={cnt}")
    except Exception as e:
        print(f"optionGreek name={sym:10} expiry={exp}: ERROR {e}")
