"""Unit tests for recorder/metrics.py: Volume differencing, VWAP, Black-76, and derived metrics."""

from __future__ import annotations

from datetime import date, datetime
import math
import numpy as np
import pandas as pd
import pytest

from recorder.metrics import (
    compute_bar_volume,
    CumulativeIntradayVWAP,
    Black76,
    calculate_derived_metrics,
)


def test_volume_differencing_normal() -> None:
    """Test that incremental bar volume is computed correctly from cumulative day volume."""
    # Bar 1: Day starts at 1,000 cumulative volume
    assert compute_bar_volume(current_cum_vol=1000, prev_cum_vol=0) == 1000
    # Bar 2: Cumulative volume increases to 2,500 (+1,500)
    assert compute_bar_volume(current_cum_vol=2500, prev_cum_vol=1000) == 1500
    # Bar 3: Cumulative volume unchanged (+0)
    assert compute_bar_volume(current_cum_vol=2500, prev_cum_vol=2500) == 0


def test_volume_differencing_contract_rollover() -> None:
    """Test that contract rollover resets cumulative baseline without negative volume."""
    # Near contract cumulative volume was 50,000
    # Far contract (newly active after rollover) has cumulative volume 12,000
    bar_vol = compute_bar_volume(
        current_cum_vol=12000,
        prev_cum_vol=50000,
        contract_changed=True,
    )
    assert bar_vol == 12000

    # Test auto-detection of reset if cur < prev even without flag
    bar_vol_auto = compute_bar_volume(current_cum_vol=500, prev_cum_vol=50000)
    assert bar_vol_auto == 500


def test_cumulative_intraday_vwap_and_rollover() -> None:
    """Test VWAP calculation and state reset on contract change."""
    vwap_calc = CumulativeIntradayVWAP(symbol="NIFTY_FUT", contract_expiry=date(2026, 10, 29))

    # Bar 1: H=24010, L=23990, C=24000 (Typ=24000), cum_vol=100
    v1 = vwap_calc.update(high=24010, low=23990, close=24000, current_cum_vol=100)
    assert v1 == 24000.0

    # Bar 2: H=24030, L=24010, C=24020 (Typ=24020), cum_vol=300 (diff=200)
    # Total PV = 24000*100 + 24020*200 = 2400000 + 4804000 = 7204000
    # Total Vol = 300
    # VWAP = 7204000 / 300 = 24013.33
    v2 = vwap_calc.update(high=24030, low=24010, close=24020, current_cum_vol=300)
    assert v2 == 24013.33

    # Contract Rollover to November contract
    # New contract starts with cum_vol=50, H=24150, L=24130, C=24140 (Typ=24140)
    v3 = vwap_calc.update(
        high=24150,
        low=24130,
        close=24140,
        current_cum_vol=50,
        contract_expiry=date(2026, 11, 26),
    )
    assert v3 == 24140.0
    assert vwap_calc.contract_expiry == date(2026, 11, 26)


def test_black76_analytical_greeks() -> None:
    """Test Black-76 analytical greeks against call-put parity and boundary properties."""
    F = 24000.0
    K = 24000.0  # ATM
    T = 7.0 / 365.0  # 7 days to expiry
    r = 0.065
    sigma = 0.15  # 15% IV

    c_price = Black76.price(F, K, T, r, sigma, "CE")
    p_price = Black76.price(F, K, T, r, sigma, "PE")
    df = math.exp(-r * T)

    # Put-Call parity on futures: C - P = df * (F - K) = 0 for ATM
    assert pytest.approx(c_price - p_price, abs=1e-5) == 0.0

    c_greeks = Black76.greeks(F, K, T, r, sigma, "CE")
    p_greeks = Black76.greeks(F, K, T, r, sigma, "PE")

    # Gamma and Vega are identical for Call and Put
    assert c_greeks["gamma"] == p_greeks["gamma"]
    assert c_greeks["vega"] == p_greeks["vega"]

    # Delta relationship: Delta_call - Delta_put = df
    delta_diff = c_greeks["delta"] - p_greeks["delta"]
    assert pytest.approx(delta_diff, abs=0.01) == df

    # Invert IV from market price
    iv_recovered = Black76.implied_volatility(c_price, F, K, T, r, "CE")
    assert pytest.approx(iv_recovered, abs=1e-3) == sigma


