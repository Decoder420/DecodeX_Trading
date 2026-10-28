"""Tests for WalkForwardEngine: non-overlapping splits, label purging, embargoing, and gap handling."""

from __future__ import annotations

from datetime import date, datetime, timedelta
import numpy as np
import pandas as pd
import pytest
import pytz

from backtest.walk_forward import WalkForwardEngine
from models.baselines import TrendFollowingModel
from signals.gates import TradeGatekeeper


@pytest.fixture
def multi_year_df() -> pd.DataFrame:
    """Generate 10 years of synthetic daily data for walk-forward testing (2012 to 2022)."""
    tz = pytz.timezone("Asia/Kolkata")
    base_date = datetime(2012, 1, 2, 9, 15, tzinfo=tz)
    n = 2600

    timestamps = []
    curr = base_date
    while len(timestamps) < n:
        if curr.weekday() < 5:
            timestamps.append(curr)
        curr += timedelta(days=1)

    prices = 10000.0 + np.cumsum(np.random.normal(2.0, 50.0, n))
    opens = prices
    highs = prices + 40.0
    lows = prices - 40.0
    closes = prices + 5.0
    vols = np.full(n, 0.15)
    atrs = np.full(n, 80.0)

    # Flag some gaps intentionally
    is_gap = np.zeros(n, dtype=bool)
    is_gap[500] = True
    is_gap[1200] = True

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
            "is_gap": is_gap,
            "regime_label": ["TRENDING"] * n,
            "vix_pctile_252": [50.0] * n,
            "is_expiry_day": [False] * n,
            "days_to_expiry": [3] * n,
        }
    )


def test_walk_forward_splits_never_overlap_and_purge_applied(multi_year_df: pd.DataFrame) -> None:
    """Prove train and test folds never overlap and train ends purge_bars before test."""
    purge_bars = 10
    engine = WalkForwardEngine(burn_in_bars=252, purge_bars=purge_bars)
    folds = engine.generate_folds(multi_year_df)

    assert len(folds) > 0

    for fold in folds:
        train_end_date = fold.train_end_purged
        test_start_date = fold.test_start

        # Train end must be strictly before test start
        assert train_end_date < test_start_date, (
            f"Fold {fold.fold_id} train end ({train_end_date}) >= test start ({test_start_date})"
        )

        # Check that fold.purged_bars_count is 10
        assert fold.purged_bars_count == purge_bars

        # Check timestamps set intersection is empty
        train_ts = set(fold.train_df["timestamp"])
        test_ts = set(fold.test_df["timestamp"])
        overlap = train_ts.intersection(test_ts)
        assert len(overlap) == 0, f"Found {len(overlap)} overlapping timestamps in fold {fold.fold_id}!"


def test_flagged_gap_handling_excludes_trading(multi_year_df: pd.DataFrame) -> None:
    """Signals on or immediately following a flagged gap date must be converted to NO_TRADE."""
    gate = TradeGatekeeper(min_confidence=0.50, gap_lookback_bars=2)
    model = TrendFollowingModel()

    # Create dummy signals where every bar has a BUY signal
    n = len(multi_year_df)
    dummy_signals = pd.DataFrame(
        {
            "direction": ["BUY"] * n,
            "confidence": [0.8] * n,
            "suggested_entry": multi_year_df["close"].values,
            "stop_loss": multi_year_df["close"].values - 100.0,
            "take_profit": multi_year_df["close"].values + 150.0,
            "reasons": ["ALL_BUY"] * n,
            "margin": [0.4] * n,
        }
    )

    filtered, audit = gate.apply_gates(multi_year_df, dummy_signals)

    # Gap at index 500 and 1200 must be dropped
    assert filtered["direction"].iloc[500] == "NO_TRADE"
    assert "GATE_GAP_DROPPED" in filtered["reasons"].iloc[500]
    # Lookback 1 bar after gap must also be dropped
    assert filtered["direction"].iloc[501] == "NO_TRADE"
    assert audit.dropped_by_gap >= 2
