"""Intraday metrics computation: volume differencing, VWAP, Black-76 Greeks, and derived option metrics."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
from scipy.optimize import brentq
from scipy.stats import norm


def compute_bar_volume(
    current_cum_vol: int,
    prev_cum_vol: int,
    contract_changed: bool = False,
) -> int:
    """Compute incremental bar volume from cumulative day volume.
    
    Handles:
    - Normal tick increment: cur - prev
    - Contract rollover / reset: if contract_changed or cur < prev, returns cur
    - Negative volume protection: max(0, diff)
    """
    if contract_changed or prev_cum_vol is None or prev_cum_vol == 0:
        return max(0, int(current_cum_vol))
    
    diff = current_cum_vol - prev_cum_vol
    if diff < 0:
        # Rollover or session reset
        return max(0, int(current_cum_vol))
    return int(diff)


class CumulativeIntradayVWAP:
    """Cumulative Intraday Volume Weighted Average Price tracker.
    
    VWAP = sum(TypicalPrice * IncrementalVolume) / sum(IncrementalVolume)
    TypicalPrice = (High + Low + Close) / 3
    """

    def __init__(self, symbol: str, contract_expiry: Optional[date] = None):
        self.symbol = symbol
        self.contract_expiry = contract_expiry
        self.cum_pv: float = 0.0
        self.cum_vol: int = 0
        self.last_cum_day_vol: int = 0

    def update(
        self,
        high: float,
        low: float,
        close: float,
        current_cum_vol: int,
        contract_expiry: Optional[date] = None,
    ) -> float:
        """Update VWAP with a new bar and return current cumulative VWAP."""
        contract_changed = False
        if contract_expiry is not None and self.contract_expiry is not None:
            if contract_expiry != self.contract_expiry:
                contract_changed = True
                self.contract_expiry = contract_expiry
                self.cum_pv = 0.0
                self.cum_vol = 0
                self.last_cum_day_vol = 0

        bar_vol = compute_bar_volume(current_cum_vol, self.last_cum_day_vol, contract_changed)
        self.last_cum_day_vol = current_cum_vol

        typical_price = (high + low + close) / 3.0

        if bar_vol > 0:
            self.cum_pv += typical_price * bar_vol
            self.cum_vol += bar_vol

        if self.cum_vol > 0:
            return round(self.cum_pv / self.cum_vol, 2)
        return round(close, 2)

    def reset(self) -> None:
        """Reset state at session start."""
        self.cum_pv = 0.0
        self.cum_vol = 0
        self.last_cum_day_vol = 0


# =====================================================================
# BLACK-76 GREEKS ENGINE (Used for SENSEX BFO and Analytical Validation)
# =====================================================================

class Black76:
    """Analytical Black-76 model for European options on futures / forward prices.
    
    F: Forward or Futures price
    K: Strike price
    T: Time to expiration in annualized years (e.g. days / 365.0)
    r: Risk-free rate (decimal, e.g. 0.065 for 6.5%)
    sigma: Volatility (decimal, e.g. 0.15 for 15%)
    """

    @staticmethod
    def d1_d2(F: float, K: float, T: float, sigma: float) -> Tuple[float, float]:
        if T <= 1e-6 or sigma <= 1e-6 or F <= 0 or K <= 0:
            return float("nan"), float("nan")
        sigma_sqrt_t = sigma * math.sqrt(T)
        d1 = (math.log(F / K) + 0.5 * sigma * sigma * T) / sigma_sqrt_t
        d2 = d1 - sigma_sqrt_t
        return d1, d2

    @classmethod
    def price(cls, F: float, K: float, T: float, r: float, sigma: float, option_type: str) -> float:
        if T <= 1e-6:
            # Intrinsic value at expiration
            if option_type.upper() in ["CE", "CALL"]:
                return max(0.0, F - K)
            return max(0.0, K - F)

        d1, d2 = cls.d1_d2(F, K, T, sigma)
        if math.isnan(d1):
            return 0.0

        df = math.exp(-r * T)
        opt = option_type.upper()
        if opt in ["CE", "CALL"]:
            return df * (F * norm.cdf(d1) - K * norm.cdf(d2))
        else:
            return df * (K * norm.cdf(-d2) - F * norm.cdf(-d1))

    @classmethod
    def implied_volatility(
        cls,
        market_price: float,
        F: float,
        K: float,
        T: float,
        r: float,
        option_type: str,
    ) -> float:
        """Invert Black-76 price using Brent's method to find IV."""
        if market_price <= 0.05 or T <= 1e-6 or F <= 0 or K <= 0:
            return 0.0

        df = math.exp(-r * T)
        opt = option_type.upper()
        intrinsic = df * max(0.0, F - K) if opt in ["CE", "CALL"] else df * max(0.0, K - F)
        if market_price < intrinsic:
            market_price = intrinsic + 0.05

        def objective(sig: float) -> float:
            return cls.price(F, K, T, r, sig, opt) - market_price

        try:
            # Search bracket between 1% and 400% IV
            iv = brentq(objective, 0.01, 4.0, maxiter=50, xtol=1e-4)
            return float(iv)
        except Exception:
            return 0.0

    @classmethod
    def greeks(
        cls,
        F: float,
        K: float,
        T: float,
        r: float,
        sigma: float,
        option_type: str,
    ) -> Dict[str, float]:
        """Compute Delta, Gamma, Theta, Vega under Black-76.
        
        Theta is reported in points per day (divided by 365).
        Vega is reported in points per 1% move in volatility.
        """
        if T <= 1e-6 or sigma <= 1e-6 or F <= 0 or K <= 0:
            return {"delta": 0.0, "gamma": 0.0, "theta": 0.0, "vega": 0.0}

        d1, d2 = cls.d1_d2(F, K, T, sigma)
        if math.isnan(d1):
            return {"delta": 0.0, "gamma": 0.0, "theta": 0.0, "vega": 0.0}

        df = math.exp(-r * T)
        n_d1 = norm.pdf(d1)
        sqrt_t = math.sqrt(T)
        opt = option_type.upper()

        # Delta
        if opt in ["CE", "CALL"]:
            delta = df * norm.cdf(d1)
        else:
            delta = -df * norm.cdf(-d1)

        # Gamma (identical for Call and Put)
        gamma = (df * n_d1) / (F * sigma * sqrt_t)

        # Vega (per 1% change in vol, 0.01)
        vega = df * F * sqrt_t * n_d1 * 0.01

        # Theta (annualized then divided by 365 for daily decay)
        first_term = -(df * F * n_d1 * sigma) / (2.0 * sqrt_t)
        if opt in ["CE", "CALL"]:
            second_term = -r * df * (F * norm.cdf(d1) - K * norm.cdf(d2))
        else:
            second_term = -r * df * (K * norm.cdf(-d2) - F * norm.cdf(-d1))
        theta_annual = first_term + second_term
        theta_daily = theta_annual / 365.0

        return {
            "delta": round(float(delta), 4),
            "gamma": round(float(gamma), 6),
            "theta": round(float(theta_daily), 4),
            "vega": round(float(vega), 4),
        }


