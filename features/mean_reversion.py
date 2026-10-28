"""Mean reversion features: distance from moving average in ATR units, rolling Hurst exponent, and rolling ADF p-value."""

from __future__ import annotations

import logging
import numpy as np
import pandas as pd
from statsmodels.tsa.stattools import adfuller

from features.volatility import compute_atr

logger = logging.getLogger(__name__)


def compute_distance_from_ma_atr(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    ma_period: int = 20,
    atr_period: int = 14,
) -> pd.Series:
    """Calculate normalized distance from moving average in ATR units: (close - MA) / ATR."""
    ma = close.rolling(window=ma_period, min_periods=ma_period).mean()
    atr = compute_atr(high, low, close, period=atr_period)
    dist = (close - ma) / atr.replace(0, np.nan)
    return dist.rename(f"dist_ma_{ma_period}_atr_{atr_period}")


def calculate_hurst_exponent(series: np.ndarray, max_lags: int = 20) -> float:
    """Estimate Hurst exponent H using Rescaled Range (R/S) analysis.

    H < 0.5: Mean-reverting
    H = 0.5: Random walk / Brownian motion
    H > 0.5: Trending / Persistent
    """
    if len(series) < max_lags * 2:
        return np.nan

    lags = range(2, max_lags)
    tau = []
    for lag in lags:
        # Array of differences over lag
        diff = series[lag:] - series[:-lag]
        tau.append(np.std(diff))

    if len(tau) < 2 or any(t <= 0 or np.isnan(t) for t in tau):
        return np.nan

    # Fit line: log(tau) = H * log(lag) + c
    log_lags = np.log(list(lags))
    log_tau = np.log(tau)
    poly = np.polyfit(log_lags, log_tau, 1)
    hurst = poly[0]
    return float(np.clip(hurst, 0.0, 1.0))


def compute_rolling_hurst(close: pd.Series, window: int = 100) -> pd.Series:
    """Calculate rolling Hurst exponent strictly using past window bars."""
    hurst_series = pd.Series(np.nan, index=close.index, name=f"hurst_{window}")
    vals = close.values

    for i in range(window - 1, len(vals)):
        sub = vals[i - window + 1 : i + 1]
        hurst_series.iloc[i] = calculate_hurst_exponent(sub)

    return hurst_series


def compute_rolling_adf(close: pd.Series, window: int = 60) -> pd.Series:
    """Calculate rolling Augmented Dickey-Fuller (ADF) test p-value.

    p-value < 0.05 indicates stationarity (mean reversion).
    """
    adf_series = pd.Series(np.nan, index=close.index, name=f"adf_pvalue_{window}")
    vals = close.values

    for i in range(window - 1, len(vals)):
        sub = vals[i - window + 1 : i + 1]
        try:
            # maxlag=1 for speed in rolling context
            try:
                res = adfuller(sub, maxlag=1, autolag=None, result_object=False)
            except TypeError:
                res = adfuller(sub, maxlag=1, autolag=None)
            adf_series.iloc[i] = res[1]  # p-value
        except Exception:
            adf_series.iloc[i] = np.nan

    return adf_series
