"""Live Options Chain & Greeks Cockpit Provider.

Resolves active contracts, merges Open Interest with Delta, Gamma, Theta, Vega,
and computes institutional options microstructure metrics (PCR, Max Pain, GEX).
"""

from __future__ import annotations

import json
import logging
import math
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import duckdb
import numpy as np
import pandas as pd

from config.loader import config_manager
from recorder.metrics import Black76, calculate_derived_metrics

logger = logging.getLogger("OptionsChainProvider")

ROOT_DIR = Path(__file__).resolve().parent.parent
SCRIP_CACHE_PATH = ROOT_DIR / "data" / "cache" / "angel_scrip_master.json"
DEFAULT_LIVE_DIR = ROOT_DIR / "data" / "live"

STRIKE_STEPS = {
    "NIFTY": 50.0,
    "BANKNIFTY": 100.0,
    "SENSEX": 100.0,
}

LOT_SIZES = {
    "NIFTY": 65,
    "BANKNIFTY": 30,
    "SENSEX": 20,
}


def get_available_expiries(instrument: str) -> List[Tuple[str, str]]:
    """Return available upcoming expiries with labels driven strictly by config expiry rules."""
    today = datetime.now().date()
    expiries_found: set[Tuple[date, str]] = set()

    if SCRIP_CACHE_PATH.exists():
        try:
            with open(SCRIP_CACHE_PATH, "r", encoding="utf-8") as f:
                scrips = json.load(f)
            for s in scrips:
                if s.get("name") == instrument and s.get("instrumenttype") == "OPTIDX":
                    exp = s.get("expiry")
                    if exp:
                        try:
                            dt = datetime.strptime(exp, "%d%b%Y").date()
                            if dt >= today:
                                expiries_found.add((dt, exp))
                        except Exception:
                            pass
        except Exception as e:
            logger.warning("Error reading scrip master for expiries: %s", e)

    if not expiries_found:
        if instrument == "NIFTY":
            return [("03NOV2026", "03NOV2026 — Near Weekly (6d)"), ("23NOV2026", "23NOV2026 — Monthly Expiry (26d)")]
        elif instrument == "BANKNIFTY":
            return [("23NOV2026", "23NOV2026 — Monthly Expiry (26d)"), ("29DEC2026", "29DEC2026 — Monthly Expiry (62d)")]
        elif instrument == "SENSEX":
            return [("29OCT2026", "29OCT2026 — Weekly (1d)"), ("05NOV2026", "05NOV2026 — Weekly (8d)")]

    sorted_exps = sorted(list(expiries_found), key=lambda x: x[0])
    result: List[Tuple[str, str]] = []

    for dt, exp_str in sorted_exps[:6]:
        days_left = (dt - today).days

        # Expiry rule resolution via ConfigManager
        rule = config_manager.get_expiry_rule(instrument, dt)
        target_weekday = config_manager._day_name_to_weekday(rule.get("day_of_week", "Tuesday"))
        candidates = config_manager._get_candidate_expiry_dates_in_month(dt.year, dt.month, target_weekday, "weekly")
        resolved_cands = [config_manager.resolve_expiry_date(c) for c in candidates]
        is_monthly = (dt == resolved_cands[-1]) if resolved_cands else False

        if days_left == 0:
            type_tag = "TODAY'S EXPIRY (0d)"
        elif days_left == 1:
            type_tag = "EXPIRY TOMORROW (1d)"
        elif is_monthly:
            type_tag = f"Monthly Expiry ({days_left}d)"
        elif days_left <= 7:
            type_tag = f"Near Weekly ({days_left}d)"
        else:
            type_tag = f"Weekly Expiry ({days_left}d)"

        display = f"{exp_str} — {type_tag}"
        result.append((exp_str, display))

    return result