# =====================================================================
# DERIVED INTRADAY OPTION METRICS (PCR, Max Pain, ATM IV, Skew, Basis)
# =====================================================================

def calculate_derived_metrics(
    underlying: str,
    spot_price: float,
    futures_price: Optional[float],
    options_df: pd.DataFrame,
    recording_since: Optional[datetime] = None,
    history_days_count: int = 1,
) -> Dict[str, Any]:
    """Calculate PCR (OI & Vol), Max Pain, ATM IV, 25-Delta IV Skew, and Futures Basis.
    
    options_df expected columns:
    [strike, option_type, ltp, oi, volume, iv, delta]
    """
    now = datetime.now()
    if options_df.empty or spot_price <= 0:
        return {
            "timestamp": now,
            "underlying": underlying,
            "pcr_oi": None,
            "pcr_volume": None,
            "max_pain": None,
            "atm_iv": None,
            "iv_skew": None,
            "futures_basis": round(futures_price - spot_price, 2) if futures_price else None,
            "recording_since": recording_since or now,
            "history_days_count": history_days_count,
        }

    ce_df = options_df[options_df["option_type"].str.upper() == "CE"]
    pe_df = options_df[options_df["option_type"].str.upper() == "PE"]

    # 1. PCR OI & PCR Volume
    ce_oi = ce_df["oi"].sum()
    pe_oi = pe_df["oi"].sum()
    pcr_oi = round(float(pe_oi / ce_oi), 3) if ce_oi > 0 else None

    ce_vol = ce_df["volume"].sum()
    pe_vol = pe_df["volume"].sum()
    pcr_volume = round(float(pe_vol / ce_vol), 3) if ce_vol > 0 else None

    # 2. Max Pain: Strike minimizing sum(CE_loss + PE_loss)
    strikes = np.sort(options_df["strike"].unique())
    total_losses = []
    for s in strikes:
        ce_loss = ce_df.apply(lambda r: max(0.0, s - r["strike"]) * r["oi"], axis=1).sum()
        pe_loss = pe_df.apply(lambda r: max(0.0, r["strike"] - s) * r["oi"], axis=1).sum()
        total_losses.append(ce_loss + pe_loss)

    max_pain = float(strikes[np.argmin(total_losses)]) if len(strikes) > 0 else None

    # 3. ATM IV: Average IV of closest ATM Call and Put
    closest_strike = min(strikes, key=lambda x: abs(x - spot_price)) if len(strikes) > 0 else None
    atm_iv = None
    if closest_strike is not None:
        atm_ce = ce_df[ce_df["strike"] == closest_strike]
        atm_pe = pe_df[pe_df["strike"] == closest_strike]
        iv_vals = []
        if not atm_ce.empty and atm_ce.iloc[0]["iv"] > 0:
            iv_vals.append(atm_ce.iloc[0]["iv"])
        if not atm_pe.empty and atm_pe.iloc[0]["iv"] > 0:
            iv_vals.append(atm_pe.iloc[0]["iv"])
        if iv_vals:
            atm_iv = round(float(np.mean(iv_vals)), 4)

    # 4. 25-Delta IV Skew: IV(Put ~ -0.25) - IV(Call ~ 0.25)
    iv_skew = None
    if "delta" in options_df.columns:
        ce_with_delta = ce_df[ce_df["delta"] > 0].copy()
        pe_with_delta = pe_df[pe_df["delta"] < 0].copy()
        if not ce_with_delta.empty and not pe_with_delta.empty:
            call_25 = ce_with_delta.iloc[(ce_with_delta["delta"] - 0.25).abs().argmin()]
            put_25 = pe_with_delta.iloc[(pe_with_delta["delta"] - (-0.25)).abs().argmin()]
            if call_25["iv"] > 0 and put_25["iv"] > 0:
                iv_skew = round(float(put_25["iv"] - call_25["iv"]), 4)

    # 5. Futures Basis
    futures_basis = round(futures_price - spot_price, 2) if futures_price else None

    return {
        "timestamp": now,
        "underlying": underlying,
        "pcr_oi": pcr_oi,
        "pcr_volume": pcr_volume,
        "max_pain": max_pain,
        "atm_iv": atm_iv,
        "iv_skew": iv_skew,
        "futures_basis": futures_basis,
        "recording_since": recording_since or now,
        "history_days_count": history_days_count,
    }
