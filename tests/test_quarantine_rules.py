"""Tests for options microstructure validation and quarantine rules."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from data.options_audit import (
    evaluate_put_call_parity_pair,
    quarantine_options_dataframe,
    validate_option_snapshot_row,
)


def test_quarantine_rule_ltp_zero_or_negative():
    """Verify that rows with LTP <= 0 are quarantined."""
    row_zero = {"strike": 22500, "option_type": "CE", "ltp": 0.0, "delta": 0.50, "oi": 1000}
    is_val, reason = validate_option_snapshot_row(row_zero)
    assert not is_val
    assert "LTP <= 0" in reason

    row_neg = {"strike": 22500, "option_type": "CE", "ltp": -5.0, "delta": 0.50, "oi": 1000}
    is_val, reason = validate_option_snapshot_row(row_neg)
    assert not is_val
    assert "LTP <= 0" in reason


def test_quarantine_rule_delta_zero_or_nan():
    """Verify that rows with delta = 0 or NaN are quarantined."""
    row_zero_delta = {"strike": 22500, "option_type": "CE", "ltp": 150.0, "delta": 0.0, "oi": 1000}
    is_val, reason = validate_option_snapshot_row(row_zero_delta)
    assert not is_val
    assert "Delta is zero or NaN" in reason

    row_nan_delta = {"strike": 22500, "option_type": "CE", "ltp": 150.0, "delta": np.nan, "oi": 1000}
    is_val, reason = validate_option_snapshot_row(row_nan_delta)
    assert not is_val
    assert "Delta is zero or NaN" in reason


def test_quarantine_rule_delta_sign_consistency():
    """Verify CE delta must be positive and PE delta must be negative."""
    row_ce_neg = {"strike": 22500, "option_type": "CE", "ltp": 150.0, "delta": -0.45, "oi": 1000}
    is_val, reason = validate_option_snapshot_row(row_ce_neg)
    assert not is_val
    assert "Call option has negative delta" in reason

    row_pe_pos = {"strike": 22500, "option_type": "PE", "ltp": 150.0, "delta": +0.55, "oi": 1000}
    is_val, reason = validate_option_snapshot_row(row_pe_pos)
    assert not is_val
    assert "Put option has positive delta" in reason


def test_quarantine_rule_liquid_strike_zero_oi():
    """Verify that liquid ATM +/- 500 strikes with zero OI are quarantined."""
    atm = 22500.0
    # Liquid ATM strike (22500) with 0 OI -> quarantined
    row_atm_zero_oi = {"strike": 22500, "option_type": "CE", "ltp": 180.0, "delta": 0.52, "oi": 0}
    is_val, reason = validate_option_snapshot_row(row_atm_zero_oi, atm_strike=atm, liquid_window_pts=500.0)
    assert not is_val
    assert "Zero or missing OI" in reason

    # Liquid OTM strike within 500 pts (22700) with 0 OI -> quarantined
    row_near_zero_oi = {"strike": 22700, "option_type": "CE", "ltp": 75.0, "delta": 0.32, "oi": 0}
    is_val, reason = validate_option_snapshot_row(row_near_zero_oi, atm_strike=atm, liquid_window_pts=500.0)
    assert not is_val
    assert "Zero or missing OI" in reason

    # Far OTM strike outside 500 pts (23500) with 0 OI -> not quarantined by liquid rule
    row_far_zero_oi = {"strike": 23500, "option_type": "CE", "ltp": 2.0, "delta": 0.02, "oi": 0}
    is_val, reason = validate_option_snapshot_row(row_far_zero_oi, atm_strike=atm, liquid_window_pts=500.0)
    assert is_val


def test_quarantine_options_dataframe_partition():
    """Verify dataframe partitioning into valid and quarantined tables."""
    data = [
        {"strike": 22500, "option_type": "CE", "ltp": 180.0, "delta": 0.52, "oi": 50000, "iv": 0.14},
        {"strike": 22500, "option_type": "PE", "ltp": 150.0, "delta": -0.48, "oi": 60000, "iv": 0.16},
        {"strike": 22550, "option_type": "CE", "ltp": 0.0, "delta": 0.40, "oi": 10000, "iv": 0.14},  # Bad: LTP 0
        {"strike": 22600, "option_type": "CE", "ltp": 110.0, "delta": 0.0, "oi": 20000, "iv": 0.14},  # Bad: Delta 0
        {"strike": 22650, "option_type": "PE", "ltp": 210.0, "delta": -0.65, "oi": 0, "iv": 0.15},    # Bad: Liquid 0 OI
    ]
    df = pd.DataFrame(data)
    df_valid, df_q = quarantine_options_dataframe(df, atm_strike=22500.0, liquid_window_pts=500.0)

    assert len(df_valid) == 2
    assert len(df_q) == 3
    assert all(df_valid["is_valid"])
    assert not any(df_q["is_valid"])
    assert "quarantine_reason" in df_q.columns


def test_put_call_parity_pair_evaluation():
    """Verify Put-Call Parity: C - P = (F - K)*e^(-rT)."""
    # Healthy ATM pair
    # K=22500, F=22533.04, DTE=6 days, r=6.85%
    # Actual spread C - P = 181.5 - 148.5 = 33.0
    res_pass = evaluate_put_call_parity_pair(
        call_ltp=181.5,
        put_ltp=148.5,
        strike=22500.0,
        forward_or_spot=22533.04,
        dte_days=6.0,
        r=0.0685,
        tolerance_pts=5.0,
    )
    assert res_pass["is_pass"]
    assert res_pass["discrepancy_pts"] < 1.0

    # Broken/arbitraged pair (Call mispriced 50 pts too high)
    res_fail = evaluate_put_call_parity_pair(
        call_ltp=231.5,
        put_ltp=148.5,
        strike=22500.0,
        forward_or_spot=22533.04,
        dte_days=6.0,
        r=0.0685,
        tolerance_pts=5.0,
    )
    assert not res_fail["is_pass"]
    assert res_fail["discrepancy_pts"] > 40.0
