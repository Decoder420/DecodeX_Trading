"""Pytest verifying strict absence of lookahead bias across all features including GARCH and HMM regime.

Strengthened for 1,000+ rows, 5+ truncation cutoffs, and complete overlapping row comparisons.
"""

from __future__ import annotations

from datetime import datetime, timedelta
import numpy as np
import pandas as pd
import pytest
import pytz

from config.loader import ConfigManager
from features.pipeline import FeaturePipeline


@pytest.fixture
def synthetic_1000_bars() -> pd.DataFrame:
    """Generate realistic synthetic OHLCV time series of 1,050 bars with fixed seed."""
    np.random.seed(42)
    n = 1050
    tz = pytz.timezone("Asia/Kolkata")
    base_date = datetime(2020, 1, 1, 9, 15, tzinfo=tz)

    timestamps = []
    curr = base_date
    while len(timestamps) < n:
        if curr.weekday() < 5:
            timestamps.append(curr)
        curr += timedelta(days=1)

    # Geometric random walk with drift and volatility clustering
    ret = np.random.normal(0.0004, 0.011, n)
    # High-volatility cluster
    ret[200:300] = np.random.normal(-0.001, 0.024, 100)
    ret[600:700] = np.random.normal(0.0008, 0.020, 100)

    prices = 12000.0 * np.exp(np.cumsum(ret))

    opens = prices * (1.0 + np.random.normal(0, 0.0015, n))
    highs = np.maximum(opens, prices) * (1.0 + np.abs(np.random.normal(0.002, 0.0015, n)))
    lows = np.minimum(opens, prices) * (1.0 - np.abs(np.random.normal(0.002, 0.0015, n)))
    closes = prices
    volumes = np.random.randint(150000, 800000, n).astype(float)

    df = pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes,
            "volume": volumes,
        }
    )
    return df


OPTIMIZER_COLS = {
    "garch_1_1_vol",
    "prob_trending",
    "prob_ranging",
    "prob_high_vol",
}


@pytest.mark.parametrize("cutoff_idx", [650, 750, 850, 925, 1000])
def test_comprehensive_lookahead_leakage_multi_cutoff(
    synthetic_1000_bars: pd.DataFrame,
    cutoff_idx: int,
) -> None:
    """Prove strict absence of lookahead leakage across 1,000+ rows and multiple truncation points.

    Asserts that for EVERY row i in [0 ... cutoff_idx] and for ALL feature columns,
    computing on the full dataset yields mathematically identical values to computing
    strictly on the truncated dataset. Non-optimizer features are verified to 1e-8 tolerance.
    """
    cfg = ConfigManager()
    pipeline = FeaturePipeline(cfg)

    full_df = synthetic_1000_bars.copy()
    truncated_df = synthetic_1000_bars.iloc[: cutoff_idx + 1].copy()

    # Synthetic aligned VIX series
    vix_close = 15.0 + np.sin(np.linspace(0, 20, len(full_df))) * 4.0
    vix_full = pd.DataFrame(
        {
            "timestamp": full_df["timestamp"],
            "open": vix_close,
            "high": vix_close + 0.5,
            "low": vix_close - 0.5,
            "close": vix_close,
            "volume": 0.0,
        }
    )
    vix_trunc = vix_full.iloc[: cutoff_idx + 1].copy()

    # Compute features on full dataset
    feat_full = pipeline.compute_all_features(
        df=full_df,
        instrument="NIFTY",
        vix_df=vix_full,
        include_garch=True,
        include_regime=True,
        include_mean_reversion=True,
    )

    # Compute features on truncated dataset (strictly no future data available)
    feat_trunc = pipeline.compute_all_features(
        df=truncated_df,
        instrument="NIFTY",
        vix_df=vix_trunc,
        include_garch=True,
        include_regime=True,
        include_mean_reversion=True,
    )

    assert len(feat_trunc) == cutoff_idx + 1

    # Compare ALL overlapping rows (0 to cutoff_idx)
    overlap_full = feat_full.iloc[: cutoff_idx + 1]
    overlap_trunc = feat_trunc.iloc[: cutoff_idx + 1]

    # Non-numeric columns to compare separately
    cat_cols = ["regime_label", "market_structure_trend"]
    for col in cat_cols:
        if col in overlap_full.columns:
            mismatches = (overlap_full[col] != overlap_trunc[col]).sum()
            assert mismatches == 0, (
                f"Categorical feature '{col}' had {mismatches} mismatches "
                f"at cutoff {cutoff_idx} across overlapping rows."
            )

    # Compare all numeric columns across all overlapping rows
    excluded = set(cat_cols + ["timestamp", "updated_at"])
    numeric_cols = [
        c
        for c in overlap_full.columns
        if c not in excluded and pd.api.types.is_numeric_dtype(overlap_full[c])
    ]

    for col in numeric_cols:
        series_full = overlap_full[col].values
        series_trunc = overlap_trunc[col].values

        nan_mask_full = pd.isna(series_full)
        nan_mask_trunc = pd.isna(series_trunc)

        # Assert NaNs / nulls match exactly
        assert np.array_equal(nan_mask_full, nan_mask_trunc), (
            f"NaN pattern mismatch in feature '{col}' at cutoff {cutoff_idx}!"
        )

        if pd.api.types.is_bool_dtype(overlap_full[col]):
            assert np.array_equal(series_full, series_trunc), (
                f"Boolean mismatch in feature '{col}' at cutoff {cutoff_idx}!"
            )
            continue

        valid_mask = ~nan_mask_full
        if np.any(valid_mask):
            diff = np.abs(series_full[valid_mask] - series_trunc[valid_mask])
            max_diff = np.max(diff)

            # Strict 1e-8 tolerance for deterministic analytic features; 1e-4 for numerical optimizers
            tol = 1e-4 if col in OPTIMIZER_COLS else 1e-8
            assert max_diff < tol, (
                f"Lookahead leak detected in feature '{col}' at cutoff {cutoff_idx}! "
                f"Max absolute discrepancy: {max_diff:.6e} (tolerance: {tol})"
            )


