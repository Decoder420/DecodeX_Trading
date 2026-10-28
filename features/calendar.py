"""Calendar and session features: day of week, expiry flags, days to expiry, gap size, and month-end."""

from __future__ import annotations

from datetime import date
from typing import Optional
import numpy as np
import pandas as pd

from config.loader import ConfigManager, config_manager


def compute_calendar_features(
    df: pd.DataFrame,
    instrument: str,
    cfg: Optional[ConfigManager] = None,
) -> pd.DataFrame:
    """Calculate date-aware calendar features including time-varying expiry tracking.

    Args:
        df: DataFrame with datetime 'timestamp', 'open', 'high', 'low', 'close'
        instrument: Canonical instrument key (e.g. 'NIFTY', 'BANKNIFTY', 'SENSEX')
        cfg: Optional ConfigManager instance.
    """
    c_mgr = cfg or config_manager
    ts = pd.to_datetime(df["timestamp"])
    res = pd.DataFrame(index=df.index)

    # 1. Day of week (0 = Monday, ..., 4 = Friday)
    try:
        res["day_of_week"] = ts.dt.day_of_week
    except (AttributeError, Exception):
        res["day_of_week"] = ts.dt.dayofweek

    # 2. Expiry day flag and days to expiry (using time-varying rules + exchange holidays)
    is_expiry_list = []
    days_to_expiry_list = []
    for dt in ts:
        d = dt.date()
        is_expiry_list.append(int(c_mgr.is_expiry_day(instrument, d)))
        days_to_expiry_list.append(c_mgr.days_to_expiry(instrument, d))

    res["is_expiry_day"] = is_expiry_list
    res["days_to_expiry"] = days_to_expiry_list

    # 3. Gap up/down size: (open_t - close_{t-1}) / close_{t-1} * 100
    prev_close = df["close"].shift(1)
    res["gap_pct"] = ((df["open"] - prev_close) / prev_close.replace(0, np.nan)) * 100.0

    # 4. Previous day range position: (close_t - low_{t-1}) / (high_{t-1} - low_{t-1})
    prev_high = df["high"].shift(1)
    prev_low = df["low"].shift(1)
    prev_range = (prev_high - prev_low).replace(0, np.nan)
    res["prev_range_pos"] = (df["close"] - prev_low) / prev_range

    # 5. Month end flag: 1 if date is the last trading day of the calendar month
    is_month_end = []
    for dt in ts:
        d = dt.date()
        next_trading = c_mgr.get_next_trading_day(d)
        is_month_end.append(int(next_trading.month != d.month))
    res["is_month_end"] = is_month_end

    return res
