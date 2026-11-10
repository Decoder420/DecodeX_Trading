"""Unit tests for Signal Labels, Direction Alignment, and Anti-Collision Guard."""

import pandas as pd
import pytest
from dashboard.tradingview_chart import build_tradingview_html
from signals.engine import IntradaySignalEngine, SignalState, TradeAction, TradePlan


def test_bullish_option_buying_signal_and_risk_sides():
    """Verify that bullish option buying is labeled BUY CE with correct SL/Target sides."""
    engine = IntradaySignalEngine("NIFTY")
    spot = 22700.0
    plan = engine.compute_signal(
        spot_price=spot,
        ema_21=22650.0,
        ema_50=22600.0,
        adx_14=30.0,
        atr_14=50.0,
        pcr_oi=1.35,
        account_equity=1000000.0,
    )

    # 1. State and Action
    assert plan.state in (SignalState.BUY, SignalState.STRONG_BUY)
    assert plan.action == TradeAction.BUY_CE
    assert "CE" in plan.suggested_strike
    assert "SELL" not in plan.action.value

    # 2. Underlying Spot Direction Sides: SL < Entry < T1 < T2
    assert plan.stop_loss < plan.spot_price, "Spot SL must be below spot entry for Bullish BUY CE"
    assert plan.target_1 > plan.spot_price, "Spot T1 must be above spot entry for Bullish BUY CE"
    assert plan.target_2 > plan.target_1, "Spot T2 must be above T1 for Bullish BUY CE"

    # 3. Option Premium Sides: Opt SL < Opt Entry < Opt T1 < Opt T2
    assert plan.option_entry_ltp > 0.0
    assert plan.option_stop_loss < plan.option_entry_ltp, "Option SL must be below option entry"
    assert plan.option_target_1 > plan.option_entry_ltp, "Option T1 must be above option entry"
    assert plan.option_target_2 > plan.option_target_1, "Option T2 must be above option T1"

    # 4. Telemetry Transparency
    assert plan.instrument == "NIFTY"
    assert len(plan.reasons) > 0


def test_bearish_option_buying_signal_and_risk_sides():
    """Verify that bearish option buying is labeled BUY PE (NEVER SELL PE) with correct SL/Target sides."""
    engine = IntradaySignalEngine("NIFTY")
    spot = 22700.0
    plan = engine.compute_signal(
        spot_price=spot,
        ema_21=22750.0,
        ema_50=22800.0,
        adx_14=30.0,
        atr_14=50.0,
        pcr_oi=0.65,
        account_equity=1000000.0,
    )

    # 1. State and Action: Must be BUY PE, NOT SELL PE!
    assert plan.state in (SignalState.SELL, SignalState.STRONG_SELL)
    assert plan.action == TradeAction.BUY_PE
    assert "PE" in plan.suggested_strike
    assert "SELL PE" not in plan.action.value
    assert "SELL CE" not in plan.action.value

    # 2. Underlying Spot Direction Sides: T2 < T1 < Entry < SL
    assert plan.stop_loss > plan.spot_price, "Spot SL must be ABOVE spot entry for Bearish BUY PE"
    assert plan.target_1 < plan.spot_price, "Spot T1 must be BELOW spot entry for Bearish BUY PE"
    assert plan.target_2 < plan.target_1, "Spot T2 must be BELOW T1 for Bearish BUY PE"

    # 3. Option Premium Sides: Put premium goes UP as underlying spot falls!
    # Opt SL < Opt Entry < Opt T1 < Opt T2
    assert plan.option_entry_ltp > 0.0
    assert plan.option_stop_loss < plan.option_entry_ltp, "Put Option SL must be below entry premium"
    assert plan.option_target_1 > plan.option_entry_ltp, "Put Option T1 must be above entry premium"
    assert plan.option_target_2 > plan.option_target_1, "Put Option T2 must be above option T1"

    # 4. Telemetry Transparency
    assert len(plan.reasons) > 0


def test_opposite_signal_collision_guard():
    """Verify that opposite signals (BUY CE and BUY PE) cannot overlap on the same candle bar."""
    engine = IntradaySignalEngine("NIFTY")
    plan = engine.compute_signal(spot_price=22700.0, ema_21=22650.0, ema_50=22600.0, atr_14=50.0)

    candles_df = pd.DataFrame([{
        "timestamp": "2026-10-28 10:30:00",
        "open": 22690.0, "high": 22710.0, "low": 22685.0, "close": 22700.0,
        "volume": 0.0, "source": "broker_history"
    }])

    # Simulated overlapping signal log containing both BUY CE and SELL/BUY PE at the same timestamp
    colliding_log = pd.DataFrame([
        {
            "Timestamp": "2026-10-28 10:30:00",
            "Signal": "BUY 22700 CE",
            "Strike": "22700 CE",
            "Direction": "BULLISH",
        },
        {
            "Timestamp": "2026-10-28 10:30:00",
            "Signal": "BUY 22500 PE",
            "Strike": "22500 PE",
            "Direction": "BEARISH",
        },
    ])

    html = build_tradingview_html(
        candles_df=candles_df,
        signal_log_df=colliding_log,
        plan=plan,
        spot_ltp=22700.0,
        max_pain=22700.0,
        instrument="NIFTY",
        timeframe="15m",
        is_stale=False,
    )

    # In markers payload, only one marker should exist for the timestamp, never both BUY CE and BUY PE overlapping
    # Check marker JSON
    import json, re
    match = re.search(r'const markersData = (\[.*?\]);', html, re.DOTALL)
    assert match is not None
    markers = json.loads(match.group(1))

    # All timestamps must be unique
    times = [m["time"] for m in markers]
    assert len(times) == len(set(times)), "Collision detected: Multiple markers on the exact same bar!"

    # Verify no SELL PE text in markers
    for m in markers:
        assert "SELL PE" not in m.get("text", "")
        assert "SELL CE" not in m.get("text", "")
