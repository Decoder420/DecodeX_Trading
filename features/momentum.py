"""Momentum features: RSI, MACD, ROC, Stochastic Oscillator, and Rolling Return Z-score."""

from __future__ import annotations

import numpy as np
import pandas as pd


def compute_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """Calculate Relative Strength Index (RSI) using Wilder's smoothing."""
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    alpha = 1.0 / period
    avg_gain = gain.ewm(alpha=alpha, adjust=False).mean()
    avg_loss = loss.ewm(alpha=alpha, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100.0 - (100.0 / (1.0 + rs))
    return rsi.rename(f"rsi_{period}")


def compute_macd(
    close: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> pd.DataFrame:
    """Calculate Moving Average Convergence Divergence (MACD)."""
    fast_ema = close.ewm(span=fast, adjust=False).mean()
    slow_ema = close.ewm(span=slow, adjust=False).mean()
    macd_line = fast_ema - slow_ema
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line

    return pd.DataFrame(
        {
            f"macd_line_{fast}_{slow}": macd_line,
            f"macd_signal_{fast}_{slow}_{signal}": signal_line,
            f"macd_hist_{fast}_{slow}_{signal}": histogram,
        },
        index=close.index,
    )


def compute_roc(close: pd.Series, period: int = 10) -> pd.Series:
    """Calculate Rate of Change (ROC) in percentage."""
    roc = ((close - close.shift(period)) / close.shift(period).replace(0, np.nan)) * 100.0
    return roc.rename(f"roc_{period}")


def compute_stochastic(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    k_period: int = 14,
    d_period: int = 3,
) -> pd.DataFrame:
    """Calculate Fast and Slow Stochastic Oscillators (%K, %D)."""
    lowest_low = low.rolling(window=k_period, min_periods=k_period).min()
    highest_high = high.rolling(window=k_period, min_periods=k_period).max()

    denom = (highest_high - lowest_low).replace(0, np.nan)
    stoch_k = 100.0 * ((close - lowest_low) / denom)
    stoch_d = stoch_k.rolling(window=d_period, min_periods=d_period).mean()

    return pd.DataFrame(
        {
            f"stoch_k_{k_period}": stoch_k,
            f"stoch_d_{k_period}_{d_period}": stoch_d,
        },
        index=close.index,
    )


def compute_returns_zscore(close: pd.Series, window: int = 20) -> pd.Series:
    """Calculate rolling Z-score of simple log returns."""
    log_ret = np.log(close / close.shift(1))
    rolling_mean = log_ret.rolling(window=window, min_periods=window).mean()
    rolling_std = log_ret.rolling(window=window, min_periods=window).std()

    z_score = (log_ret - rolling_mean) / rolling_std.replace(0, np.nan)
    return z_score.rename(f"returns_zscore_{window}")
