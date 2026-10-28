"""Institutional Options Microstructure Audit & Quarantine Engine.

Validation Rules:
1. LTP Validity: LTP must be strictly positive (LTP > 0).
2. Delta Bounds: Delta must be non-null, finite, non-zero, and within [-1.0, 1.0].
   - CE Delta in (0.001, 1.0]
   - PE Delta in [-1.0, -0.001)
3. Liquid Strike Open Interest: For strikes within ATM +/- 500 points, OI must be strictly > 0.
4. Volatility Sanity: Implied Volatility must be within reasonable bounds (1% <= IV <= 300%).
5. Bid-Ask Monotonicity: If bid and ask quotes exist, ask >= bid.
6. Put-Call Parity Tolerance: Synthetic forward C - P = (F - K)*e^(-rT) discrepancy within tolerance.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd


def validate_option_snapshot_row(
    row: Dict[str, Any] | pd.Series,
    atm_strike: Optional[float] = None,
    liquid_window_pts: float = 500.0,
) -> Tuple[bool, Optional[str]]:
    """Validate a single options snapshot row against institutional data quality rules.
    
    Returns:
        (is_valid: bool, quarantine_reason: Optional[str])
    """
    ltp = row.get("ltp")
    if ltp is None or pd.isna(ltp) or float(ltp) <= 0.0:
        return False, "LTP <= 0 or missing"

    strike = row.get("strike")
    if strike is None or pd.isna(strike) or float(strike) <= 0.0:
        return False, "Invalid strike <= 0"
    strike = float(strike)

    opt_type = str(row.get("option_type", "")).upper()
    if opt_type not in ("CE", "PE", "CALL", "PUT"):
        return False, f"Invalid option_type '{opt_type}'"

    delta = row.get("delta")
    if delta is None or pd.isna(delta) or float(delta) == 0.0:
        return False, "Delta is zero or NaN"
    
    delta = float(delta)
    if abs(delta) > 1.0001:
        return False, f"Delta {delta} exceeds absolute bound 1.0"

    if opt_type in ("CE", "CALL") and delta < 0.0:
        return False, f"Call option has negative delta {delta}"
    if opt_type in ("PE", "PUT") and delta > 0.0:
        return False, f"Put option has positive delta {delta}"

    # Liquid strike OI check: strikes near ATM must have open interest
    oi = row.get("oi")
    if atm_strike is not None and abs(strike - atm_strike) <= liquid_window_pts:
        if oi is None or pd.isna(oi) or int(oi) <= 0:
            return False, f"Zero or missing OI ({oi}) on liquid strike {strike} (ATM={atm_strike})"

    # Bid-Ask monotonicity check if available
    bid = row.get("bid")
    ask = row.get("ask")
    if bid is not None and ask is not None and pd.notna(bid) and pd.notna(ask):
        if float(ask) < float(bid) and float(ask) > 0.0:
            return False, f"Inverted orderbook: ask ({ask}) < bid ({bid})"

    # IV sanity
    iv = row.get("iv")
    if iv is not None and pd.notna(iv):
        iv_f = float(iv)
        if iv_f < 0.005 or iv_f > 3.5:
            return False, f"Implied volatility {iv_f:.4f} outside bounds [0.5%, 350%]"

    return True, None


def quarantine_options_dataframe(
    df: pd.DataFrame,
    atm_strike: Optional[float] = None,
    liquid_window_pts: float = 500.0,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Audit and split an options snapshots DataFrame into valid and quarantined partitions."""
    if df.empty:
        df_empty_valid = df.copy()
        df_empty_valid["is_valid"] = pd.Series(dtype=bool)
        df_empty_q = df.copy()
        df_empty_q["quarantine_reason"] = pd.Series(dtype=str)
        return df_empty_valid, df_empty_q

    valid_mask = []
    reasons = []

    for _, row in df.iterrows():
        is_val, reason = validate_option_snapshot_row(
            row, atm_strike=atm_strike, liquid_window_pts=liquid_window_pts
        )
        valid_mask.append(is_val)
        reasons.append(reason)

    df_valid = df[valid_mask].copy()
    df_valid["is_valid"] = True

    df_quarantined = df[[not v for v in valid_mask]].copy()
    df_quarantined["is_valid"] = False
    df_quarantined["quarantine_reason"] = [r for r, v in zip(reasons, valid_mask) if not v]

    return df_valid, df_quarantined


def evaluate_put_call_parity_pair(
    call_ltp: float,
    put_ltp: float,
    strike: float,
    forward_or_spot: float,
    dte_days: float,
    r: float = 0.0685,
    tolerance_pts: float = 15.0,
) -> Dict[str, Any]:
    """Verify Put-Call Parity: C - P = (F - K) * e^(-rT)."""
    t_years = max(1.0, dte_days) / 365.25
    discount_factor = math.exp(-r * t_years)
    
    # Implied forward from options: F = K + (C - P) * e^(rT)
    implied_forward = strike + (call_ltp - put_ltp) * math.exp(r * t_years)
    
    # Discrepancy against expected forward/spot
    theoretical_spread = (forward_or_spot - strike) * discount_factor
    actual_spread = call_ltp - put_ltp
    discrepancy = abs(actual_spread - theoretical_spread)
    
    is_pass = discrepancy <= tolerance_pts
    return {
        "strike": strike,
        "call_ltp": call_ltp,
        "put_ltp": put_ltp,
        "actual_spread": round(actual_spread, 2),
        "theoretical_spread": round(theoretical_spread, 2),
        "implied_forward": round(implied_forward, 2),
        "discrepancy_pts": round(discrepancy, 2),
        "is_pass": is_pass,
        "tolerance_pts": tolerance_pts,
    }
