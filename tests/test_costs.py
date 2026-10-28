"""Tests for effective-dated transaction cost calculation across multiple historical regimes.

Verifies hand-computed values for 2012, 2018, and 2025 against the CostCalculator.
"""

from __future__ import annotations

from datetime import date
import pytest

from backtest.costs import CostCalculator


def test_hand_computed_costs_2012() -> None:
    """Hand-computed verification for May 2012 (Finance Act 2012 Service Tax 12.36%, STT 0.017%)."""
    calc = CostCalculator()
    trade_date = date(2012, 5, 15)
    price = 5000.0
    qty = 50.0  # 1 lot NIFTY
    turnover = price * qty  # 250,000

    # BUY leg
    buy_cost = calc.calculate_trade_leg_cost(price, qty, "BUY", trade_date, slippage_bps=1.5)
    assert buy_cost.turnover == 250000.0
    assert buy_cost.brokerage == 20.0
    assert buy_cost.stt == 0.0  # No STT on buy
    assert pytest.approx(buy_cost.stamp_duty, rel=1e-5) == 5.0
    assert pytest.approx(buy_cost.exchange_charges, rel=1e-5) == 5.0
    assert pytest.approx(buy_cost.sebi_turnover_fee, rel=1e-5) == 0.25
    assert pytest.approx(buy_cost.gst, rel=1e-5) == (20.0 + 5.0 + 0.25) * 0.1236  # 3.1209
    assert pytest.approx(buy_cost.slippage_cost, rel=1e-5) == 250000.0 * 0.00015  # 37.50
    expected_buy_total = 20.0 + 5.0 + 5.0 + 0.25 + 3.1209 + 37.50
    assert pytest.approx(buy_cost.total_cost, rel=1e-4) == expected_buy_total

    # SELL leg
    sell_price = 5100.0
    sell_turnover = sell_price * qty  # 255,000
    sell_cost = calc.calculate_trade_leg_cost(sell_price, qty, "SELL", trade_date, slippage_bps=1.5)
    assert sell_cost.turnover == 255000.0
    assert sell_cost.brokerage == 20.0
    assert pytest.approx(sell_cost.stt, rel=1e-5) == 255000.0 * 0.00017  # 43.35
    assert sell_cost.stamp_duty == 0.0  # No stamp duty on sell
    assert pytest.approx(sell_cost.exchange_charges, rel=1e-5) == 255000.0 * 0.00002  # 5.10
    assert pytest.approx(sell_cost.sebi_turnover_fee, rel=1e-5) == 255000.0 * 0.000001  # 0.255
    assert pytest.approx(sell_cost.gst, rel=1e-5) == (20.0 + 5.10 + 0.255) * 0.1236  # 3.133878
    assert pytest.approx(sell_cost.slippage_cost, rel=1e-5) == 255000.0 * 0.00015  # 38.25
    expected_sell_total = 20.0 + 43.35 + 5.10 + 0.255 + 3.133878 + 38.25
    assert pytest.approx(sell_cost.total_cost, rel=1e-4) == expected_sell_total


def test_hand_computed_costs_2018() -> None:
    """Hand-computed verification for August 2018 (GST 18.0%, STT 0.010%)."""
    calc = CostCalculator()
    trade_date = date(2018, 8, 10)
    price = 11000.0
    qty = 75.0  # 1 lot NIFTY in 2018
    turnover = price * qty  # 825,000

    buy_cost = calc.calculate_trade_leg_cost(price, qty, "BUY", trade_date, slippage_bps=1.5)
    assert buy_cost.turnover == 825000.0
    assert buy_cost.brokerage == 20.0
    assert buy_cost.stt == 0.0
    assert pytest.approx(buy_cost.stamp_duty, rel=1e-5) == 825000.0 * 0.00002  # 16.50
    assert pytest.approx(buy_cost.exchange_charges, rel=1e-5) == 825000.0 * 0.000019  # 15.675
    assert pytest.approx(buy_cost.sebi_turnover_fee, rel=1e-5) == 825000.0 * 0.000001  # 0.825
    assert pytest.approx(buy_cost.gst, rel=1e-5) == (20.0 + 15.675 + 0.825) * 0.18  # 6.57
    assert pytest.approx(buy_cost.slippage_cost, rel=1e-5) == 825000.0 * 0.00015  # 123.75
    expected_buy_total = 20.0 + 16.50 + 15.675 + 0.825 + 6.57 + 123.75
    assert pytest.approx(buy_cost.total_cost, rel=1e-4) == expected_buy_total


