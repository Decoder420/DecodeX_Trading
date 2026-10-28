import os
import math
from datetime import datetime
import numpy as np
from scipy.stats import norm
import pyotp
from SmartApi import SmartConnect
from dotenv import load_dotenv

load_dotenv()
client = SmartConnect(api_key=os.getenv("ANGEL_API_KEY"))
orig_rh = client.requestHeaders
client.requestHeaders = lambda: {**orig_rh(), "Content-Type": "application/json"}
totp = pyotp.TOTP(os.getenv("ANGEL_TOTP_SECRET")).now()
client.generateSession(os.getenv("ANGEL_CLIENT_ID"), os.getenv("ANGEL_MPIN"), totp)

# Fetch NIFTY Option Greeks from Angel One
res = client.optionGreek({"name": "NIFTY", "expirydate": "27OCT2026"})
greeks_list = res.get("data") or []
print(f"Fetched {len(greeks_list)} NIFTY strikes from Angel One optionGreek")

# Get Spot or Futures LTP
spot_res = client.getMarketData("LTP", {"NSE": ["99926000"]})
spot_ltp = spot_res["data"]["fetched"][0]["ltp"]
print(f"NIFTY Spot LTP: {spot_ltp}")

# Expiry date: 2026-10-27 15:30 IST. Current time:
now = datetime.now()
exp_dt = datetime(2026, 10, 27, 15, 30)
diff_hours = (exp_dt - now).total_seconds() / 3600.0
T = max(diff_hours / (365.0 * 24.0), 1e-5)
r = 0.065 # 6.5% RBI T-bill rate

def black76_greeks(F, K, T, r, sigma, opt_type):
    if sigma <= 0 or T <= 0 or F <= 0 or K <= 0:
        return {"delta": 0, "gamma": 0, "theta": 0, "vega": 0}
    d1 = (math.log(F / K) + 0.5 * sigma * sigma * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    disc = math.exp(-r * T)
    pdf_d1 = norm.pdf(d1)
    
    if opt_type.upper() == "CE":
        delta = disc * norm.cdf(d1)
    else:
        delta = disc * (norm.cdf(d1) - 1.0)
    
    gamma = (disc * pdf_d1) / (F * sigma * math.sqrt(T))
    vega = (F * disc * pdf_d1 * math.sqrt(T)) / 100.0 # per 1% IV
    
    if opt_type.upper() == "CE":
        theta = (- (F * disc * sigma * pdf_d1) / (2 * math.sqrt(T)) - r * disc * (F * norm.cdf(d1) - K * norm.cdf(d2))) / 365.0
    else:
        theta = (- (F * disc * sigma * pdf_d1) / (2 * math.sqrt(T)) + r * disc * (K * norm.cdf(-d2) - F * norm.cdf(-d1))) / 365.0
        
    return {"delta": delta, "gamma": gamma, "theta": theta, "vega": vega}

delta_diffs = []
gamma_diffs = []
theta_diffs = []
vega_diffs = []

sample_checks = []

for g in greeks_list:
    k = float(g.get("strikePrice", 0))
    iv = float(g.get("impliedVolatility", 0)) / 100.0
    otype = g.get("optionType", "CE")
    if iv <= 0.01 or iv > 2.0:
        continue
    
    # Angel Greeks
    a_delta = float(g.get("delta", 0))
    a_gamma = float(g.get("gamma", 0))
    a_theta = float(g.get("theta", 0))
    a_vega = float(g.get("vega", 0))
    
    # Black-76 with F = spot_ltp * exp(r * T)
    F = spot_ltp * math.exp(r * T)
    b_greeks = black76_greeks(F, k, T, r, iv, otype)
    
    d_err = abs(b_greeks["delta"] - a_delta)
    g_err = abs(b_greeks["gamma"] - a_gamma)
    
    delta_diffs.append(d_err)
    gamma_diffs.append(g_err)
    theta_diffs.append(abs(b_greeks["theta"] - a_theta))
    vega_diffs.append(abs(b_greeks["vega"] - a_vega))
    
    if abs(k - spot_ltp) < 150:
        sample_checks.append({
            "strike": k, "type": otype,
            "angel_delta": a_delta, "b76_delta": round(b_greeks["delta"], 4),
            "angel_gamma": a_gamma, "b76_gamma": round(b_greeks["gamma"], 6),
            "angel_iv": round(iv * 100, 2)
        })

print("\n--- BLACK-76 VALIDATION VS ANGEL OPTIONGREEK (NIFTY) ---")
print(f"Sample validated ATM strikes: {len(delta_diffs)}")
print(f"Delta Mean Absolute Error (MAE): {np.mean(delta_diffs):.4f}")
print(f"Gamma Mean Absolute Error (MAE): {np.mean(gamma_diffs):.6f}")
print(f"Theta Mean Absolute Error (MAE): {np.mean(theta_diffs):.2f}")
print(f"Vega Mean Absolute Error (MAE):  {np.mean(vega_diffs):.4f}")

print("\nATM Strikes Comparison Sample:")
for s in sample_checks[:5]:
    print(f"  Strike {s['strike']} {s['type']} (IV {s['angel_iv']}%): Angel Delta={s['angel_delta']}, B76 Delta={s['b76_delta']} | Angel Gamma={s['angel_gamma']}, B76 Gamma={s['b76_gamma']}")
