import os
import sys
import json
from pathlib import Path
from dotenv import load_dotenv
import pyotp
from SmartApi import SmartConnect

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

api_key = os.getenv("ANGEL_API_KEY")
client_id = os.getenv("ANGEL_CLIENT_ID")
mpin = os.getenv("ANGEL_MPIN")
totp_secret = os.getenv("ANGEL_TOTP_SECRET")

client = SmartConnect(api_key=api_key)
orig_rh = client.requestHeaders
client.requestHeaders = lambda: {**orig_rh(), "Content-Type": "application/json"}
totp = pyotp.TOTP(totp_secret).now()
sess = client.generateSession(client_id, mpin, totp)
if not sess.get("status"):
    print("Session failed:", sess)
    sys.exit(1)

print("--- TESTING SENSEX OPTION GREEKS (BFO) ---")
try:
    with open("data/cache/angel_scrip_master.json") as f:
        scrips = json.load(f)
    bfo_opts = [s for s in scrips if s.get("exch_seg") == "BFO" and s.get("name") == "SENSEX" and s.get("instrumenttype") == "OPTIDX"]
    print(f"Total SENSEX BFO options in master: {len(bfo_opts)}")
    expiries = sorted(list(set(s.get("expiry") for s in bfo_opts if s.get("expiry"))))
    print(f"SENSEX BFO Option expiries: {expiries[:5]}")
    nearest_exp = "29OCT2026"
    print(f"Querying optionGreek for SENSEX expiry: {nearest_exp}")
    
    greeks_resp = client.optionGreek({"name": "SENSEX", "expirydate": nearest_exp})
    g_data = greeks_resp.get("data") or []
    status = greeks_resp.get("status")
    print(f"optionGreek BFO status: {status}, returned {len(g_data)} strikes")
    if g_data:
        s0 = g_data[0]
        print(f"Sample strike: {s0.get('strikePrice')} {s0.get('optionType')}, Delta: {s0.get('delta')}, IV: {s0.get('impliedVolatility')}, Vol: {s0.get('tradeVolume')}")
except Exception as e:
    print(f"optionGreek BFO error: {e}")

print("\n--- TESTING SENSEX QUOTE (BFO) ---")
try:
    sample_bfo_tokens = [s["token"] for s in bfo_opts[:5]]
    print(f"Sample BFO tokens: {sample_bfo_tokens}")
    q_resp = client.getMarketData("FULL", {"BFO": sample_bfo_tokens})
    f_data = q_resp.get("data", {}).get("fetched") or []
    q_status = q_resp.get("status")
    print(f"getMarketData FULL BFO status: {q_status}, fetched {len(f_data)} tokens")
    if f_data:
        q0 = f_data[0]
        print(f"Sample quote token: {q0.get('symbolToken')}, symbol: {q0.get('tradingSymbol')}, ltp: {q0.get('ltp')}, depth bids: {len(q0.get('depth', {}).get('buy', []))}")
except Exception as e:
    print(f"quote BFO error: {e}")
