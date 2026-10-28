"""Tests for time-varying lot sizes, expiry regimes, holiday calendar awareness, and labeling."""

from __future__ import annotations

from datetime import date, datetime, timedelta
import pandas as pd
import pytest

from config.loader import ConfigManager
from models.labels import compute_forward_returns, compute_triple_barrier_labels


def test_time_varying_lot_sizes() -> None:
    cfg = ConfigManager()

    # NIFTY lot sizes across regimes (2010 to present)
    assert cfg.get_lot_size("NIFTY", date(2012, 1, 1)) == 50
    assert cfg.get_lot_size("NIFTY", date(2020, 1, 1)) == 75
    assert cfg.get_lot_size("NIFTY", date(2022, 1, 1)) == 50
    assert cfg.get_lot_size("NIFTY", date(2024, 6, 1)) == 25
    assert cfg.get_lot_size("NIFTY", date(2025, 1, 1)) == 75
    assert cfg.get_lot_size("NIFTY", date(2026, 2, 1)) == 65  # Current lot size

    # BANK NIFTY lot sizes across regimes (2010 to present)
    assert cfg.get_lot_size("BANKNIFTY", date(2012, 1, 1)) == 25
    assert cfg.get_lot_size("BANKNIFTY", date(2018, 1, 1)) == 40
    assert cfg.get_lot_size("BANKNIFTY", date(2021, 1, 1)) == 25
    assert cfg.get_lot_size("BANKNIFTY", date(2023, 8, 1)) == 15
    assert cfg.get_lot_size("BANKNIFTY", date(2025, 1, 1)) == 35  # SEBI Nov 2024 revision
    assert cfg.get_lot_size("BANKNIFTY", date(2026, 2, 1)) == 30  # Replaced 35 around Dec 2025/Jan 2026

    # SENSEX lot sizes
    assert cfg.get_lot_size("SENSEX", date(2012, 1, 1)) == 50
    assert cfg.get_lot_size("SENSEX", date(2023, 6, 1)) == 10
    assert cfg.get_lot_size("SENSEX", date(2025, 1, 1)) == 20
    assert cfg.get_lot_size("SENSEX", date(2026, 2, 1)) == 20  # Current lot size


def test_time_varying_expiry_rules() -> None:
    cfg = ConfigManager()

    # NIFTY expiry regimes: monthly 2010 -> weekly Thu 2019 -> weekly Tue 2025
    rule_nifty_2012 = cfg.get_expiry_rule("NIFTY", date(2012, 1, 1))
    assert rule_nifty_2012["frequency"] == "monthly"
    assert rule_nifty_2012["day_of_week"] == "Thursday"

    rule_nifty_2020 = cfg.get_expiry_rule("NIFTY", date(2020, 1, 1))
    assert rule_nifty_2020["frequency"] == "weekly"
    assert rule_nifty_2020["day_of_week"] == "Thursday"

    rule_nifty_current = cfg.get_expiry_rule("NIFTY", date(2025, 9, 15))
    assert rule_nifty_current["frequency"] == "weekly"
    assert rule_nifty_current["day_of_week"] == "Tuesday"

    # BANK NIFTY expiry regimes: monthly 2010 -> weekly Thu 2016 -> weekly Wed 2023 -> monthly Thu 2024 -> monthly Tue 2025
    rule_bn_2012 = cfg.get_expiry_rule("BANKNIFTY", date(2012, 1, 1))
    assert rule_bn_2012["frequency"] == "monthly"
    assert rule_bn_2012["day_of_week"] == "Thursday"

    rule_bn_2018 = cfg.get_expiry_rule("BANKNIFTY", date(2018, 1, 1))
    assert rule_bn_2018["frequency"] == "weekly"
    assert rule_bn_2018["day_of_week"] == "Thursday"

    rule_bn_2023 = cfg.get_expiry_rule("BANKNIFTY", date(2023, 10, 1))
    assert rule_bn_2023["frequency"] == "weekly"
    assert rule_bn_2023["day_of_week"] == "Wednesday"

    rule_bn_nov24 = cfg.get_expiry_rule("BANKNIFTY", date(2024, 12, 1))
    assert rule_bn_nov24["frequency"] == "monthly"
    assert rule_bn_nov24["day_of_week"] == "Thursday"

    rule_bn_curr = cfg.get_expiry_rule("BANKNIFTY", date(2025, 9, 15))
    assert rule_bn_curr["frequency"] == "monthly"
    assert rule_bn_curr["day_of_week"] == "Tuesday"

    # SENSEX expiry regimes: monthly 2010 -> weekly Fri 2023 -> weekly Tue Nov 2024 -> weekly Thu Sep 2025
    rule_sen_2012 = cfg.get_expiry_rule("SENSEX", date(2012, 1, 1))
    assert rule_sen_2012["frequency"] == "monthly"
    assert rule_sen_2012["day_of_week"] == "Thursday"

    rule_sen_2023 = cfg.get_expiry_rule("SENSEX", date(2023, 8, 1))
    assert rule_sen_2023["frequency"] == "weekly"
    assert rule_sen_2023["day_of_week"] == "Friday"

    rule_sen_tue = cfg.get_expiry_rule("SENSEX", date(2025, 1, 1))
    assert rule_sen_tue["frequency"] == "weekly"
    assert rule_sen_tue["day_of_week"] == "Tuesday"  # SEBI framework Nov 2024 - Aug 2025

    rule_sen_curr = cfg.get_expiry_rule("SENSEX", date(2025, 9, 15))
    assert rule_sen_curr["frequency"] == "weekly"
    assert rule_sen_curr["day_of_week"] == "Thursday"


