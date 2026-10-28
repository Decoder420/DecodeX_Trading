"""Provider factory and data orchestrator with automatic fallback."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional, Tuple
import pandas as pd

from config.loader import ConfigManager, config_manager
from data.angel_provider import AngelOneProvider
from data.base_provider import BaseDataProvider
from data.cleaner import DataCleaner
from data.quality_report import DataQualityReporter
from data.storage import StorageManager
from data.upstox_provider import UpstoxProvider
from data.yfinance_provider import YFinanceProvider

logger = logging.getLogger(__name__)


class DataOrchestrator:
    """Coordinates data fetching, fallback logic, cleaning, and persistent incremental storage."""

    def __init__(self, cfg: Optional[ConfigManager] = None) -> None:
        self.cfg = cfg or config_manager
        self.cleaner = DataCleaner(self.cfg)
        self.storage = StorageManager(self.cfg)
        self.reporter = DataQualityReporter(self.cfg)
        self.primary_provider_name = self.cfg.get("data.provider.primary", "angelone").lower()
        self.fallback_provider_name = self.cfg.get("data.provider.fallback", "yfinance").lower()
        self.provider: BaseDataProvider = self._init_provider()

    def _init_provider(self) -> BaseDataProvider:
        """Initialize primary data provider; gracefully fall back if credentials missing."""
        if self.primary_provider_name == "angelone":
            try:
                logger.info("Attempting initialization of primary provider: AngelOneProvider")
                return AngelOneProvider(self.cfg)
            except (ValueError, ConnectionError, Exception) as e:
                logger.warning(
                    "AngelOneProvider initialization failed: %s. "
                    "Falling back to %s daily data.",
                    e,
                    self.fallback_provider_name,
                )
                return YFinanceProvider(self.cfg)
        elif self.primary_provider_name == "groww":
            try:
                from data.groww_provider import GrowwProvider
                logger.info("Attempting initialization of primary provider: GrowwProvider")
                return GrowwProvider(self.cfg)
            except Exception as e:
                logger.warning(
                    "GrowwProvider initialization failed: %s. Falling back to %s daily data.",
                    e,
                    self.fallback_provider_name,
                )
                return YFinanceProvider(self.cfg)
        elif self.primary_provider_name == "upstox":
            logger.warning("Upstox provider requested; running adapter stub with fallback.")
            return UpstoxProvider(self.cfg)
        else:
            return YFinanceProvider(self.cfg)

    def fetch_and_store(
        self,
        symbol: str,
        timeframe: str = "1d",
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        force_refresh: bool = False,
    ) -> Tuple[pd.DataFrame, DataQualityReporter]:
        """Fetch missing candles incrementally, clean them, update storage, and log quality report."""
        tz = self.cleaner.tz
        # Normalize start and end datetimes to timezone-aware
        norm_start = start.astimezone(tz) if start and start.tzinfo else (tz.localize(start) if start else None)
        norm_end = end.astimezone(tz) if end and end.tzinfo else (tz.localize(end) if end else datetime.now(tz))

        latest_ts = None if force_refresh else self.storage.get_latest_timestamp(symbol, timeframe)
        earliest_ts = None if force_refresh else self.storage.get_earliest_timestamp(symbol, timeframe)

        fetch_start = norm_start
        fetch_end = norm_end

        all_market_dates = self.storage.get_all_market_trading_dates()

        if not force_refresh and latest_ts is not None and earliest_ts is not None:
            # Case 1: Storage covers requested range
            if (norm_start is None or norm_start >= earliest_ts) and (norm_end <= latest_ts):
                logger.info("Local storage is already up to date for %s [%s].", symbol, timeframe)
                df_stored = self.storage.load_ohlcv(symbol, timeframe, start=norm_start, end=norm_end)
                _, metrics = self.cleaner.clean_ohlcv(df_stored, timeframe=timeframe, market_trading_dates=all_market_dates)
                self.reporter.evaluate_instrument(symbol, timeframe, df_stored, metrics)
                return df_stored, self.reporter

            # Case 2: Only forward incremental needed
            if norm_start and norm_start >= earliest_ts and norm_end > latest_ts:
                fetch_start = latest_ts + timedelta(seconds=1)
                fetch_end = norm_end
                logger.info(
                    "Incremental forward fetch for %s [%s]: %s to %s",
                    symbol,
                    timeframe,
                    fetch_start,
                    fetch_end,
                )
            # Case 3: Need earlier history as well
            elif norm_start and norm_start < earliest_ts:
                logger.info(
                    "Expanding historical range for %s [%s]: fetching %s to %s",
                    symbol,
                    timeframe,
                    norm_start,
                    norm_end,
                )
                fetch_start = norm_start
                fetch_end = norm_end

        # Fetch new data
        raw_df = self.provider.fetch_ohlcv(symbol=symbol, timeframe=timeframe, start=fetch_start, end=fetch_end)

        # Fallback to yfinance if primary returned empty for any reason
        if raw_df.empty and not isinstance(self.provider, YFinanceProvider):
            logger.warning(
                "Primary provider returned empty data for %s [%s]. Attempting YFinanceProvider fallback.",
                symbol,
                timeframe,
            )
            yf_provider = YFinanceProvider(self.cfg)
            raw_df = yf_provider.fetch_ohlcv(symbol=symbol, timeframe=timeframe, start=fetch_start, end=fetch_end)

        if not raw_df.empty:
            cleaned_df, metrics = self.cleaner.clean_ohlcv(
                raw_df, timeframe=timeframe, market_trading_dates=all_market_dates
            )
            self.storage.save_ohlcv(cleaned_df, symbol=symbol, timeframe=timeframe)
        else:
            metrics = {"duplicates_removed": 0}

        # Load consolidated time series from storage
        consolidated_df = self.storage.load_ohlcv(symbol, timeframe, start=norm_start, end=norm_end)
        self.reporter.evaluate_instrument(symbol, timeframe, consolidated_df, metrics)

        return consolidated_df, self.reporter

    def fetch_vix(
        self,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> pd.DataFrame:
        """Fetch India VIX candles."""
        try:
            return self.provider.fetch_vix(start=start, end=end)
        except Exception as e:
            logger.warning("Primary provider failed for VIX: %s. Using YFinanceProvider.", e)
            yf_provider = YFinanceProvider(self.cfg)
            return yf_provider.fetch_vix(start=start, end=end)