def test_derived_metrics_calculation() -> None:
    """Test PCR, Max Pain, ATM IV, Skew, and Basis calculation."""
    spot = 24000.0
    fut = 24050.0

    options_data = [
        {"strike": 23800.0, "option_type": "CE", "ltp": 250.0, "oi": 50000, "volume": 10000, "iv": 0.16, "delta": 0.70},
        {"strike": 23800.0, "option_type": "PE", "ltp": 40.0, "oi": 150000, "volume": 30000, "iv": 0.18, "delta": -0.25},
        {"strike": 24000.0, "option_type": "CE", "ltp": 120.0, "oi": 100000, "volume": 25000, "iv": 0.14, "delta": 0.50},
        {"strike": 24000.0, "option_type": "PE", "ltp": 115.0, "oi": 120000, "volume": 20000, "iv": 0.14, "delta": -0.50},
        {"strike": 24200.0, "option_type": "CE", "ltp": 45.0, "oi": 160000, "volume": 35000, "iv": 0.13, "delta": 0.25},
        {"strike": 24200.0, "option_type": "PE", "ltp": 240.0, "oi": 40000, "volume": 8000, "iv": 0.15, "delta": -0.70},
    ]
    df_opts = pd.DataFrame(options_data)

    metrics = calculate_derived_metrics(
        underlying="NIFTY",
        spot_price=spot,
        futures_price=fut,
        options_df=df_opts,
    )

    # PCR OI = (150000 + 120000 + 40000) / (50000 + 100000 + 160000) = 310000 / 310000 = 1.0
    assert metrics["pcr_oi"] == 1.0
    # PCR Vol = (30000 + 20000 + 8000) / (10000 + 25000 + 35000) = 58000 / 70000 = 0.829
    assert metrics["pcr_volume"] == 0.829
    # Basis = 24050 - 24000 = 50.0
    assert metrics["futures_basis"] == 50.0
    # ATM IV at 24000 = 0.14
    assert metrics["atm_iv"] == 0.14
    # 25-Delta Skew = IV(PE @ -0.25) - IV(CE @ 0.25) = 0.18 - 0.13 = 0.05
    assert metrics["iv_skew"] == 0.05


def test_futures_roll_rules() -> None:
    """Test institutional futures rollover evaluation rules (OI crossover, volume crossover, time cutoff)."""
    from recorder.roll import FuturesRollManager

    mgr = FuturesRollManager(underlying="NIFTY")
    near_exp = date(2026, 10, 27)
    next_exp = date(2026, 11, 23)

    # 1. DTE > 1: No roll allowed yet
    t_early = datetime(2026, 10, 20, 11, 0)
    sig1 = mgr.evaluate_roll(
        current_time=t_early,
        near_expiry=near_exp,
        near_symbol="NIFTY27OCTFUT",
        near_price=22700.0,
        near_oi=12000000,
        near_vol=5000000,
        next_expiry=next_exp,
        next_symbol="NIFTY23NOVFUT",
        next_price=22810.0,
        next_oi=3000000,
        next_vol=1000000,
    )
    assert not sig1.should_roll
    assert "DTE=7 > 1" in sig1.reason

    # 2. Expiry Eve (DTE=1, e.g. 2026-10-26 today): Next OI exceeds near OI -> Trigger Roll!
    t_eve = datetime(2026, 10, 26, 13, 0)
    sig2 = mgr.evaluate_roll(
        current_time=t_eve,
        near_expiry=near_exp,
        near_symbol="NIFTY27OCTFUT",
        near_price=22706.0,
        near_oi=11093000,
        near_vol=4655000,
        next_expiry=next_exp,
        next_symbol="NIFTY23NOVFUT",
        next_price=22820.0,
        next_oi=11247000,  # Crossover!
        next_vol=4469000,
    )
    assert sig2.should_roll
    assert "OI Crossover detected" in sig2.reason
    assert sig2.roll_spread == 114.0  # 22820 - 22706

    # 3. Post-roll state: subsequent evaluations confirm already rolled
    sig3 = mgr.evaluate_roll(
        current_time=t_eve,
        near_expiry=near_exp,
        near_symbol="NIFTY27OCTFUT",
        near_price=22706.0,
        near_oi=11093000,
        near_vol=4655000,
        next_expiry=next_exp,
        next_symbol="NIFTY23NOVFUT",
        next_price=22820.0,
        next_oi=11247000,
        next_vol=4469000,
    )
    assert not sig3.should_roll
    assert "Already rolled" in sig3.reason

    # 4. Mandatory Time Cutoff test (fresh manager on Expiry Day at 12:30 IST)
    mgr_fresh = FuturesRollManager(underlying="BANKNIFTY")
    t_exp_day = datetime(2026, 10, 27, 12, 30)
    sig4 = mgr_fresh.evaluate_roll(
        current_time=t_exp_day,
        near_expiry=near_exp,
        near_symbol="BANKNIFTY27OCTFUT",
        near_price=54200.0,
        near_oi=2000000,  # near still higher
        near_vol=1000000,
        next_expiry=next_exp,
        next_symbol="BANKNIFTY23NOVFUT",
        next_price=54600.0,
        next_oi=1500000,  # next lower
        next_vol=800000,
    )
    assert sig4.should_roll
    assert "Mandatory expiry day cutoff" in sig4.reason