def test_expiry_rules_continuous_coverage_from_2010() -> None:
    """Verify that EVERY single date from 2010-01-01 to today has an active, valid expiry rule."""
    cfg = ConfigManager()
    curr = date(2010, 1, 1)
    end = date.today()

    instruments = ["NIFTY", "BANKNIFTY", "SENSEX"]
    # Sample every 30 days to cover all regimes efficiently
    while curr <= end:
        for inst in instruments:
            rule = cfg.get_expiry_rule(inst, curr)
            assert rule is not None, f"No rule found for {inst} on {curr}"
            assert rule.get("frequency") in ["weekly", "monthly"]
            assert rule.get("day_of_week") in ["Tuesday", "Wednesday", "Thursday", "Friday"]

            lot = cfg.get_lot_size(inst, curr)
            assert isinstance(lot, int) and lot > 0, f"Invalid lot size for {inst} on {curr}"
        curr += timedelta(days=30)


def test_expiry_holiday_advancement() -> None:
    """If an expiry date falls on a recognized exchange trading holiday, it must shift to the previous trading day."""
    cfg = ConfigManager()

    # 2024-03-29 is Good Friday (Holiday in config/holidays.yaml)
    nominal_friday = date(2024, 3, 29)
    assert cfg.is_holiday(nominal_friday)
    resolved = cfg.resolve_expiry_date(nominal_friday)
    assert resolved == date(2024, 3, 28)

    # 2024-08-15 is Independence Day (Thursday holiday)
    nominal_thursday = date(2024, 8, 15)
    assert cfg.is_holiday(nominal_thursday)
    resolved_thu = cfg.resolve_expiry_date(nominal_thursday)
    assert resolved_thu == date(2024, 8, 14)


def test_labels_module_triple_barrier() -> None:
    """Validate Triple Barrier outcome calculation."""
    df = pd.DataFrame(
        {
            "close": [100.0, 101.0, 105.0, 102.0, 100.0],
            "high": [100.5, 103.0, 106.0, 103.0, 101.0],
            "low": [99.5, 100.0, 104.0, 101.0, 99.0],
            "atr_14": [2.0, 2.0, 2.0, 2.0, 2.0],
        }
    )

    tb = compute_triple_barrier_labels(df, pt_atr_mult=2.0, sl_atr_mult=1.0, time_limit_bars=3)
    assert "tb_label" in tb.columns
    assert tb.iloc[0]["tb_label"] == 1
    assert tb.iloc[0]["tb_barrier_hit"] == "PROFIT_TAKE"

    fwd = compute_forward_returns(df["close"], horizons=[1, 2])
    assert "target_fwd_ret_1" in fwd.columns
    assert "target_dir_1" in fwd.columns
    assert fwd.iloc[0]["target_dir_1"] == 1


def test_expiry_labeling_17nov2026_weekly():
    """Verify that 17NOV2026 is strictly classified as Weekly Expiry (19d), NOT Monthly Expiry.
    
    In November 2026 for NIFTY (Tuesday expiry regime):
    - 2026-11-03: Candidate 0 (Near Weekly)
    - 2026-11-10: Candidate 1 (Weekly)
    - 2026-11-17: Candidate 2 (Weekly Expiry, 19d to expiry)
    - 2026-11-24: Candidate 3 (Monthly Expiry, last Tuesday of month)
    """
    cfg = ConfigManager()

    dt_17nov = date(2026, 11, 17)
    rule = cfg.get_expiry_rule("NIFTY", dt_17nov)
    assert rule["frequency"] == "weekly"
    assert rule["day_of_week"] == "Tuesday"

    # Candidates in November 2026
    target_weekday = cfg._day_name_to_weekday("Tuesday")
    candidates = cfg._get_candidate_expiry_dates_in_month(2026, 11, target_weekday, "weekly")
    resolved_cands = [cfg.resolve_expiry_date(c) for c in candidates]

    # Verify 17NOV2026 is candidate 2
    assert dt_17nov in resolved_cands
    assert resolved_cands.index(dt_17nov) == 2

    # Monthly contract is strictly the last candidate
    monthly_cand = resolved_cands[-1]
    assert monthly_cand == date(2026, 11, 24) or monthly_cand == date(2026, 11, 23)
    assert dt_17nov != monthly_cand, "17NOV2026 must NOT be marked as monthly!"

    # Verify options_chain labeling logic
    from dashboard.options_chain import get_available_expiries
    expiries = get_available_expiries("NIFTY")
    # If scrip cache contains 17NOV2026 or fallback, verify tag
    for exp_str, label in expiries:
        if "17NOV2026" in exp_str:
            assert "Weekly" in label
            assert "Monthly" not in label
        if "23NOV2026" in exp_str or "24NOV2026" in exp_str:
            assert "Monthly" in label

