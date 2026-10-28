"""Target labeling methods (Triple Barrier & Forward Return Directions) strictly reserved for Part 2 modeling."""

from __future__ import annotations

import logging
from typing import List, Optional
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def compute_forward_returns(
    close: pd.Series,
    horizons: Optional[List[int]] = None,
    threshold: float = 0.0,
) -> pd.DataFrame:
    """Calculate forward return and direction for future horizons (target labeling).

    Note: These labels look forward into the future and MUST NOT be used as input features.
    """
    if horizons is None:
        horizons = [1, 3, 5]

    res = pd.DataFrame(index=close.index)
    for h in horizons:
        # Shift -h looks h steps ahead
        future_ret = (close.shift(-h) - close) / close
        direction = pd.Series(0, index=close.index)
        direction[future_ret > threshold] = 1
        direction[future_ret < -threshold] = -1
        # Trailing rows where future is unknown should be NaN
        direction[future_ret.isna()] = np.nan

        res[f"target_fwd_ret_{h}"] = future_ret
        res[f"target_dir_{h}"] = direction

    return res


def compute_triple_barrier_labels(
    df: pd.DataFrame,
    pt_atr_mult: float = 2.0,
    sl_atr_mult: float = 1.5,
    time_limit_bars: int = 10,
    atr_col: str = "atr_14",
) -> pd.DataFrame:
    """Compute Triple Barrier labeling outcome for each bar.

    Barriers:
    1. Upper barrier: entry_price + (pt_atr_mult * ATR) -> Label +1
    2. Lower barrier: entry_price - (sl_atr_mult * ATR) -> Label -1
    3. Vertical barrier: time_limit_bars -> Label 0

    Returns:
        DataFrame with ['tb_label', 'tb_barrier_hit', 'tb_holding_period', 'tb_return']
    """
    n = len(df)
    labels = np.full(n, np.nan)
    barrier_hit = np.full(n, "NONE", dtype=object)
    holding_period = np.full(n, np.nan)
    trade_returns = np.full(n, np.nan)

    if atr_col not in df.columns:
        from features.volatility import compute_atr
        atr = compute_atr(df["high"], df["low"], df["close"], period=14)
    else:
        atr = df[atr_col]

    close_vals = df["close"].values
    high_vals = df["high"].values
    low_vals = df["low"].values
    atr_vals = atr.values

    for i in range(n):
        entry_price = close_vals[i]
        curr_atr = atr_vals[i]

        if np.isnan(curr_atr) or curr_atr <= 0:
            continue

        upper_barrier = entry_price + (pt_atr_mult * curr_atr)
        lower_barrier = entry_price - (sl_atr_mult * curr_atr)
        max_horizon = min(i + time_limit_bars, n - 1)

        outcome_found = False
        for step in range(i + 1, max_horizon + 1):
            h_k = high_vals[step]
            l_k = low_vals[step]

            # Check if both barriers breached in same bar
            if h_k >= upper_barrier and l_k <= lower_barrier:
                # Conservative: assign stop loss hit
                labels[i] = -1
                barrier_hit[i] = "STOP_LOSS_DUAL"
                holding_period[i] = step - i
                trade_returns[i] = (lower_barrier - entry_price) / entry_price
                outcome_found = True
                break
            elif h_k >= upper_barrier:
                labels[i] = 1
                barrier_hit[i] = "PROFIT_TAKE"
                holding_period[i] = step - i
                trade_returns[i] = (upper_barrier - entry_price) / entry_price
                outcome_found = True
                break
            elif l_k <= lower_barrier:
                labels[i] = -1
                barrier_hit[i] = "STOP_LOSS"
                holding_period[i] = step - i
                trade_returns[i] = (lower_barrier - entry_price) / entry_price
                outcome_found = True
                break

        if not outcome_found:
            # Vertical barrier (time limit) reached
            if max_horizon > i:
                exit_price = close_vals[max_horizon]
                labels[i] = 0
                barrier_hit[i] = "TIME_LIMIT"
                holding_period[i] = max_horizon - i
                trade_returns[i] = (exit_price - entry_price) / entry_price
            else:
                # End of dataset
                labels[i] = np.nan
                barrier_hit[i] = "UNRESOLVED"

    return pd.DataFrame(
        {
            "tb_label": labels,
            "tb_barrier_hit": barrier_hit,
            "tb_holding_period": holding_period,
            "tb_return": trade_returns,
        },
        index=df.index,
    )
