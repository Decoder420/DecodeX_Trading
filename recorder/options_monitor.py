"""Options chain snapshot monitor: Full chain PCR & Max Pain, ATM +/- 10 storage,
merged Open Interest from getMarketData FULL, and Black-76 for SENSEX.
"""

from __future__ import annotations

import json
import logging
import math
import os
import time
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
import numpy as np
import pandas as pd
import pytz

from config.loader import ConfigManager, config_manager
from data.rate_limiter import shared_rate_limiter
from recorder.metrics import Black76, calculate_derived_metrics

logger = logging.getLogger("OptionsMonitor")


class OptionsMonitor:
    """Monitors options chains for NIFTY, BANKNIFTY, SENSEX:
    - Merges Open Interest from getMarketData FULL
    - Calculates PCR & Max Pain on the FULL chain (avoiding edge artifacts)
    - Records ATM +/- 10 CE and PE strikes for storage
    - Dynamically recenters strikes as spot moves
    """

    STRIKE_STEPS = {
        "NIFTY": 50.0,
        "BANKNIFTY": 100.0,
        "SENSEX": 100.0,
    }

    def __init__(self, client: Any, cfg: Optional[ConfigManager] = None) -> None:
        self.client = client
        self.cfg = cfg or config_manager
        self.tz = pytz.timezone(self.cfg.get("market.timezone", "Asia/Kolkata"))
        self.risk_free_rate = self.cfg.get("options_model.risk_free_rate_pct", 6.5) / 100.0
        self.atm_strike_window = self.cfg.get("options_model.atm_strike_window", 10)

        # Scrip master path
        self.cache_path = Path(
            self.cfg.get("data.provider.angelone.cache_path", "data/cache/angel_scrip_master.json")
        )
        self._scrip_master: List[Dict[str, Any]] = []
        self._load_scrip_master()

        # Cache of active center strike per underlying
        self.center_strikes: Dict[str, float] = {}
        # Active expiries per underlying: {symbol: [(date, exp_str), ...]}
        self.active_expiries: Dict[str, List[Tuple[date, str]]] = {}
        self._resolve_expiries()

    def _load_scrip_master(self) -> None:
        if self.cache_path.exists():
            try:
                with open(self.cache_path, "r", encoding="utf-8") as f:
                    self._scrip_master = json.load(f)
                logger.info("OptionsMonitor loaded %d scrips from cache", len(self._scrip_master))
            except Exception as e:
                logger.warning("Failed loading scrip master cache: %s", e)

    def _resolve_expiries(self) -> None:
        """Find the nearest weekly and nearest monthly expiry for NIFTY, BANKNIFTY, SENSEX."""
        today = datetime.now().date()
        underlyings = ["NIFTY", "BANKNIFTY", "SENSEX"]
        exp_by_symbol: Dict[str, Set[Tuple[date, str]]] = {u: set() for u in underlyings}

        for s in self._scrip_master:
            name = s.get("name")
            seg = s.get("exch_seg")
            inst = s.get("instrumenttype")
            exp = s.get("expiry")
            if seg in ["NFO", "BFO"] and inst == "OPTIDX" and name in exp_by_symbol and exp:
                try:
                    exp_dt = datetime.strptime(exp, "%d%b%Y").date()
                    if exp_dt >= today:
                        exp_by_symbol[name].add((exp_dt, exp))
                except Exception:
                    pass

        for u in underlyings:
            sorted_exp = sorted(list(exp_by_symbol[u]), key=lambda x: x[0])
            if len(sorted_exp) >= 2:
                near_weekly = sorted_exp[0]
                monthly = None
                for exp_d, exp_str in sorted_exp[1:]:
                    if exp_d.month != near_weekly[0].month or (exp_d - near_weekly[0]).days >= 20:
                        monthly = (exp_d, exp_str)
                        break
                if not monthly:
                    monthly = sorted_exp[1]
                self.active_expiries[u] = [near_weekly, monthly]
            elif len(sorted_exp) == 1:
                self.active_expiries[u] = [sorted_exp[0]]
            else:
                self.active_expiries[u] = []
            logger.info("Active expiries for %s: %s", u, self.active_expiries[u])

    def get_atm_strikes(self, underlying: str, spot_price: float) -> List[float]:
        """Compute ATM +/- 10 strike prices centered on spot price."""
        step = self.STRIKE_STEPS.get(underlying, 50.0)
        center = round(spot_price / step) * step
        self.center_strikes[underlying] = center
        strikes = []
        for i in range(-self.atm_strike_window, self.atm_strike_window + 1):
            strikes.append(round(center + i * step, 2))
        return strikes

    def should_recenter(self, underlying: str, spot_price: float) -> bool:
        """Check if spot price moved beyond one strike step from previous center."""
        prev_center = self.center_strikes.get(underlying)
        if prev_center is None:
            return True
        step = self.STRIKE_STEPS.get(underlying, 50.0)
        return abs(spot_price - prev_center) >= step

    def fetch_snapshots(
        self,
        underlying: str,
        spot_price: float,
        futures_price: Optional[float] = None,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """Fetch options chain, merge Open Interest, compute FULL CHAIN derived metrics,
        and return ATM +/- 10 strikes for snapshot persistence.
        """
        now = datetime.now()
        atm_strikes = self.get_atm_strikes(underlying, spot_price)
        atm_strikes_set = set(atm_strikes)
        expiries = self.active_expiries.get(underlying, [])

        full_chain_rows: List[Dict[str, Any]] = []
        atm_option_rows: List[Dict[str, Any]] = []

        if underlying in ["NIFTY", "BANKNIFTY"]:
            seg = "NFO"
            for exp_dt, exp_str in expiries:
                # 1. Fetch broker optionGreek (returns all strikes with strikePrice and optionType)
                greeks_by_key: Dict[Tuple[float, str], Dict[str, Any]] = {}
                try:
                    params = {"name": underlying, "expirydate": exp_str}
                    res = shared_rate_limiter.execute_with_backoff(
                        "optionGreek",
                        self.client.optionGreek,
                        params,
                    )
                    for g in res.get("data") or []:
                        sp = round(float(g.get("strikePrice") or 0.0), 2)
                        ot = str(g.get("optionType") or "").upper()
                        if sp > 0 and ot:
                            greeks_by_key[(sp, ot)] = g
                except Exception as e:
                    logger.warning("Failed fetching optionGreek for %s %s: %s", underlying, exp_str, e)

                # 2. Find all option tokens from scrip master for this expiry
                matching_scrips = [
                    s for s in self._scrip_master
                    if s.get("exch_seg") == seg
                    and s.get("name") == underlying
                    and s.get("expiry") == exp_str
                    and s.get("instrumenttype") == "OPTIDX"
                ]

                # 3. Fetch getMarketData FULL in batches of 50 to retrieve true Open Interest
                all_tokens = [str(s["token"]) for s in matching_scrips]
                quotes_by_token: Dict[str, Dict[str, Any]] = {}
                for i in range(0, len(all_tokens), 50):
                    batch = all_tokens[i:i + 50]
                    try:
                        q_res = shared_rate_limiter.execute_with_backoff(
                            "quote",
                            self.client.getMarketData,
                            "FULL",
                            {seg: batch},
                        )
                        for q in q_res.get("data", {}).get("fetched", []):
                            quotes_by_token[str(q.get("symbolToken"))] = q
                    except Exception as e:
                        logger.warning("Failed fetching NFO quotes batch: %s", e)

                # Time to expiry in years for analytical fallback
                exp_datetime = datetime.combine(exp_dt, datetime.min.time()).replace(hour=15, minute=30)
                diff_hours = max((exp_datetime - now).total_seconds() / 3600.0, 0.1)
                T_years = diff_hours / (365.0 * 24.0)
                F_price = futures_price or (spot_price * math.exp(self.risk_free_rate * T_years))

                # 4. Merge OI from quotes with Greeks from optionGreek (or Black-76 fallback)
                for s in matching_scrips:
                    tok = str(s["token"])
                    q = quotes_by_token.get(tok, {})

                    k = round(float(s.get("strike", 0)) / 100.0, 2)
                    otype = "CE" if "CE" in s.get("symbol", "").upper() else "PE"
                    g = greeks_by_key.get((k, otype), {})

                    ltp = float(q.get("ltp") or g.get("ltp") or 0.0)
                    vol = int(float(q.get("tradeVolume") or g.get("tradeVolume") or 0))
                    # Open Interest comes directly from getMarketData FULL
                    oi = int(float(q.get("opnInterest") or 0))

                    if g and float(g.get("delta") or 0.0) != 0.0:
                        iv = float(g.get("impliedVolatility") or 0.0) / 100.0
                        delta = float(g.get("delta") or 0.0)
                        gamma = float(g.get("gamma") or 0.0)
                        theta = float(g.get("theta") or 0.0)
                        vega = float(g.get("vega") or 0.0)
                        g_source = "broker_optionGreek"
                    else:
                        # Analytical Black-76 computation
                        iv = Black76.implied_volatility(ltp, F_price, k, T_years, self.risk_free_rate, otype)
                        if iv <= 0:
                            iv = 0.16
                        b76_g = Black76.greeks(F_price, k, T_years, self.risk_free_rate, iv, otype)
                        delta = b76_g["delta"]
                        gamma = b76_g["gamma"]
                        theta = b76_g["theta"]
                        vega = b76_g["vega"]
                        g_source = "computed_black76"

                    row = {
                        "timestamp": now,
                        "underlying": underlying,
                        "contract_expiry": exp_dt,
                        "strike": k,
                        "option_type": otype,
                        "token": tok,
                        "ltp": ltp,
                        "volume": vol,
                        "oi": oi,
                        "iv": round(iv, 4),
                        "delta": round(delta, 4),
                        "gamma": round(gamma, 6),
                        "theta": round(theta, 4),
                        "vega": round(vega, 4),
                        "greeks_source": g_source,
                        "source": "rest",
                    }
                    full_chain_rows.append(row)
                    if k in atm_strikes_set:
                        atm_option_rows.append(row)

        elif underlying == "SENSEX":
            seg = "BFO"
            for exp_dt, exp_str in expiries:
                matching_scrips = [
                    s for s in self._scrip_master
                    if s.get("exch_seg") == seg
                    and s.get("name") == "SENSEX"
                    and s.get("expiry") == exp_str
                    and s.get("instrumenttype") == "OPTIDX"
                ]

                all_tokens = [str(s["token"]) for s in matching_scrips]
                quotes_by_token: Dict[str, Dict[str, Any]] = {}
                for i in range(0, len(all_tokens), 50):
                    batch = all_tokens[i:i + 50]
                    try:
                        q_res = shared_rate_limiter.execute_with_backoff(
                            "quote",
                            self.client.getMarketData,
                            "FULL",
                            {seg: batch},
                        )
                        for q in q_res.get("data", {}).get("fetched", []):
                            quotes_by_token[str(q.get("symbolToken"))] = q
                    except Exception as e:
                        logger.warning("Failed fetching BFO quotes batch: %s", e)

                exp_datetime = datetime.combine(exp_dt, datetime.min.time()).replace(hour=15, minute=30)
                diff_hours = max((exp_datetime - now).total_seconds() / 3600.0, 0.1)
                T = diff_hours / (365.0 * 24.0)
                F = (futures_price or (spot_price * math.exp(self.risk_free_rate * T)))

                for s in matching_scrips:
                    tok = str(s["token"])
                    q = quotes_by_token.get(tok, {})
                    ltp = float(q.get("ltp") or 0.0)
                    vol = int(float(q.get("tradeVolume") or 0))
                    oi = int(float(q.get("opnInterest") or 0))
                    k = float(s.get("strike", 0)) / 100.0
                    otype = "CE" if "CE" in s.get("symbol", "").upper() else "PE"

                    iv = Black76.implied_volatility(ltp, F, k, T, self.risk_free_rate, otype)
                    greeks = Black76.greeks(F, k, T, self.risk_free_rate, iv, otype)

                    row = {
                        "timestamp": now,
                        "underlying": underlying,
                        "contract_expiry": exp_dt,
                        "strike": k,
                        "option_type": otype,
                        "token": tok,
                        "ltp": ltp,
                        "volume": vol,
                        "oi": oi,
                        "iv": round(iv, 4),
                        "delta": greeks["delta"],
                        "gamma": greeks["gamma"],
                        "theta": greeks["theta"],
                        "vega": greeks["vega"],
                        "greeks_source": "computed_black76",
                        "source": "rest",
                    }
                    full_chain_rows.append(row)
                    if k in atm_strikes_set:
                        atm_option_rows.append(row)

        # 5. Compute PCR, Max Pain, and ATM IV on the FULL CHAIN DataFrame
        df_full = pd.DataFrame(full_chain_rows)
        # Filter to nearest expiry for primary derived metrics
        near_expiry_d = expiries[0][0] if expiries else None
        if near_expiry_d and not df_full.empty:
            df_full_near = df_full[df_full["contract_expiry"] == near_expiry_d]
        else:
            df_full_near = df_full

        metrics = calculate_derived_metrics(
            underlying=underlying,
            spot_price=spot_price,
            futures_price=futures_price,
            options_df=df_full_near,
        )

        return atm_option_rows, metrics