def test_lookahead_on_real_data_slice() -> None:
    """Test lookahead leakage prevention on a real historical data slice (1,000 bars) from DuckDB."""
    from data.storage import StorageManager

    sm = StorageManager()
    df_real = sm.load_ohlcv("BANKNIFTY", "1d")
    vix_real = sm.load_ohlcv("INDIA_VIX", "1d")

    if len(df_real) < 1000:
        pytest.skip("Insufficient real data in storage for 1,000-bar test")

    real_1000 = df_real.iloc[:1000].copy().reset_index(drop=True)
    cutoff = 750

    cfg = ConfigManager()
    pipeline = FeaturePipeline(cfg)

    feat_full = pipeline.compute_all_features(
        df=real_1000,
        instrument="BANKNIFTY",
        vix_df=vix_real,
        include_garch=True,
        include_regime=True,
        include_mean_reversion=True,
    )

    feat_trunc = pipeline.compute_all_features(
        df=real_1000.iloc[: cutoff + 1].copy().reset_index(drop=True),
        instrument="BANKNIFTY",
        vix_df=vix_real,
        include_garch=True,
        include_regime=True,
        include_mean_reversion=True,
    )

    overlap_full = feat_full.iloc[: cutoff + 1]
    overlap_trunc = feat_trunc.iloc[: cutoff + 1]

    # Verify categorical features
    for col in ["regime_label", "market_structure_trend"]:
        if col in overlap_full.columns:
            mismatches = (overlap_full[col] != overlap_trunc[col]).sum()
            assert mismatches == 0, f"Mismatch in real data slice feature {col}"

    # Verify numeric features with strict tolerance
    excluded = {"regime_label", "market_structure_trend", "timestamp", "updated_at"}
    numeric_cols = [
        c
        for c in overlap_full.columns
        if c not in excluded and pd.api.types.is_numeric_dtype(overlap_full[c])
    ]

    for col in numeric_cols:
        series_full = overlap_full[col].values
        series_trunc = overlap_trunc[col].values

        nan_mask_full = pd.isna(series_full)
        nan_mask_trunc = pd.isna(series_trunc)
        assert np.array_equal(nan_mask_full, nan_mask_trunc), f"NaN mismatch on real data in {col}"

        if pd.api.types.is_bool_dtype(overlap_full[col]):
            assert np.array_equal(series_full, series_trunc), f"Boolean mismatch on real data in {col}"
            continue

        valid_mask = ~nan_mask_full
        if np.any(valid_mask):
            diff = np.abs(series_full[valid_mask] - series_trunc[valid_mask])
            max_diff = np.max(diff)
            tol = 1e-4 if col in OPTIMIZER_COLS else 1e-8
            assert max_diff < tol, (
                f"Leakage in real data slice on '{col}': max diff {max_diff:.6e} > {tol}"
            )
