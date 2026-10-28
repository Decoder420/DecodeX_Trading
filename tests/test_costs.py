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


def test_hand_computed_options_statutory_costs() -> None:
    """Hand-computed verification for Indian index options trading costs (Oct 2024 revised regime).
    
    Verified Rates:
    - Options STT: 0.15% (0.0015) of premium on sales (turnover_sell * 0.0015).
    - Brokerage: INR 20.00 per executed order (INR 40.00 round-trip).
    - Exchange turnover fee (Option-specific): 0.05% (0.0005) of total premium turnover.
    - Stamp duty (Option-specific): 0.003% (0.00003) on buy premium turnover.
    - IPFT (Investor Protection Fund Trust): 0.0001% (0.0000010) on total turnover.
    - SEBI turnover fee: Rs 10 per crore (0.0000010) on total turnover.
    - GST: 18% on (Brokerage + Exchange charges + SEBI fee + IPFT).
    """
    from data.paper_trading import calculate_option_paper_costs

    entry_premium = 200.0
    exit_premium = 250.0
    qty = 65  # 1 lot NIFTY

    res = calculate_option_paper_costs(entry_premium, exit_premium, qty, recorded_bid_ask_spread=0.80)

    # 1. Turnover verification
    buy_turnover = 200.0 * 65  # 13,000.0
    sell_turnover = 250.0 * 65  # 16,250.0
    total_turnover = buy_turnover + sell_turnover  # 29,250.0

    # 2. Hand-computed components
    expected_stt = round(sell_turnover * 0.0015, 2)  # 24.38
    expected_brokerage = 40.00
    expected_exchange = round(total_turnover * 0.0005, 2)  # 14.62 (half-to-even rounding of 14.625)
    expected_stamp = round(buy_turnover * 0.00003, 2)  # 0.39
    expected_ipft = round(total_turnover * 0.000001, 2)  # 0.03
    expected_sebi = round(total_turnover * 0.000001, 2)  # 0.03
    expected_gst_base = 40.0 + (total_turnover * 0.0005) + (total_turnover * 0.000001) + (total_turnover * 0.000001)
    expected_gst = round(expected_gst_base * 0.18, 2)  # 9.84
    expected_slippage = round(0.80 * 65, 2)  # 52.00

    assert res["stt"] == expected_stt == 24.38
    assert res["brokerage"] == expected_brokerage == 40.00
    assert res["exchange_charges"] == expected_exchange == 14.62
    assert res["stamp_duty"] == expected_stamp == 0.39
    assert res["ipft"] == expected_ipft == 0.03
    assert res["sebi_fee"] == expected_sebi == 0.03
    assert res["gst"] == expected_gst == 9.84
    assert res["slippage"] == expected_slippage == 52.00

    # 3. P&L verification
    expected_gross = (250.0 - 200.0) * 65  # 3,250.00
    expected_total_costs = round(
        expected_brokerage + expected_stt + expected_stamp + expected_exchange + expected_ipft + expected_sebi + expected_gst + expected_slippage,
        2
    )
    assert res["gross_pnl"] == expected_gross == 3250.00
    assert res["total_costs"] == 141.30 or res["total_costs"] == 141.29  # within 1 paisa rounding
    assert pytest.approx(res["net_pnl"], abs=0.1) == (expected_gross - expected_total_costs)

    # 4. Show verified rates map
    vr = res["verified_rates"]
    assert vr["stt_rate"] == 0.0015
    assert vr["brokerage_per_order"] == 20.0
    assert vr["exchange_rate"] == 0.0005
    assert vr["stamp_rate"] == 0.00003
    assert vr["ipft_rate"] == 0.000001
    assert vr["sebi_rate"] == 0.000001
    assert vr["gst_rate"] == 0.18


def test_hand_computed_options_recorded_spread_slippage() -> None:
    """Verify that paper trading slippage uses recorded bid-ask spread instead of fixed 1 pt."""
    from data.paper_trading import calculate_option_paper_costs

    qty = 50
    # Wide spread case (illiquid / fast market: bid=148.0, ask=150.5 => spread=2.5 pts)
    res_wide = calculate_option_paper_costs(150.0, 160.0, qty, recorded_bid_ask_spread=2.5)
    assert res_wide["slippage_pts"] == 2.5
    assert res_wide["slippage"] == 2.5 * 50  # 125.0
    assert res_wide["slippage_source"] == "recorded_bid_ask_spread"

    # Tight spread case (liquid ATM: bid=181.4, ask=181.7 => spread=0.30 pts)
    res_tight = calculate_option_paper_costs(181.5, 195.0, qty, recorded_bid_ask_spread=0.30)
    assert res_tight["slippage_pts"] == 0.30
    assert res_tight["slippage"] == 0.30 * 50  # 15.0
    assert res_tight["slippage_source"] == "recorded_bid_ask_spread"

    # Fallback case when spread is None
    res_default = calculate_option_paper_costs(181.5, 195.0, qty, recorded_bid_ask_spread=None)
    assert res_default["slippage_pts"] == 1.0
    assert res_default["slippage"] == 1.0 * 50  # 50.0
    assert res_default["slippage_source"] == "default_fallback_1pt"



