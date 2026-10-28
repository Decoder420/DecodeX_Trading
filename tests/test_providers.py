"""Tests for data providers, credentials validation, fallback mechanics, and persistent storage."""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
import pandas as pd
import pytest
import pytz

from config.loader import ConfigManager
from data.angel_provider import AngelOneProvider
from data.provider_factory import DataOrchestrator
from data.storage import StorageManager
from data.upstox_provider import UpstoxProvider
from data.yfinance_provider import YFinanceProvider


def test_angel_one_missing_credentials_raises_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """AngelOneProvider must fail with a clear descriptive message if credentials missing."""
    monkeypatch.delenv("ANGEL_API_KEY", raising=False)
    monkeypatch.delenv("ANGEL_CLIENT_ID", raising=False)
    monkeypatch.delenv("ANGEL_MPIN", raising=False)
    monkeypatch.delenv("ANGEL_TOTP_SECRET", raising=False)

    cfg = ConfigManager()
    with pytest.raises(ValueError) as excinfo:
        AngelOneProvider(cfg)

    assert "Angel One credentials missing from environment (.env)" in str(excinfo.value)


def test_orchestrator_fallback_to_yfinance(monkeypatch: pytest.MonkeyPatch) -> None:
    """DataOrchestrator must automatically fall back to YFinanceProvider when Angel One credentials fail."""
    monkeypatch.delenv("ANGEL_API_KEY", raising=False)
    monkeypatch.delenv("ANGEL_CLIENT_ID", raising=False)
    monkeypatch.delenv("ANGEL_MPIN", raising=False)
    monkeypatch.delenv("ANGEL_TOTP_SECRET", raising=False)

    cfg = ConfigManager()
    cfg.config["data"]["provider"]["primary"] = "angelone"
    cfg.config["data"]["provider"]["fallback"] = "yfinance"

    orchestrator = DataOrchestrator(cfg)
    assert isinstance(orchestrator.provider, YFinanceProvider)


def test_upstox_adapter_stub() -> None:
    """UpstoxProvider adapter returns a valid DataFrame schema."""
    cfg = ConfigManager()
    upstox = UpstoxProvider(cfg)
    df = upstox.fetch_ohlcv("NIFTY", timeframe="1d")

    assert isinstance(df, pd.DataFrame)
    assert list(df.columns) == ["timestamp", "open", "high", "low", "close", "volume"]
    assert df.empty


def test_angel_token_resolution_offline_fallback() -> None:
    """Dynamic token resolution resolves known index symbols via static fallback when offline."""
    cfg = ConfigManager()
    # Mock credentials so AngelOneProvider can initialize for token testing
    os.environ["ANGEL_API_KEY"] = "mock_key"
    os.environ["ANGEL_CLIENT_ID"] = "mock_id"
    os.environ["ANGEL_MPIN"] = "1234"
    os.environ["ANGEL_TOTP_SECRET"] = "MOCKTOTP"

    try:
        provider = AngelOneProvider(cfg)
        nifty_token = provider.resolve_token("NIFTY", "NSE")
        banknifty_token = provider.resolve_token("BANKNIFTY", "NSE")
        sensex_token = provider.resolve_token("SENSEX", "BSE")

        assert nifty_token == "99926000"
        assert banknifty_token == "99926009"
        assert sensex_token == "99919000"
    finally:
        os.environ.pop("ANGEL_API_KEY", None)
        os.environ.pop("ANGEL_CLIENT_ID", None)
        os.environ.pop("ANGEL_MPIN", None)
        os.environ.pop("ANGEL_TOTP_SECRET", None)


def test_storage_incremental_upsert(tmp_path: Path) -> None:
    """Storage layer must persist candles and accurately track latest timestamp."""
    cfg = ConfigManager()
    test_db = tmp_path / "test_market_data.duckdb"
    cfg.config["data"]["storage"]["backend"] = "duckdb"
    cfg.config["data"]["storage"]["duckdb_path"] = str(test_db)

    storage = StorageManager(cfg)
    tz = pytz.timezone("Asia/Kolkata")

    df_batch1 = pd.DataFrame(
        {
            "timestamp": [
                datetime(2024, 1, 1, 9, 15, tzinfo=tz),
                datetime(2024, 1, 2, 9, 15, tzinfo=tz),
            ],
            "open": [100.0, 102.0],
            "high": [105.0, 106.0],
            "low": [98.0, 101.0],
            "close": [102.0, 105.0],
            "volume": [1000.0, 1500.0],
        }
    )

    rows = storage.save_ohlcv(df_batch1, "NIFTY", "1d")
    assert rows == 2

    latest_ts = storage.get_latest_timestamp("NIFTY", "1d")
    assert latest_ts is not None
    assert latest_ts.date() == datetime(2024, 1, 2).date()

    # Second batch with 1 overlapping candle and 1 new candle
    df_batch2 = pd.DataFrame(
        {
            "timestamp": [
                datetime(2024, 1, 2, 9, 15, tzinfo=tz),  # Overlapping
                datetime(2024, 1, 3, 9, 15, tzinfo=tz),  # New
            ],
            "open": [102.0, 105.0],
            "high": [106.0, 108.0],
            "low": [101.0, 104.0],
            "close": [105.0, 107.0],
            "volume": [1500.0, 2000.0],
        }
    )
    storage.save_ohlcv(df_batch2, "NIFTY", "1d")

    loaded_df = storage.load_ohlcv("NIFTY", "1d")
    # Total unique candles should be 3
    assert len(loaded_df) == 3


def test_angel_provider_header_patch(monkeypatch: pytest.MonkeyPatch) -> None:
    """AngelOneProvider.connect() must patch requestHeaders to inject capitalized Content-Type."""
    from unittest.mock import MagicMock
    from SmartApi import SmartConnect

    monkeypatch.setenv("ANGEL_API_KEY", "mock_key")
    monkeypatch.setenv("ANGEL_CLIENT_ID", "mock_id")
    monkeypatch.delenv("ANGEL_MPIN", raising=False)
    monkeypatch.setenv("ANGEL_MPIN", "1234")
    monkeypatch.setenv("ANGEL_TOTP_SECRET", "JBSWY3DPEHPK3PXP")

    # Mock generateSession on SmartConnect
    monkeypatch.setattr(SmartConnect, "generateSession", lambda self, cid, pin, totp: {"status": True})

    cfg = ConfigManager()
    provider = AngelOneProvider(cfg)
    assert provider.connect() is True
    assert provider.client is not None

    headers = provider.client.requestHeaders()
    assert "Content-Type" in headers
    assert headers["Content-Type"] == "application/json"

