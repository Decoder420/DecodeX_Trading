"""Tests for BacktestEngine execution rules: no same-bar fills, open-gap fills, dual breach, and holdout guard."""

from __future__ import annotations

from datetime import date, datetime, timedelta
import numpy as np
import pandas as pd
import pytest
import pytz

from backtest.engine import BacktestEngine
from backtest.holdout import HoldoutGuardError, HoldoutManager
from models.base import SignalDirection


@pytest.fixture
def sample_market_df() -> pd.DataFrame:
    tz = pytz.timezone("Asia/Kolkata")
    base_date = datetime(2023, 1, 2, 9, 15, tzinfo=tz)
    n = 20

    timestamps = [base_date + timedelta(days=i) for i in range(n)]
    opens = [18000.0 + i * 20.0 for i in range(n)]
    highs = [o + 50.0 for o in opens]
    lows = [o - 50.0 for o in opens]
    closes = [o + 10.0 for o in opens]
    vols = [0.15] * n
    atrs = [100.0] * n

    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes,
            "volume": [500000.0] * n,
            "realized_vol_20": vols,
            "atr_14": atrs,
            "is_gap": [False] * n,
        }
    )


def test_no_same_bar_fill(sample_market_df: pd.DataFrame) -> None:
    """Verify signal at close of bar t enters at Open of bar t+1 (never same-bar fill)."""
    engine = BacktestEngine(starting_capital=1000000.0)
    n = len(sample_market_df)

    # Signal triggered at bar index 2 close
    directions = [SignalDirection.NO_TRADE.value] * n
    directions[2] = SignalDirection.BUY.value
    stops = [0.0] * n
    stops[2] = 17800.0
    targets = [0.0] * n
    targets[2] = 18500.0

    signals_df = pd.DataFrame(
        {
            "direction": directions,
            "confidence": [0.7] * n,
            "stop_loss": stops,
            "take_profit": targets,
            "reasons": ["TEST_SIGNAL"] * n,
            "margin": [0.3] * n,
        }
    )

    res = engine.run_backtest(sample_market_df, signals_df, symbol="NIFTY")
    assert len(res.trades) > 0
    first_trade = res.trades[0]

    # Entry date must match bar index 3, NOT bar index 2!
    signal_date = sample_market_df["timestamp"].iloc[2].date()
    entry_date = sample_market_df["timestamp"].iloc[3].date()
    assert first_trade.entry_date == entry_date
    assert first_trade.entry_date != signal_date
    # Entry price must match Open of bar 3
    assert first_trade.entry_price == sample_market_df["open"].iloc[3]


def test_open_gap_beyond_stop_fills_at_open(sample_market_df: pd.DataFrame) -> None:
    """If next open is beyond the stop price, fill at the Open price, NOT the stop price."""
    df = sample_market_df.copy()
    n = len(df)

    # Setup BUY trade at bar 1 (entered at bar 2 open: 18040.0)
    directions = [SignalDirection.NO_TRADE.value] * n
    directions[1] = SignalDirection.BUY.value
    stops = [0.0] * n
    stops[1] = 17950.0  # Stop price is 17950
    targets = [0.0] * n
    targets[1] = 18500.0

    signals_df = pd.DataFrame(
        {
            "direction": directions,
            "confidence": [0.7] * n,
            "stop_loss": stops,
            "take_profit": targets,
            "reasons": ["GAP_TEST"] * n,
            "margin": [0.3] * n,
        }
    )

    # Force adverse gap-down on bar 3 open to 17800.0 (well below stop of 17950.0)
    df.loc[3, "open"] = 17800.0
    df.loc[3, "high"] = 17850.0
    df.loc[3, "low"] = 17750.0
    df.loc[3, "close"] = 17820.0

    engine = BacktestEngine(starting_capital=1000000.0)
    res = engine.run_backtest(df, signals_df, symbol="NIFTY")

    assert len(res.trades) == 1
    trade = res.trades[0]
    assert trade.exit_reason == "GAP_STOP_LOSS"
    # MUST fill at open price (17800.0), NOT stop price (17950.0)
    assert trade.exit_price == 17800.0
    assert trade.exit_price != 17950.0


