"""Trend indicators: EMA, ADX, Supertrend, intraday VWAP, and Higher-High/Higher-Low structure."""

from __future__ import annotations

import logging
from typing import Dict, List, Optional
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def compute_ema(series: pd.Series, period: int) -> pd.Series:
    """Calculate Exponential Moving Average strictly using historical data."""
    return series.ewm(span=period, adjust=False).mean()


def compute_all_emas(series: pd.Series, periods: Optional[List[int]] = None) -> pd.DataFrame:
    """Calculate multiple EMAs (default: 9, 21, 50, 200)."""
    if periods is None:
        periods = [9, 21, 50, 200]
    res = pd.DataFrame(index=series.index)
    for p in periods:
        res[f"ema_{p}"] = compute_ema(series, p)
    return res


def compute_adx(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int = 14,
) -> pd.DataFrame:
    """Calculate Average Directional Index (ADX), +DI, and -DI."""
    prev_close = close.shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    up_move = high - high.shift(1)
    down_move = low.shift(1) - low

    pos_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    neg_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

    # Wilder's smoothing via ewm (alpha = 1 / period)
    alpha = 1.0 / period
    atr = tr.ewm(alpha=alpha, adjust=False).mean()
    pos_dm_smooth = pd.Series(pos_dm, index=high.index).ewm(alpha=alpha, adjust=False).mean()
    neg_dm_smooth = pd.Series(neg_dm, index=high.index).ewm(alpha=alpha, adjust=False).mean()

    pos_di = 100.0 * (pos_dm_smooth / atr.replace(0, np.nan))
    neg_di = 100.0 * (neg_dm_smooth / atr.replace(0, np.nan))

    dx = 100.0 * ((pos_di - neg_di).abs() / (pos_di + neg_di).replace(0, np.nan))
    adx = dx.ewm(alpha=alpha, adjust=False).mean()

    return pd.DataFrame(
        {
            f"adx_{period}": adx,
            f"plus_di_{period}": pos_di,
            f"minus_di_{period}": neg_di,
        },
        index=high.index,
    )


def compute_supertrend(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int = 10,
    multiplier: float = 3.0,
) -> pd.DataFrame:
    """Calculate Supertrend indicator strictly forward without future lookahead.

    Returns:
        pd.DataFrame with 'supertrend' and 'supertrend_direction' (1 = bullish, -1 = bearish).
    """
    prev_close = close.shift(1)
    tr = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1.0 / period, adjust=False).mean()

    hl2 = (high + low) / 2.0
    basic_ub = hl2 + (multiplier * atr)
    basic_lb = hl2 - (multiplier * atr)

    n = len(close)
    final_ub = np.zeros(n)
    final_lb = np.zeros(n)
    supertrend = np.zeros(n)
    direction = np.zeros(n, dtype=int)

    c_vals = close.values
    bub_vals = basic_ub.values
    blb_vals = basic_lb.values

    # Iterative forward pass: at step i, only step i and i-1 are referenced
    for i in range(n):
        if i == 0:
            final_ub[0] = bub_vals[0]
            final_lb[0] = blb_vals[0]
            direction[0] = 1 if c_vals[0] >= final_lb[0] else -1
            supertrend[0] = final_lb[0] if direction[0] == 1 else final_ub[0]
            continue

        # Final Upper Band
        if bub_vals[i] < final_ub[i - 1] or c_vals[i - 1] > final_ub[i - 1]:
            final_ub[i] = bub_vals[i]
        else:
            final_ub[i] = final_ub[i - 1]

        # Final Lower Band
        if blb_vals[i] > final_lb[i - 1] or c_vals[i - 1] < final_lb[i - 1]:
            final_lb[i] = blb_vals[i]
        else:
            final_lb[i] = final_lb[i - 1]

        # Trend direction
        if direction[i - 1] == 1:
            if c_vals[i] < final_lb[i]:
                direction[i] = -1
                supertrend[i] = final_ub[i]
            else:
                direction[i] = 1
                supertrend[i] = final_lb[i]
        else:
            if c_vals[i] > final_ub[i]:
                direction[i] = 1
                supertrend[i] = final_lb[i]
            else:
                direction[i] = -1
                supertrend[i] = final_ub[i]

    return pd.DataFrame(
        {
            f"supertrend_{period}_{multiplier}": supertrend,
            f"supertrend_direction_{period}_{multiplier}": direction,
        },
        index=close.index,
    )


def compute_vwap(df: pd.DataFrame, is_tradable_proxy: bool = False) -> pd.DataFrame:
    """Calculate Intraday VWAP and Price vs VWAP distance.

    NOTE: Indian index spot series (NIFTY 50, BANK NIFTY, SENSEX) have no traded volume.
    VWAP is computed only where volume exists (tradable futures proxy) and skipped for
    index series with a clear log message.
    """
    res = pd.DataFrame(
        {
            "vwap": np.nan,
            "price_vs_vwap_pct": np.nan,
        },
        index=df.index,
    )

    if not is_tradable_proxy or "volume" not in df.columns or (df["volume"] <= 0).all() or df["volume"].isna().all():
        logger.info(
            "Index series contains no traded volume; skipping VWAP calculation as intended."
        )
        return res

    typical_price = (df["high"] + df["low"] + df["close"]) / 3.0
    vol = df["volume"].fillna(0)

    # Intraday cumulative reset per date session
    date_group = df["timestamp"].dt.date
    cum_pv = (typical_price * vol).groupby(date_group).cumsum()
    cum_vol = vol.groupby(date_group).cumsum()

    vwap = cum_pv / cum_vol.replace(0, np.nan)
    res["vwap"] = vwap
    res["price_vs_vwap_pct"] = (df["close"] - vwap) / vwap * 100.0
    return res


def compute_hh_hl_structure(
    high: pd.Series,
    low: pd.Series,
    window: int = 5,
) -> pd.DataFrame:
    """Classify Higher High (HH) and Higher Low (HL) market structure.

    Evaluates swing highs and swing lows strictly using past window bars (causal).
    """
    rolling_max = high.rolling(window=window, min_periods=window).max()
    rolling_min = low.rolling(window=window, min_periods=window).min()

    # Swing high: current high equals the rolling max of past window bars
    is_swing_high = high == rolling_max
    is_swing_low = low == rolling_min

    # Higher high: swing high is higher than the previous swing high
    prev_swing_high = high.where(is_swing_high).ffill().shift(1)
    prev_swing_low = low.where(is_swing_low).ffill().shift(1)

    is_higher_high = (is_swing_high) & (high > prev_swing_high)
    is_higher_low = (is_swing_low) & (low > prev_swing_low)
    is_lower_high = (is_swing_high) & (high < prev_swing_high)
    is_lower_low = (is_swing_low) & (low < prev_swing_low)

    # Structural trend: +1 if last identified structure was HH/HL, -1 if LH/LL
    structure_signal = pd.Series(0, index=high.index)
    structure_signal.loc[is_higher_high | is_higher_low] = 1
    structure_signal.loc[is_lower_high | is_lower_low] = -1
    structure_trend = structure_signal.replace(0, np.nan).ffill().fillna(0).astype(int)

    return pd.DataFrame(
        {
            "is_higher_high": is_higher_high.astype(int),
            "is_higher_low": is_higher_low.astype(int),
            "is_lower_high": is_lower_high.astype(int),
            "is_lower_low": is_lower_low.astype(int),
            "market_structure_trend": structure_trend,
        },
        index=high.index,
    )
