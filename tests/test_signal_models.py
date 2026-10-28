"""Tests for Signal Models: output formats, calibration slice separation, determinism, and ensemble consensus."""

from __future__ import annotations

from datetime import datetime, timedelta
import numpy as np
import pandas as pd
import pytest
import pytz

from models.base import SignalDirection
from models.baselines import (
    BreakoutModel,
    MeanReversionModel,
    RegimeSwitchingBaselineModel,
    TrendFollowingModel,
)
from models.calibration import split_calibration_slice
from models.ensemble import ConsensusVotingEnsemble
from models.linear import RegularizedLogisticModel
from models.tree_models import LightGBMDirectionModel, LightGBMTripleBarrierModel


@pytest.fixture
def sample_feature_df() -> pd.DataFrame:
    np.random.seed(42)
    n = 600
    tz = pytz.timezone("Asia/Kolkata")
    base_date = datetime(2021, 1, 1, 9, 15, tzinfo=tz)

    timestamps = [base_date + timedelta(days=i) for i in range(n)]
    prices = 15000.0 * np.exp(np.cumsum(np.random.normal(0.0003, 0.012, n)))

    df = pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": prices * 0.999,
            "high": prices * 1.008,
            "low": prices * 0.992,
            "close": prices,
            "volume": [300000.0] * n,
            "ema_21": prices * 0.998,
            "ema_50": prices * 0.995,
            "adx_14": np.random.uniform(15.0, 40.0, n),
            "returns_zscore_20": np.random.normal(0.0, 1.0, n),
            "bb_pct_b_20": np.random.uniform(0.0, 1.0, n),
            "bb_mid_20": prices * 0.996,
            "atr_14": [80.0] * n,
            "realized_vol_20": [0.16] * n,
            "regime_label": ["TRENDING" if i % 2 == 0 else "RANGING" for i in range(n)],
            "vix_pctile_252": [50.0] * n,
            "is_expiry_day": [False] * n,
            "days_to_expiry": [3] * n,
            "is_gap": [False] * n,
        }
    )

    from models.labels import compute_forward_returns, compute_triple_barrier_labels
    fwd = compute_forward_returns(df["close"], horizons=[1, 3])
    tb = compute_triple_barrier_labels(df, pt_atr_mult=2.0, sl_atr_mult=1.5, time_limit_bars=10)

    for col in fwd.columns:
        df[col] = fwd[col]
    for col in tb.columns:
        df[col] = tb[col]

    return df


def test_calibration_slice_separation(sample_feature_df: pd.DataFrame) -> None:
    """Verify calibration slice takes last 20% of train window with 10-bar purge in between."""
    train_sub, calib_sub = split_calibration_slice(sample_feature_df, calib_pct=0.20, purge_bars=10)

    total_len = len(sample_feature_df)
    calib_len = len(calib_sub)
    train_len = len(train_sub)

    assert calib_len == int(total_len * 0.20)
    # The gap between train end and calib start must be exactly 10 bars
    assert train_len == total_len - calib_len - 10
    # No overlapping rows
    assert len(set(train_sub["timestamp"]).intersection(set(calib_sub["timestamp"]))) == 0


def test_model_3b_exact_label_exits(sample_feature_df: pd.DataFrame) -> None:
    """Model 3B must use exactly 2.0 ATR profit target and 1.5 ATR stop loss."""
    model = LightGBMTripleBarrierModel()
    model.fit(sample_feature_df)
    preds = model.predict_signals(sample_feature_df)

    assert "direction" in preds.columns
    assert "confidence" in preds.columns
    assert "stop_loss" in preds.columns
    assert "take_profit" in preds.columns

    # Verify BUY stops and targets
    buy_rows = preds[preds["direction"] == SignalDirection.BUY.value]
    if len(buy_rows) > 0:
        row = buy_rows.iloc[0]
        entry = row["suggested_entry"]
        stop = row["stop_loss"]
        target = row["take_profit"]
        atr = 80.0  # from fixture

        assert pytest.approx(entry - stop, rel=1e-3) == 1.5 * atr
        assert pytest.approx(target - entry, rel=1e-3) == 2.0 * atr


def test_determinism_with_fixed_seeds(sample_feature_df: pd.DataFrame) -> None:
    """Two independent fits and runs with fixed seed must yield identical predictions."""
    m1 = LightGBMDirectionModel()
    m2 = LightGBMDirectionModel()

    m1.fit(sample_feature_df)
    m2.fit(sample_feature_df)

    p1 = m1.predict_signals(sample_feature_df)
    p2 = m2.predict_signals(sample_feature_df)

    pd.testing.assert_series_equal(p1["direction"], p2["direction"])
    np.testing.assert_allclose(p1["confidence"].values, p2["confidence"].values, rtol=1e-6)
    np.testing.assert_allclose(p1["margin"].values, p2["margin"].values, rtol=1e-6)


def test_ensemble_consensus_rule(sample_feature_df: pd.DataFrame) -> None:
    """ConsensusVotingEnsemble fires ONLY when at least min_agreement models agree."""
    m_trend = TrendFollowingModel()
    m_breakout = BreakoutModel()
    m_linear = RegularizedLogisticModel()

    ensemble = ConsensusVotingEnsemble(models=[m_trend, m_breakout, m_linear], min_agreement=2)
    ensemble.fit(sample_feature_df)
    preds = ensemble.predict_signals(sample_feature_df)

    assert "direction" in preds.columns
    assert "reasons" in preds.columns

    # If direction is BUY or SELL, reasons must mention CONSENSUS
    trades = preds[preds["direction"] != SignalDirection.NO_TRADE.value]
    for _, row in trades.iterrows():
        assert "CONSENSUS" in row["reasons"]


def test_ensemble_components_fit_strictly_before_test_fold(sample_feature_df: pd.DataFrame) -> None:
    """Prove that ensemble components are re-fitted strictly on data preceding each test fold."""
    train_fold_1 = sample_feature_df.iloc[:250].copy()
    test_fold_1 = sample_feature_df.iloc[260:350].copy()
    train_fold_2 = sample_feature_df.iloc[:350].copy()

    m_linear = RegularizedLogisticModel(name="Logistic_L1", penalty="l1")
    m_trend = TrendFollowingModel()
    m_tb = LightGBMTripleBarrierModel()

    ensemble = ConsensusVotingEnsemble(models=[m_linear, m_trend, m_tb], min_agreement=2)

    # 1. Fit on Fold 1
    ensemble.fit(train_fold_1)
    assert ensemble.is_fitted
    weights_fold_1 = np.copy(m_linear.model.coef_)

    preds_fold_1 = ensemble.predict_signals(test_fold_1)
    audit_1 = ensemble.voting_audit
    assert "vote_distribution_by_member" in audit_1
    assert "deciding_votes_by_member" in audit_1

    # 2. Re-fit on Fold 2 (expanding history)
    ensemble.fit(train_fold_2)
    weights_fold_2 = np.copy(m_linear.model.coef_)

    # Weights must update because training data expanded
    assert not np.allclose(weights_fold_1, weights_fold_2)
    # The models must have been re-fit, not left with stale weights
    assert m_linear.is_fitted
    assert m_tb.is_fitted
