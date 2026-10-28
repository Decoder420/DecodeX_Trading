"""Unit tests for IntradaySignalEngine and TradePlan generation."""

import pytest
from signals.engine import IntradaySignalEngine, SignalState, TradeAction


def test_bullish_signal_generation():
    engine = IntradaySignalEngine("NIFTY")
    plan = engine.compute_signal(
        spot_price=22710.0,
        ema_21=22680.0,
        ema_50=22640.0,
        adx_14=28.5,
        atr_14=120.0,
        pcr_oi=1.28,
        max_pain=22750.0,
        futures_basis=52.0,
        account_equity=1000000.0,
        risk_pct=1.0,
        atr_multiplier=1.5,
    )

    assert plan.state in [SignalState.BUY, SignalState.STRONG_BUY]
    assert plan.action == TradeAction.BUY_CE
    assert "CE" in plan.suggested_strike
    assert plan.stop_loss < plan.spot_price
    assert plan.target_1 > plan.spot_price
    assert plan.target_2 > plan.target_1
    assert plan.lots >= 1
    assert plan.quantity == plan.lots * 65


def test_bearish_signal_generation():
    engine = IntradaySignalEngine("NIFTY")
    plan = engine.compute_signal(
        spot_price=22550.0,
        ema_21=22620.0,
        ema_50=22680.0,
        adx_14=31.0,
        atr_14=140.0,
        pcr_oi=0.72,
        max_pain=22450.0,
        futures_basis=-10.0,
        account_equity=1000000.0,
        risk_pct=1.0,
        atr_multiplier=1.5,
    )

    assert plan.state in [SignalState.SELL, SignalState.STRONG_SELL]
    assert plan.action == TradeAction.BUY_PE
    assert "PE" in plan.suggested_strike
    assert plan.stop_loss > plan.spot_price
    assert plan.target_1 < plan.spot_price
    assert plan.target_2 < plan.target_1
    assert plan.lots >= 1


def test_neutral_signal_generation():
    engine = IntradaySignalEngine("NIFTY")
    plan = engine.compute_signal(
        spot_price=22650.0,
        ema_21=22648.0,
        ema_50=22652.0,
        adx_14=18.0,  # weak ADX
        atr_14=100.0,
        pcr_oi=1.02,  # neutral PCR
        max_pain=22650.0,
        account_equity=1000000.0,
    )

    assert plan.state == SignalState.NEUTRAL
    assert plan.action == TradeAction.WAIT
    assert plan.lots == 0


def test_banknifty_lot_size_and_strikes():
    engine = IntradaySignalEngine("BANKNIFTY")
    assert engine.lot_size == 30
    assert engine.strike_step == 100.0

    plan = engine.compute_signal(
        spot_price=54350.0,
        ema_21=54200.0,
        ema_50=54100.0,
        adx_14=27.0,
        atr_14=350.0,
        pcr_oi=1.20,
        max_pain=54500.0,
        account_equity=500000.0,
        risk_pct=1.5,
    )
    assert "CE" in plan.suggested_strike
    assert plan.quantity % 30 == 0


def test_entry_range_property_and_formatting():
    engine = IntradaySignalEngine("NIFTY")
    plan = engine.compute_signal(
        spot_price=22700.0,
        ema_21=22680.0,
        ema_50=22650.0,
        adx_14=26.0,
        atr_14=100.0,
    )
    assert hasattr(plan, "entry_range")
    assert "₹" in plan.entry_range
    assert "–" in plan.entry_range
    assert f"{plan.entry_min:,.2f}" in plan.entry_range
    assert f"{plan.entry_max:,.2f}" in plan.entry_range


def test_3stage_profit_locking_state_machine():
    """Verify 3-Stage Dynamic Profit-Locking: Stage 0 (Initial) -> Stage 1 (Breakeven @ 50% T1) -> Stage 2 (Profit Trail @ T1)."""
    from dashboard.intraday_data import get_live_multi_day_candles

    engine = IntradaySignalEngine("NIFTY")
    candles = get_live_multi_day_candles(instrument="NIFTY", timeframe="15m", date_str="2026-10-26", live_ltp=22753.2)

    # 1. Stage 0: Initial Risk
    plan_st0 = engine.compute_6factor_signal(candles_df=candles, timeframe="15m", live_mfe_pts=0.0)
    assert plan_st0.stage == 0
    assert "STAGE 0" in plan_st0.stage_label
    assert plan_st0.trailing_sl == plan_st0.stop_loss

    # T1 distance in pts
    t1_dist = abs(plan_st0.target_1 - plan_st0.spot_price)

    # 2. Stage 1: Breakeven Lock when MFE >= 50% of T1
    half_t1_mfe = t1_dist * 0.55
    plan_st1 = engine.compute_6factor_signal(candles_df=candles, timeframe="15m", live_mfe_pts=half_t1_mfe)
    assert plan_st1.stage == 1
    assert "STAGE 1" in plan_st1.stage_label
    assert "BREAKEVEN" in plan_st1.stage_label
    assert plan_st1.trailing_sl == plan_st1.spot_price

    # 3. Stage 2: Profit Trail when MFE >= 100% of T1
    full_t1_mfe = t1_dist * 1.05
    plan_st2 = engine.compute_6factor_signal(candles_df=candles, timeframe="15m", live_mfe_pts=full_t1_mfe)
    assert plan_st2.stage == 2
    assert "STAGE 2" in plan_st2.stage_label
    assert "PROFIT TRAIL" in plan_st2.stage_label
    # In BUY, trailing SL should be above entry price (profit locked)
    if plan_st2.state in [SignalState.BUY, SignalState.STRONG_BUY]:
        assert plan_st2.trailing_sl >= plan_st2.spot_price


def test_small_account_guardrail_mismatch():
    """Verify small-account ₹500 risk mismatch against 15m ATR structural SL triggers guardrail."""
    from dashboard.intraday_data import get_live_multi_day_candles

    engine = IntradaySignalEngine("NIFTY")
    candles_15m = get_live_multi_day_candles(instrument="NIFTY", timeframe="15m", date_str="2026-10-26", live_ltp=22753.2)

    # ₹50,000 equity @ 1% risk = ₹500 max rupee risk
    plan = engine.compute_6factor_signal(
        candles_df=candles_15m,
        timeframe="15m",
        account_equity=50000.0,
        risk_pct=1.0,
    )

    assert plan.is_account_risk_mismatch is True
    assert plan.max_risk_inr == 500.0
    assert plan.hard_capital_sl > 0.0
    assert "Scalping" in plan.mismatch_tip
    assert "1m or 3m" in plan.mismatch_tip


def test_6factor_confluence_and_historical_backtest():
    """Verify historical backtest win-rate, profit factor, expectancy telemetry across multi-day candles."""
    from dashboard.intraday_data import get_live_multi_day_candles

    engine = IntradaySignalEngine("NIFTY")
    candles = get_live_multi_day_candles(instrument="NIFTY", timeframe="15m", date_str="2026-10-26", live_ltp=22753.2)
    stats, markers = engine.evaluate_historical_backtest(candles, timeframe="15m")

    assert "win_rate_pct" in stats
    assert "profit_factor" in stats
    assert "expectancy_pts" in stats
    assert "total_trades" in stats
    assert stats["total_trades"] >= 1
    assert stats["win_rate_pct"] >= 0.0
    assert len(markers) >= 1
    # Markers have lightweight-charts format
    assert "time" in markers[0]
    assert "position" in markers[0]
    assert "color" in markers[0]

