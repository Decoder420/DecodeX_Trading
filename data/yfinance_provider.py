"""Yahoo Finance data provider implementation."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Dict, Optional
import pandas as pd
import pytz
import yfinance as yf

from config.loader import ConfigManager, config_manager
from data.base_provider import BaseDataProvider

logger = logging.getLogger(__name__)


class YFinanceProvider(BaseDataProvider):
    """Fetches historical market data via Yahoo Finance."""

    DEFAULT_SYMBOL_MAP: Dict[str, str] = {
        "NIFTY": "^NSEI",
        "^NSEI": "^NSEI",
        "BANKNIFTY": "^NSEBANK",
        "^NSEBANK": "^NSEBANK",
        "SENSEX": "^BSESN",
        "^BSESN": "^BSESN",
        "VIX": "^INDIAVIX",
        "^INDIAVIX": "^INDIAVIX",
        "INDIA VIX": "^INDIAVIX",
    }

    def __init__(self, cfg: Optional[ConfigManager] = None) -> None:
        self.cfg = cfg or config_manager
        self.tz = pytz.timezone(self.cfg.get("market.timezone", "Asia/Kolkata"))
        self._init_symbol_map()

    def _init_symbol_map(self) -> None:
        self.symbol_map = dict(self.DEFAULT_SYMBOL_MAP)
        instruments = self.cfg.get("instruments", {})
        for inst_key, inst_data in instruments.items():
            yf_sym = inst_data.get("symbols", {}).get("yfinance")
            if yf_sym:
                self.symbol_map[inst_key] = yf_sym
        vix_sym = self.cfg.get("vix.symbols.yfinance")
        if vix_sym:
            self.symbol_map["INDIA VIX"] = vix_sym
            self.symbol_map["VIX"] = vix_sym

    def _resolve_symbol(self, symbol: str) -> str:
        return self.symbol_map.get(symbol.upper(), symbol)

    def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str = "1d",
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> pd.DataFrame:
        """Fetch historical OHLCV data using Yahoo Finance."""
        yf_symbol = self._resolve_symbol(symbol)
        interval = "1d" if timeframe in ["1d", "D", "day"] else "15m"

        # yfinance limits 15m intraday data to max ~60 days
        if interval == "15m":
            max_intraday_start = datetime.now() - timedelta(days=59)
            if start is None or start < max_intraday_start:
                logger.warning(
                    "yfinance restricts 15m intraday data to ~60 calendar days. "
                    "Adjusting start date to %s.",
                    max_intraday_start.strftime("%Y-%m-%d"),
                )
                start = max_intraday_start

        logger.info(
            "Fetching %s (%s) from yfinance [timeframe=%s, start=%s, end=%s]",
            symbol,
            yf_symbol,
            interval,
            start,
            end,
        )

        try:
            ticker = yf.Ticker(yf_symbol)
            df = ticker.history(
                interval=interval,
                start=start.strftime("%Y-%m-%d") if start else None,
                end=(end + timedelta(days=1)).strftime("%Y-%m-%d") if end else None,
                auto_adjust=False,
            )
        except Exception as e:
            logger.error("Failed to fetch %s from yfinance: %s", yf_symbol, e)
            return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])

        if df.empty:
            logger.warning("Empty dataset returned from yfinance for %s", yf_symbol)
            return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])

        df = df.reset_index()

        # Rename columns to standard lowercase schema
        col_rename = {
            "Date": "timestamp",
            "Datetime": "timestamp",
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume",
        }
        df = df.rename(columns=col_rename)

        # Standardize timestamp timezone to Asia/Kolkata
        if "timestamp" in df.columns:
            if df["timestamp"].dt.tz is None:
                df["timestamp"] = df["timestamp"].dt.tz_localize(self.tz)
            else:
                df["timestamp"] = df["timestamp"].dt.tz_convert(self.tz)

        # Retain standard columns
        cols = ["timestamp", "open", "high", "low", "close", "volume"]
        for col in cols:
            if col not in df.columns:
                df[col] = 0.0

        df = df[cols].sort_values("timestamp").reset_index(drop=True)
        return df

    def fetch_vix(
        self,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> pd.DataFrame:
        """Fetch India VIX historical data."""
        vix_sym = self.cfg.get("vix.symbols.yfinance", "^INDIAVIX")
        return self.fetch_ohlcv(symbol=vix_sym, timeframe="1d", start=start, end=end)