def load_options_chain_data(
    instrument: str,
    expiry_str: str,
    spot_price: float,
    window_strikes: int = 7,
) -> Dict[str, Any]:
    """Retrieve full options chain, Greeks (Delta, Gamma, Theta, Vega), OI, and Max Pain."""
    now = datetime.now()
    step = STRIKE_STEPS.get(instrument, 50.0)
    lot_size = LOT_SIZES.get(instrument, 65)
    atm_strike = round(spot_price / step) * step

    # Target strikes: ATM +/- window_strikes
    target_strikes = [round(atm_strike + i * step, 2) for i in range(-window_strikes, window_strikes + 1)]
    target_strikes_set = set(target_strikes)

    # Parse expiry date
    try:
        exp_date = datetime.strptime(expiry_str, "%d%b%Y").date()
    except Exception:
        exp_date = now.date()

    exp_datetime = datetime.combine(exp_date, datetime.min.time()).replace(hour=15, minute=30)
    diff_hours = max((exp_datetime - now).total_seconds() / 3600.0, 0.5)
    T_years = diff_hours / (365.0 * 24.0)
    r = 0.065  # 6.5% risk-free rate

    # Check live DuckDB database for today or most recent session with options_snapshots
    session_date = now.strftime("%Y_%m_%d")
    target_dbs = [ROOT_DIR / "data" / "live" / f"live_{session_date}.duckdb"]
    live_files = sorted(list((ROOT_DIR / "data" / "live").glob("live_*.duckdb")), reverse=True)
    for lf in live_files:
        if lf not in target_dbs:
            target_dbs.append(lf)

    db_path = None
    for p in target_dbs:
        if p.exists():
            try:
                con_chk = duckdb.connect(str(p), read_only=True)
                tables = [r[0] for r in con_chk.execute("SHOW TABLES").fetchall()]
                con_chk.close()
                if "options_snapshots" in tables:
                    db_path = p
                    break
            except Exception:
                pass
    if db_path is None:
        db_path = target_dbs[0]
    
    rows_by_strike: Dict[float, Dict[str, Any]] = {k: {"CE": None, "PE": None} for k in target_strikes}
    all_chain_rows: List[Dict[str, Any]] = []
    latest_ts = None
    has_live_ticks = False

    def _to_naive_ist(val: Any) -> Optional[pd.Timestamp]:
        if val is None or pd.isna(val):
            return None
        try:
            ts = pd.to_datetime(val)
            if ts.tz is not None:
                ts = ts.tz_convert("Asia/Kolkata").tz_localize(None)
            return ts
        except Exception:
            return None

    # 1. Check in-memory live state JSON for active options streaming
    state_path = DEFAULT_LIVE_DIR / "live_state.json"
    live_quotes: Dict[str, Any] = {}
    if state_path.exists():
        try:
            with open(state_path, "r", encoding="utf-8") as f:
                state_data = json.load(f)
            if state_data.get("has_live"):
                live_quotes = state_data.get("latest_option_quotes", {})
                raw_opt_ts = state_data.get("last_option_tick_time") or state_data.get("timestamp")
                if raw_opt_ts:
                    parsed_state_ts = _to_naive_ist(raw_opt_ts)
                    if parsed_state_ts is not None:
                        latest_ts = parsed_state_ts
                        has_live_ticks = True
        except Exception as e:
            logger.debug("Failed reading live_state.json for options: %s", e)

    if db_path.exists():
        try:
            conn = duckdb.connect(str(db_path), read_only=True)
            exp_date_str = exp_date.strftime("%Y-%m-%d")
            query = f"""
                SELECT strike, option_type, token, ltp, oi, volume, iv, delta, gamma, theta, vega, greeks_source, timestamp
                FROM options_snapshots
                WHERE underlying = '{instrument}'
                  AND contract_expiry = '{exp_date_str}'
                  AND (is_valid IS NULL OR is_valid = TRUE)
                ORDER BY timestamp DESC
            """
            df_snap = conn.execute(query).df()

            # Check if live_ticks table has recent OPTIDX ticks
            tables = [r[0] for r in conn.execute("SHOW TABLES").fetchall()]
            df_ticks = pd.DataFrame()
            if "live_ticks" in tables:
                df_ticks = conn.execute("""
                    SELECT token, symbol, ltp, volume, ltq, exchange_timestamp as timestamp
                    FROM live_ticks
                    WHERE instrument_type = 'OPTIDX'
                    ORDER BY exchange_timestamp DESC
                """).df()
                if not df_ticks.empty:
                    has_live_ticks = True
                    tick_ts = _to_naive_ist(df_ticks["timestamp"].max())
                    if tick_ts is not None and (latest_ts is None or tick_ts > latest_ts):
                        latest_ts = tick_ts
                else:
                    # Check recent ticks from live feed for underlying
                    u_row = conn.execute(f"""
                        SELECT max(exchange_timestamp) FROM live_ticks
                        WHERE symbol = '{instrument}'
                    """).fetchone()
                    if u_row and u_row[0] is not None:
                        u_ts = _to_naive_ist(u_row[0])
                        if u_ts is not None and (latest_ts is None or u_ts > latest_ts):
                            latest_ts = u_ts
            conn.close()

            if not df_snap.empty:
                snap_ts = _to_naive_ist(df_snap["timestamp"].max())
                if latest_ts is None and snap_ts is not None:
                    latest_ts = snap_ts
                # Deduplicate to keep latest quote per strike and option_type
                df_latest = df_snap.drop_duplicates(subset=["strike", "option_type"], keep="first")
                for _, r_data in df_latest.iterrows():
                    k = round(float(r_data["strike"]), 2)
                    otype = str(r_data["option_type"]).upper()
                    all_chain_rows.append(r_data.to_dict())
                    if k in rows_by_strike and otype in ["CE", "PE"]:
                        rows_by_strike[k][otype] = r_data.to_dict()

            if not df_ticks.empty:
                df_ticks_latest = df_ticks.drop_duplicates(subset=["token"], keep="first")
                token_dict = df_ticks_latest.set_index("token").to_dict(orient="index")
                for k in target_strikes:
                    for otype in ["CE", "PE"]:
                        row = rows_by_strike[k][otype]
                        if row and str(row.get("token")) in token_dict:
                            t_data = token_dict[str(row["token"])]
                            if float(t_data.get("ltp", 0.0)) > 0:
                                row["ltp"] = float(t_data["ltp"])
                                row["volume"] = int(t_data.get("volume", row.get("volume", 0)))
                                row["greeks_source"] = "live_ws_tick"

            if live_quotes:
                has_live_ticks = True
                for k in target_strikes:
                    for otype in ["CE", "PE"]:
                        row = rows_by_strike[k][otype]
                        if row:
                            t_str = str(row.get("token"))
                            if t_str in live_quotes:
                                q_data = live_quotes[t_str]
                                if float(q_data.get("ltp", 0.0)) > 0:
                                    row["ltp"] = float(q_data["ltp"])
                                    row["volume"] = int(q_data.get("volume", row.get("volume", 0)))
                                    if "oi" in q_data and int(q_data["oi"]) > 0:
                                        row["oi"] = int(q_data["oi"])
                                    row["greeks_source"] = "live_ws_tick"
        except Exception as e:
            logger.warning("Error reading options data from DuckDB: %s", e)

    # Populate and validate strikes using actual market prices and inverted IV
    real_strikes_count = 0
    for k in target_strikes:
        for otype in ["CE", "PE"]:
            existing = rows_by_strike[k][otype]
            has_real_quote = (
                existing is not None
                and float(existing.get("ltp", 0.0)) > 0.0
                and int(existing.get("oi", 0)) > 0
            )

            if has_real_quote:
                real_ltp = float(existing["ltp"])
                real_oi = int(existing["oi"])
                real_vol = int(existing.get("volume", 0))

                # Check if existing broker Greeks are valid
                raw_iv = float(existing.get("iv", 0.0))
                raw_delta = float(existing.get("delta", 0.0))
                src = str(existing.get("greeks_source", "broker_optionGreek"))

                if raw_iv > 0.0 and raw_delta != 0.0 and src == "broker_optionGreek":
                    iv = raw_iv if raw_iv > 1.0 else round(raw_iv * 100.0, 2)
                    delta = raw_delta
                    gamma = float(existing.get("gamma", 0.0))
                    theta = float(existing.get("theta", 0.0))
                    vega = float(existing.get("vega", 0.0))
                    g_source = "broker_optionGreek"
                else:
                    # Invert Black-76 on the ACTUAL option market LTP
                    computed_iv = Black76.implied_volatility(
                        market_price=real_ltp,
                        F=spot_price,
                        K=k,
                        T=T_years,
                        r=r,
                        option_type=otype,
                    )
                    if computed_iv > 0.001:
                        b76_g = Black76.greeks(F=spot_price, K=k, T=T_years, r=r, sigma=computed_iv, option_type=otype)
                        iv = round(computed_iv * 100.0, 2)
                        delta = b76_g["delta"]
                        gamma = b76_g["gamma"]
                        theta = b76_g["theta"]
                        vega = b76_g["vega"]
                        g_source = "market_iv_inversion"
                    else:
                        iv = 16.0
                        delta = 0.50 if otype == "CE" else -0.50
                        gamma = 0.0008
                        theta = -15.0
                        vega = 10.0
                        g_source = "boundary_fallback"

                rows_by_strike[k][otype] = {
                    "strike": k,
                    "option_type": otype,
                    "ltp": real_ltp,
                    "oi": real_oi,
                    "volume": real_vol,
                    "iv": iv,
                    "delta": delta,
                    "gamma": gamma,
                    "theta": theta,
                    "vega": vega,
                    "greeks_source": g_source,
                    "is_real": True,
                }
                real_strikes_count += 1
            else:
                # Fallback to Black-76 theoretical pricing for missing strikes
                moneyness = abs(spot_price - k) / spot_price
                iv_est = max(0.12, min(0.35, 0.165 + moneyness * 0.40))
                b76_price = Black76.price(F=spot_price, K=k, T=T_years, r=r, sigma=iv_est, option_type=otype)
                greeks = Black76.greeks(F=spot_price, K=k, T=T_years, r=r, sigma=iv_est, option_type=otype)
                dist_factor = max(0.05, 1.0 - (abs(k - spot_price) / (step * 8)))
                oi_synth = int(dist_factor * 4500000)

                rows_by_strike[k][otype] = {
                    "strike": k,
                    "option_type": otype,
                    "ltp": round(b76_price, 2),
                    "oi": oi_synth,
                    "volume": int(oi_synth * 0.75),
                    "iv": round(iv_est * 100.0, 2),
                    "delta": greeks["delta"],
                    "gamma": greeks["gamma"],
                    "theta": greeks["theta"],
                    "vega": greeks["vega"],
                    "greeks_source": "synthetic_model",
                    "is_real": False,
                }

    # Build Matrix DataFrame
    matrix_rows = []
    total_ce_oi = 0
    total_pe_oi = 0

    for k in sorted(target_strikes):
        ce = rows_by_strike[k]["CE"]
        pe = rows_by_strike[k]["PE"]

        ce_oi = ce.get("oi", 0)
        pe_oi = pe.get("oi", 0)
        total_ce_oi += ce_oi
        total_pe_oi += pe_oi

        # Strike annotation
        if k == atm_strike:
            strike_label = f"🟢 ₹{k:,.0f} (ATM)"
        else:
            strike_label = f"₹{k:,.0f}"

        matrix_rows.append({
            "Call Delta (Δ)": f"{ce.get('delta', 0.0):+.3f}",
            "Call Gamma (Γ)": f"{ce.get('gamma', 0.0):.5f}",
            "Call Theta (Θ/d)": f"{ce.get('theta', 0.0):.2f}",
            "Call IV%": f"{ce.get('iv', 16.0):.1f}%",
            "Call OI (Lakhs)": f"{ce_oi / 100000.0:.2f}L",
            "Call LTP (₹)": f"₹{ce.get('ltp', 0.0):,.2f}",
            "STRIKE": strike_label,
            "Put LTP (₹)": f"₹{pe.get('ltp', 0.0):,.2f}",
            "Put OI (Lakhs)": f"{pe_oi / 100000.0:.2f}L",
            "Put IV%": f"{pe.get('iv', 16.0):.1f}%",
            "Put Delta (Δ)": f"{pe.get('delta', 0.0):+.3f}",
            "Put Gamma (Γ)": f"{pe.get('gamma', 0.0):.5f}",
            "Put Theta (Θ/d)": f"{pe.get('theta', 0.0):.2f}",
            "Greeks Source": ce.get("greeks_source", pe.get("greeks_source", "broker_optionGreek")),
            "_raw_strike": k,
        })

    df_matrix = pd.DataFrame(matrix_rows)

    # Derived summary metrics from real OI surface
    pcr_oi = round(total_pe_oi / max(total_ce_oi, 1), 3)

    # Max Pain calculation across all strikes
    strikes_arr = np.array(sorted(target_strikes))
    total_losses = []
    for s in strikes_arr:
        ce_loss = sum(max(0.0, s - k) * rows_by_strike[k]["CE"].get("oi", 0) for k in strikes_arr)
        pe_loss = sum(max(0.0, k - s) * rows_by_strike[k]["PE"].get("oi", 0) for k in strikes_arr)
        total_losses.append(ce_loss + pe_loss)
    max_pain = float(strikes_arr[np.argmin(total_losses)]) if len(strikes_arr) > 0 else atm_strike

    # ATM Strike Specific Greeks
    atm_ce = rows_by_strike[atm_strike]["CE"]
    atm_pe = rows_by_strike[atm_strike]["PE"]

    atm_call_delta = float(atm_ce.get("delta", 0.50))
    atm_put_delta = float(atm_pe.get("delta", -0.50))
    net_atm_delta = round(atm_call_delta + atm_put_delta, 3)

    atm_call_theta = float(atm_ce.get("theta", -16.5))
    atm_put_theta = float(atm_pe.get("theta", -15.5))
    straddle_theta_day = round(atm_call_theta + atm_put_theta, 2)
    daily_theta_cost_inr = round(abs(straddle_theta_day) * lot_size, 2)

    atm_gamma = float(atm_ce.get("gamma", 0.0008))
    # Gamma exposure (GEX) estimate in Cr
    net_gex_crores = round(((total_ce_oi - total_pe_oi) * atm_gamma * (spot_price ** 2) * 0.01) / 1e7, 2)

    # Telemetry and Feed Transparency Metadata
    total_contracts = len(target_strikes) * 2
    is_synthetic = (real_strikes_count == 0)
    if real_strikes_count == total_contracts:
        feed_type = "Live NFO WebSocket Feed" if has_live_ticks else "Live NFO Exchange Feed (Real Market Snapshots)"
        feed_badge_color = "#00E676"
    elif real_strikes_count > 0:
        feed_type = f"Hybrid Feed ({real_strikes_count}/{total_contracts} Live Strikes)"
        feed_badge_color = "#FFB300"
    else:
        feed_type = "Estimated / Synthetic Model"
        feed_badge_color = "#FF5252"

    if latest_ts is not None:
        try:
            last_opt_tick_str = latest_ts.strftime("%Y-%m-%d %H:%M:%S IST")
        except Exception:
            last_opt_tick_str = str(latest_ts)
    else:
        last_opt_tick_str = "N/A (Synthetic Baseline)"

    return {
        "matrix_df": df_matrix,
        "pcr_oi": pcr_oi,
        "max_pain": max_pain,
        "atm_strike": atm_strike,
        "atm_call_delta": atm_call_delta,
        "atm_put_delta": atm_put_delta,
        "net_atm_delta": net_atm_delta,
        "atm_call_theta": atm_call_theta,
        "atm_put_theta": atm_put_theta,
        "straddle_theta_day": straddle_theta_day,
        "daily_theta_cost_inr": daily_theta_cost_inr,
        "atm_gamma": atm_gamma,
        "net_gex_crores": net_gex_crores,
        "atm_call_ltp": float(atm_ce.get("ltp", 0.0)),
        "atm_put_ltp": float(atm_pe.get("ltp", 0.0)),
        "total_ce_oi": total_ce_oi,
        "total_pe_oi": total_pe_oi,
        "expiry_str": expiry_str,
        "feed_type": feed_type,
        "feed_badge_color": feed_badge_color,
        "last_option_tick_time": last_opt_tick_str,
        "is_synthetic": is_synthetic,
        "real_strikes_count": real_strikes_count,
        "total_strikes_count": total_contracts,
    }
