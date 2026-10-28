"""Abstract base class for financial data providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional
import pandas as pd


class BaseDataProvider(ABC):
    """Abstract interface defining required data provider operations."""

    @abstractmethod
    def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str = "1d",
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> pd.DataFrame:
        """Fetch historical OHLCV data for an instrument.

        Args:
            symbol: Canonical instrument symbol identifier.
            timeframe: Data resolution ("1d" or "15m").
            start: Optional beginning datetime of the period.
            end: Optional ending datetime of the period.

        Returns:
            pd.DataFrame with columns:
            ['timestamp', 'open', 'high', 'low', 'close', 'volume']
            where timestamp is timezone-aware in Asia/Kolkata.
        """
        pass

    @abstractmethod
    def fetch_vix(
        self,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> pd.DataFrame:
        """Fetch India VIX historical data.

        Args:
            start: Optional start datetime.
            end: Optional end datetime.

        Returns:
            pd.DataFrame with columns:
            ['timestamp', 'open', 'high', 'low', 'close', 'volume']
        """
        pass