def test_open_gap_beyond_target_fills_at_open(sample_market_df: pd.DataFrame) -> None:
    """If next open is beyond target price, fill at the Open price, NOT the target price."""
    df = sample_market_df.copy()
    n = len(df)

    directions = [SignalDirection.NO_TRADE.value] * n
    directions[1] = SignalDirection.BUY.value
    stops = [0.0] * n
    stops[1] = 17900.0
    targets = [0.0] * n
    targets[1] = 18150.0  # Target price is 18150

    signals_df = pd.DataFrame(
        {
            "direction": directions,
            "confidence": [0.7] * n,
            "stop_loss": stops,
            "take_profit": targets,
            "reasons": ["GAP_TEST"] * n,
            "margin": [0.3] * n,
        }
    )

    # Force favorable gap-up on bar 3 open to 18300.0 (well above target of 18150.0)
    df.loc[3, "open"] = 18300.0
    df.loc[3, "high"] = 18350.0
    df.loc[3, "low"] = 18250.0
    df.loc[3, "close"] = 18320.0

    engine = BacktestEngine(starting_capital=1000000.0)
    res = engine.run_backtest(df, signals_df, symbol="NIFTY")

    assert len(res.trades) == 1
    trade = res.trades[0]
    assert trade.exit_reason == "GAP_PROFIT_TAKE"
    # MUST fill at open price (18300.0), NOT target price (18150.0)
    assert trade.exit_price == 18300.0


def test_conservative_dual_breach_assumes_stop_loss(sample_market_df: pd.DataFrame) -> None:
    """If both High >= Target and Low <= Stop occur in the same bar, assume stop was hit first."""
    df = sample_market_df.copy()
    n = len(df)

    directions = [SignalDirection.NO_TRADE.value] * n
    directions[1] = SignalDirection.BUY.value
    stops = [0.0] * n
    stops[1] = 17950.0
    targets = [0.0] * n
    targets[1] = 18150.0

    signals_df = pd.DataFrame(
        {
            "direction": directions,
            "confidence": [0.7] * n,
            "stop_loss": stops,
            "take_profit": targets,
            "reasons": ["DUAL_BREACH_TEST"] * n,
            "margin": [0.3] * n,
        }
    )

    # Bar 3 opens within range (18050), but expands to High 18200 (>= target) and Low 17900 (<= stop)
    df.loc[3, "open"] = 18050.0
    df.loc[3, "high"] = 18200.0
    df.loc[3, "low"] = 17900.0
    df.loc[3, "close"] = 18020.0

    engine = BacktestEngine(starting_capital=1000000.0)
    res = engine.run_backtest(df, signals_df, symbol="NIFTY")

    assert len(res.trades) == 1
    trade = res.trades[0]
    assert trade.exit_reason == "STOP_LOSS_CONSERVATIVE_DUAL"
    assert trade.exit_price == 17950.0  # Stop price executed


def test_holdout_guard_locking(tmp_path) -> None:
    """Holdout guard executes once and refuses a second run unless allow_override=True."""
    guard_file = tmp_path / "test_holdout_guard.json"
    mgr = HoldoutManager(guard_file_path=guard_file)

    assert not mgr.is_locked()

    def dummy_eval() -> dict:
        return {"sharpe": 1.45, "cagr": 18.2}

    # First run succeeds
    res1 = mgr.evaluate_holdout(dummy_eval, model_name="Model_Test")
    assert res1["sharpe"] == 1.45
    assert mgr.is_locked()

    # Second run without override must raise HoldoutGuardError
    with pytest.raises(HoldoutGuardError):
        mgr.evaluate_holdout(dummy_eval, model_name="Model_Test", allow_override=False)

    # Run with explicit override flag succeeds
    res2 = mgr.evaluate_holdout(dummy_eval, model_name="Model_Test", allow_override=True)
    assert res2["cagr"] == 18.2
