"""Upstox API data provider adapter stub."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional
import pandas as pd

from config.loader import ConfigManager, config_manager
from data.base_provider import BaseDataProvider

logger = logging.getLogger(__name__)


class UpstoxProvider(BaseDataProvider):
    """Adapter stub for Upstox V2 Historical Data API.

    Maintains identical interface with YFinanceProvider and AngelOneProvider.
    """

    def __init__(self, cfg: Optional[ConfigManager] = None) -> None:
        self.cfg = cfg or config_manager
        logger.info("Initialized UpstoxProvider adapter stub.")

    def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str = "1d",
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> pd.DataFrame:
        """Fetch OHLCV candles via Upstox API."""
        logger.warning(
            "UpstoxProvider.fetch_ohlcv is an adapter stub. Please configure Upstox API credentials "
            "or use AngelOneProvider / YFinanceProvider."
        )
        return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])

    def fetch_vix(
        self,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> pd.DataFrame:
        """Fetch India VIX candles via Upstox API."""
        return self.fetch_ohlcv(symbol="INDIA VIX", timeframe="1d", start=start, end=end)
