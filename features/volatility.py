"""Volatility features: ATR, Bollinger width, Realized Volatility, GARCH(1,1), and India VIX rank."""

from __future__ import annotations

import logging
from typing import Optional
import numpy as np
import pandas as pd
from arch import arch_model

logger = logging.getLogger(__name__)


def compute_atr(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int = 14,
) -> pd.Series:
    """Calculate Average True Range (ATR) using Wilder's smoothing."""
    prev_close = close.shift(1)
    tr = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1.0 / period, adjust=False).mean()
    return atr.rename(f"atr_{period}")


def compute_bollinger_bands(
    close: pd.Series,
    period: int = 20,
    num_std: float = 2.0,
) -> pd.DataFrame:
    """Calculate Bollinger Bands, Bandwidth, and %B."""
    mid = close.rolling(window=period, min_periods=period).mean()
    std = close.rolling(window=period, min_periods=period).std()

    upper = mid + (num_std * std)
    lower = mid - (num_std * std)
    bandwidth = (upper - lower) / mid.replace(0, np.nan)
    percent_b = (close - lower) / (upper - lower).replace(0, np.nan)

    return pd.DataFrame(
        {
            f"bb_mid_{period}": mid,
            f"bb_upper_{period}_{num_std}": upper,
            f"bb_lower_{period}_{num_std}": lower,
            f"bb_width_{period}_{num_std}": bandwidth,
            f"bb_pct_b_{period}_{num_std}": percent_b,
        },
        index=close.index,
    )


def compute_realized_volatility(
    close: pd.Series,
    window: int = 20,
    annualization_factor: int = 252,
) -> pd.Series:
    """Calculate rolling annualized realized volatility from log returns."""
    log_ret = np.log(close / close.shift(1))
    rolling_std = log_ret.rolling(window=window, min_periods=window).std()
    realized_vol = rolling_std * np.sqrt(annualization_factor)
    return realized_vol.rename(f"realized_vol_{window}")


def compute_garch_forecast(
    close: pd.Series,
    fit_window: int = 252,
    p: int = 1,
    q: int = 1,
    refit_step: int = 5,
) -> pd.Series:
    """Compute rolling one-step GARCH(p,q) conditional volatility forecast.

    Strictly causal: at index i, fits GARCH on returns up to i (window [i - fit_window + 1 : i + 1])
    and forecasts conditional sigma for the next step.
    Refitting is done periodically (every refit_step bars) to balance computational efficiency
    while preserving deterministic leak-free historical alignment.
    """
    returns = np.log(close / close.shift(1)).fillna(0.0) * 100.0  # Scale for optimizer stability
    n = len(returns)
    garch_forecast = pd.Series(np.nan, index=close.index, name=f"garch_{p}_{q}_vol")

    if n < fit_window:
        logger.warning(
            "Dataset length (%d) is shorter than GARCH fit_window (%d). Returning NaNs.",
            n,
            fit_window,
        )
        return garch_forecast

    cached_res = None
    last_fit_idx = -1

    for i in range(fit_window, n):
        # Determine whether to refit model
        if cached_res is None or (i - last_fit_idx) >= refit_step:
            window_returns = returns.iloc[i - fit_window + 1 : i + 1]
            try:
                am = arch_model(window_returns, vol="Garch", p=p, q=q, rescale=False)
                cached_res = am.fit(disp="off", show_warning=False)
                last_fit_idx = i
            except Exception as e:
                logger.debug("GARCH fit error at bar %d: %s", i, e)
                continue

        if cached_res is not None:
            try:
                # 1-step conditional variance forecast
                f = cached_res.forecast(horizon=1)
                var = f.variance.iloc[-1].values[0]
                # Scale back to standard return units
                garch_forecast.iloc[i] = (np.sqrt(var) / 100.0) * np.sqrt(252)
            except Exception:
                pass

    return garch_forecast


def compute_vix_features(
    vix_df: Optional[pd.DataFrame],
    target_timestamps: pd.Series,
    percentile_window: int = 252,
) -> pd.DataFrame:
    """Align India VIX level and calculate rolling historical percentile rank."""
    n = len(target_timestamps)
    res = pd.DataFrame(
        {
            "vix_close": np.nan,
            f"vix_pctile_{percentile_window}": np.nan,
        },
        index=target_timestamps.index,
    )

    if vix_df is None or vix_df.empty or "close" not in vix_df.columns:
        return res

    vix_sub = vix_df[["timestamp", "close"]].rename(columns={"close": "vix_close"}).copy()
    vix_sub["timestamp"] = pd.to_datetime(vix_sub["timestamp"]).astype("datetime64[ns, Asia/Kolkata]")
    target_df = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(target_timestamps).astype("datetime64[ns, Asia/Kolkata]"),
            "orig_idx": range(n),
        }
    )

    merged = pd.merge_asof(
        target_df.sort_values("timestamp"),
        vix_sub.sort_values("timestamp"),
        on="timestamp",
        direction="backward",
    ).sort_values("orig_idx")

    aligned_vix = merged["vix_close"].values
    res["vix_close"] = aligned_vix

    # Rolling percentile rank: fraction of past window values <= current value
    def _pctile_rank(window_vals: np.ndarray) -> float:
        if len(window_vals) == 0 or np.isnan(window_vals[-1]):
            return np.nan
        curr = window_vals[-1]
        valid = window_vals[~np.isnan(window_vals)]
        if len(valid) == 0:
            return np.nan
        return float(np.mean(valid <= curr)) * 100.0

    min_p = min(percentile_window, max(5, percentile_window // 4))
    rolling_pctile = (
        pd.Series(aligned_vix, index=res.index)
        .rolling(window=percentile_window, min_periods=min_p)
        .apply(_pctile_rank, raw=True)
    )

    res[f"vix_pctile_{percentile_window}"] = rolling_pctile
    return res