def test_hand_computed_costs_2025() -> None:
    """Hand-computed verification for February 2025 (STT 0.020%, NSE true-to-label 0.00173%, stress slippage 5.0 bps)."""
    calc = CostCalculator()
    trade_date = date(2025, 2, 15)
    price = 23000.0
    qty = 65.0  # Current NIFTY lot size
    turnover = price * qty  # 1,495,000

    sell_cost = calc.calculate_trade_leg_cost(price, qty, "SELL", trade_date, slippage_bps=5.0)
    assert sell_cost.turnover == 1495000.0
    assert sell_cost.brokerage == 20.0
    assert pytest.approx(sell_cost.stt, rel=1e-5) == 1495000.0 * 0.0002  # 299.00
    assert sell_cost.stamp_duty == 0.0
    assert pytest.approx(sell_cost.exchange_charges, rel=1e-5) == 1495000.0 * 0.0000173  # 25.8635
    assert pytest.approx(sell_cost.ipft, rel=1e-5) == 1495000.0 * 0.0000010  # 1.495
    assert pytest.approx(sell_cost.sebi_turnover_fee, rel=1e-5) == 1495000.0 * 0.000001  # 1.495
    assert pytest.approx(sell_cost.gst, rel=1e-5) == (20.0 + 25.8635 + 1.495 + 1.495) * 0.18  # 8.79363
    assert pytest.approx(sell_cost.slippage_cost, rel=1e-5) == 1495000.0 * 0.0005  # 747.50
    expected_sell_total = 20.0 + 299.00 + 25.8635 + 1.495 + 1.495 + 8.79363 + 747.50
    assert pytest.approx(sell_cost.total_cost, rel=1e-4) == expected_sell_total


def test_hand_computed_costs_2026_budget() -> None:
    """Hand-computed verification for post-April 2026 (Budget 2026 STT 0.050% on sell side + IPFT 0.00010%)."""
    calc = CostCalculator()
    trade_date = date(2026, 4, 15)
    price = 24000.0
    qty = 65.0  # 1 lot NIFTY
    turnover = price * qty  # 1,560,000

    sell_cost = calc.calculate_trade_leg_cost(price, qty, "SELL", trade_date, slippage_bps=1.5)
    assert sell_cost.turnover == 1560000.0
    assert sell_cost.brokerage == 20.0
    # STT at 0.05% on sell turnover
    assert pytest.approx(sell_cost.stt, rel=1e-5) == 1560000.0 * 0.0005  # 780.00
    assert sell_cost.stamp_duty == 0.0
    assert pytest.approx(sell_cost.exchange_charges, rel=1e-5) == 1560000.0 * 0.0000173  # 26.988
    assert pytest.approx(sell_cost.ipft, rel=1e-5) == 1560000.0 * 0.0000010  # 1.56
    assert pytest.approx(sell_cost.sebi_turnover_fee, rel=1e-5) == 1560000.0 * 0.000001  # 1.56
    # GST on (Brokerage + Exchange + IPFT + SEBI): (20 + 26.988 + 1.56 + 1.56) * 18% = 50.108 * 0.18 = 9.01944
    assert pytest.approx(sell_cost.gst, rel=1e-5) == (20.0 + 26.988 + 1.56 + 1.56) * 0.18  # 9.01944
    assert pytest.approx(sell_cost.slippage_cost, rel=1e-5) == 1560000.0 * 0.00015  # 234.00
    
    # Exact component sum
    expected_components_sum = (
        sell_cost.brokerage
        + sell_cost.stt
        + sell_cost.stamp_duty
        + sell_cost.exchange_charges
        + sell_cost.ipft
        + sell_cost.sebi_turnover_fee
        + sell_cost.gst
        + sell_cost.slippage_cost
    )
    assert pytest.approx(sell_cost.total_cost, abs=1e-6) == expected_components_sum
    assert pytest.approx(sell_cost.total_cost, abs=1e-4) == 1073.12744


