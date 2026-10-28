"""Tests for data cleaning, anomaly flagging, timezone normalization, and quality reporting."""

from __future__ import annotations

from datetime import datetime, timedelta
import pandas as pd
import pytz
import pytest

from config.loader import ConfigManager
from data.cleaner import DataCleaner
from data.quality_report import DataQualityReporter


@pytest.fixture
def sample_raw_dataframe() -> pd.DataFrame:
    tz = pytz.timezone("Asia/Kolkata")
    base_ts = datetime(2024, 1, 1, 9, 15, tzinfo=tz)

    timestamps = [base_ts + timedelta(days=i) for i in range(10)]
    # Duplicate the 3rd timestamp
    timestamps[3] = timestamps[2]

    df = pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": [100.0, 101.0, 102.0, 102.5, 0.0, 104.0, 105.0, 106.0, 107.0, 150.0],  # row 4 is zero, row 9 is outlier spike
            "high": [101.0, 102.0, 103.0, 103.0, 104.0, 103.0, 106.0, 107.0, 108.0, 155.0], # row 5 has high < open (103 < 104)
            "low": [99.0, 100.0, 101.0, 101.5, 98.0, 102.0, 104.0, 105.0, 106.0, 148.0],
            "close": [100.5, 101.5, 102.2, 102.8, 103.0, 103.5, 105.5, 106.5, 107.5, 152.0],
            "volume": [1000] * 10,
        }
    )
    return df


def test_cleaner_detects_duplicates(sample_raw_dataframe: pd.DataFrame) -> None:
    cfg = ConfigManager()
    cleaner = DataCleaner(cfg)

    cleaned_df, metrics = cleaner.clean_ohlcv(sample_raw_dataframe, timeframe="1d")

    # One duplicate timestamp should have been removed
    assert metrics["duplicates_removed"] == 1
    assert len(cleaned_df) == len(sample_raw_dataframe) - 1
    assert cleaned_df["timestamp"].is_monotonic_increasing


def test_cleaner_flags_zero_and_negative_prices(sample_raw_dataframe: pd.DataFrame) -> None:
    cfg = ConfigManager()
    cleaner = DataCleaner(cfg)

    cleaned_df, metrics = cleaner.clean_ohlcv(sample_raw_dataframe, timeframe="1d")

    # Row with open = 0.0 should be flagged
    assert metrics["zero_negative_prices_flagged"] >= 1
    bad_rows = cleaned_df[cleaned_df["is_zero_or_negative"]]
    assert len(bad_rows) >= 1
    assert (bad_rows["open"] <= 0).any()


def test_cleaner_flags_invalid_ohlc(sample_raw_dataframe: pd.DataFrame) -> None:
    cfg = ConfigManager()
    cleaner = DataCleaner(cfg)

    cleaned_df, metrics = cleaner.clean_ohlcv(sample_raw_dataframe, timeframe="1d")

    # Row 5 (high < open: 103 < 104) must be flagged
    assert metrics["ohlc_violations_flagged"] >= 1
    invalid_ohlc = cleaned_df[cleaned_df["is_ohlc_invalid"]]
    assert len(invalid_ohlc) >= 1


def test_cleaner_flags_outliers_without_deletion(sample_raw_dataframe: pd.DataFrame) -> None:
    cfg = ConfigManager()
    cleaner = DataCleaner(cfg)

    cleaned_df, metrics = cleaner.clean_ohlcv(sample_raw_dataframe, timeframe="1d")

    # Outlier spike at row 9 should be flagged in is_outlier, NOT deleted
    assert "is_outlier" in cleaned_df.columns
    # Ensure length matches (no silent row drop)
    assert len(cleaned_df) == metrics["final_rows"]


def test_timezone_normalization() -> None:
    cfg = ConfigManager()
    cleaner = DataCleaner(cfg)

    # DataFrame with naive timestamps (no timezone)
    naive_ts = [datetime(2024, 1, 1) + timedelta(days=i) for i in range(5)]
    df = pd.DataFrame(
        {
            "timestamp": naive_ts,
            "open": [100.0] * 5,
            "high": [105.0] * 5,
            "low": [95.0] * 5,
            "close": [102.0] * 5,
            "volume": [100.0] * 5,
        }
    )

    cleaned_df, _ = cleaner.clean_ohlcv(df, timeframe="1d")
    assert cleaned_df["timestamp"].dt.tz is not None
    assert str(cleaned_df["timestamp"].dt.tz) == "Asia/Kolkata"


def test_data_quality_report() -> None:
    cfg = ConfigManager()
    reporter = DataQualityReporter(cfg)

    tz = pytz.timezone("Asia/Kolkata")
    df = pd.DataFrame(
        {
            "timestamp": [datetime(2024, 1, 1, 9, 15, tzinfo=tz), datetime(2024, 1, 2, 9, 15, tzinfo=tz)],
            "open": [100.0, 101.0],
            "high": [102.0, 103.0],
            "low": [99.0, 100.0],
            "close": [101.0, 102.0],
            "volume": [500.0, 600.0],
            "is_outlier": [False, False],
            "is_gap": [False, False],
            "is_zero_or_negative": [False, False],
        }
    )

    rep = reporter.evaluate_instrument("NIFTY", "1d", df)
    assert rep["instrument"] == "NIFTY"
    assert rep["row_count"] == 2
    assert rep["status"] == "HEALTHY"

    summary_str = reporter.print_summary()
    assert "Data Quality Report" in summary_str
    assert "NIFTY" in summary_str


def test_unexplained_gaps_blocks_healthy_status() -> None:
    """Status must NOT say HEALTHY if any gap is unexplained."""
    cfg = ConfigManager()
    reporter = DataQualityReporter(cfg)
    tz = pytz.timezone("Asia/Kolkata")

    df = pd.DataFrame(
        {
            "timestamp": [datetime(2024, 1, 1, 9, 15, tzinfo=tz), datetime(2024, 1, 5, 9, 15, tzinfo=tz)],
            "open": [100.0, 101.0],
            "high": [102.0, 103.0],
            "low": [99.0, 100.0],
            "close": [101.0, 102.0],
            "volume": [500.0, 600.0],
            "is_outlier": [False, False],
            "is_gap": [False, True],
            "is_zero_or_negative": [False, False],
        }
    )

    metrics_with_unexplained = {
        "duplicates_removed": 0,
        "gaps_detected": 1,
        "unexplained_gaps": 1,
        "gap_details": [
            {
                "missing_date": "2024-01-03",
                "resumed_date": "2024-01-05",
                "category": "REAL_MISSING_DATA",
                "explanation": "Real missing candle on trading weekday",
            }
        ],
    }

    rep = reporter.evaluate_instrument("NIFTY", "1d", df, cleaning_metrics=metrics_with_unexplained)
    assert rep["status"] != "HEALTHY"
    assert "UNEXPLAINED_GAPS" in rep["status"]

    summary = reporter.print_summary()
    assert "Flagged Gaps Audit & Root-Cause Explanation" in summary
    assert "REAL_MISSING_DATA" in summary
