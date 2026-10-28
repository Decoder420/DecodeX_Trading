"""Data cleaning, validation, outlier detection, and gap detection."""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
import pytz

from config.loader import ConfigManager, config_manager

logger = logging.getLogger(__name__)


class DataCleaner:
    """Cleans financial time series, flags anomalies and gaps without silent data loss."""

    def __init__(self, cfg: Optional[ConfigManager] = None) -> None:
        self.cfg = cfg or config_manager
        self.tz = pytz.timezone(self.cfg.get("market.timezone", "Asia/Kolkata"))
        self.outlier_std_threshold = float(self.cfg.get("data_cleaning.outlier_std_threshold", 4.5))
        self.outlier_rolling_window = int(self.cfg.get("data_cleaning.outlier_rolling_window", 20))

    def clean_ohlcv(
        self,
        df: pd.DataFrame,
        timeframe: str = "1d",
        market_trading_dates: Optional[set[date]] = None,
    ) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """Clean OHLCV dataframe, flagging outliers and gaps without forward-filling prices.

        Returns:
            Tuple of (cleaned_df, cleaning_metrics_dict)
        """
        metrics: Dict[str, Any] = {
            "initial_rows": len(df),
            "duplicates_removed": 0,
            "zero_negative_prices_flagged": 0,
            "ohlc_violations_flagged": 0,
            "outliers_flagged": 0,
            "gaps_detected": 0,
            "gap_details": [],
            "unexplained_gaps": 0,
            "final_rows": 0,
        }

        if df.empty:
            metrics["final_rows"] = 0
            return df, metrics

        data = df.copy()

        # 1. Standardize timestamp and normalize timezone to Asia/Kolkata
        data["timestamp"] = pd.to_datetime(data["timestamp"])
        if data["timestamp"].dt.tz is None:
            data["timestamp"] = data["timestamp"].dt.tz_localize(self.tz)
        else:
            data["timestamp"] = data["timestamp"].dt.tz_convert(self.tz)

        # 2. Duplicate timestamps handling
        pre_dup_count = len(data)
        data = data.drop_duplicates(subset=["timestamp"], keep="last").sort_values("timestamp")
        metrics["duplicates_removed"] = pre_dup_count - len(data)

        # Ensure float types for prices and volume
        price_cols = ["open", "high", "low", "close", "volume"]
        for c in price_cols:
            if c in data.columns:
                data[c] = pd.to_numeric(data[c], errors="coerce").astype(float)
            else:
                data[c] = 0.0

        # Initialize anomaly flags
        data["is_zero_or_negative"] = False
        data["is_ohlc_invalid"] = False
        data["is_outlier"] = False
        data["is_gap"] = False

        # 3. Zero or negative price checks
        bad_price_mask = (
            (data["open"] <= 0)
            | (data["high"] <= 0)
            | (data["low"] <= 0)
            | (data["close"] <= 0)
        )
        data.loc[bad_price_mask, "is_zero_or_negative"] = True
        metrics["zero_negative_prices_flagged"] = int(bad_price_mask.sum())

        # 4. OHLC logical consistency (High must be >= max(Open, Close); Low must be <= min(Open, Close))
        ohlc_viol_mask = (
            (data["high"] < data["open"])
            | (data["high"] < data["close"])
            | (data["low"] > data["open"])
            | (data["low"] > data["close"])
        )
        data.loc[ohlc_viol_mask, "is_ohlc_invalid"] = True
        metrics["ohlc_violations_flagged"] = int(ohlc_viol_mask.sum())

        # 5. Outlier detection: Flag candles where return > N rolling std deviations
        # Use log returns
        ret = np.log(data["close"] / data["close"].shift(1))
        rolling_mean = ret.rolling(window=self.outlier_rolling_window, min_periods=5).mean()
        rolling_std = ret.rolling(window=self.outlier_rolling_window, min_periods=5).std()
        # Avoid division by zero
        rolling_std = rolling_std.replace(0, np.nan)
        z_scores = ((ret - rolling_mean) / rolling_std).abs()

        outlier_mask = z_scores > self.outlier_std_threshold
        data.loc[outlier_mask, "is_outlier"] = True
        metrics["outliers_flagged"] = int(outlier_mask.sum())

        # 6. Gap detection (verified against holiday calendar & cross-instrument traded dates)
        gaps_count, gap_details = self._detect_gaps_with_details(data, timeframe, market_trading_dates)
        metrics["gaps_detected"] = gaps_count
        metrics["gap_details"] = gap_details
        metrics["unexplained_gaps"] = sum(1 for g in gap_details if g["category"] == "DATA_MISSING_IN_FEED")
        metrics["final_rows"] = len(data)

        return data.reset_index(drop=True), metrics

    def _detect_gaps_with_details(
        self,
        df: pd.DataFrame,
        timeframe: str,
        market_trading_dates: Optional[set[date]] = None,
    ) -> Tuple[int, List[Dict[str, str]]]:
        """Detect missing trading sessions or interval bars and categorize reasons without speculation."""
        if len(df) < 2:
            return 0, []

        gaps = 0
        details: List[Dict[str, str]] = []
        timestamps = df["timestamp"].tolist()

        if timeframe in ["1d", "D", "day"]:
            for i in range(1, len(timestamps)):
                prev_date = timestamps[i - 1].date()
                curr_date = timestamps[i].date()
                diff_days = (curr_date - prev_date).days

                if diff_days > 1:
                    check = prev_date + timedelta(days=1)
                    missing_on_this_step = []
                    while check < curr_date:
                        if self.cfg.is_trading_day(check):
                            # Cross-instrument check: did other instruments trade on this day?
                            other_traded = market_trading_dates is not None and check in market_trading_dates
                            if other_traded or market_trading_dates is None:
                                category = "DATA_MISSING_IN_FEED"
                                explanation = "Cross-instrument check: other instruments traded on this date; candle absent from provider feed (cause unknown)"
                            else:
                                category = "MARKET_WIDE_CLOSURE"
                                explanation = "No market instruments traded on this date; exchange closure (cause unknown)"

                            missing_on_this_step.append(
                                {
                                    "missing_date": check.strftime("%Y-%m-%d"),
                                    "resumed_date": curr_date.strftime("%Y-%m-%d"),
                                    "category": category,
                                    "explanation": explanation,
                                }
                            )
                        check += timedelta(days=1)

                    if missing_on_this_step:
                        gaps += len(missing_on_this_step)
                        df.loc[df.index[i], "is_gap"] = True
                        details.extend(missing_on_this_step)
        else:
            # Intraday 15m candle spacing
            for i in range(1, len(timestamps)):
                prev_ts = timestamps[i - 1]
                curr_ts = timestamps[i]
                if prev_ts.date() == curr_ts.date():
                    delta_min = (curr_ts - prev_ts).total_seconds() / 60.0
                    if delta_min > 15.0:
                        gaps += 1
                        df.loc[df.index[i], "is_gap"] = True
                        details.append(
                            {
                                "missing_date": prev_ts.strftime("%Y-%m-%d %H:%M"),
                                "resumed_date": curr_ts.strftime("%Y-%m-%d %H:%M"),
                                "category": "DATA_MISSING_IN_FEED",
                                "explanation": f"Missing intraday 15m candle between {prev_ts.strftime('%H:%M')} and {curr_ts.strftime('%H:%M')} (cause unknown)",
                            }
                        )
                else:
                    check = prev_ts.date() + timedelta(days=1)
                    while check < curr_ts.date():
                        if self.cfg.is_trading_day(check):
                            gaps += 1
                            df.loc[df.index[i], "is_gap"] = True
                            details.append(
                                {
                                    "missing_date": check.strftime("%Y-%m-%d"),
                                    "resumed_date": curr_ts.date().strftime("%Y-%m-%d"),
                                    "category": "DATA_MISSING_IN_FEED",
                                    "explanation": "Multi-day cross-session gap on expected trading day (cause unknown)",
                                }
                            )
                        check += timedelta(days=1)

        return gaps, details
