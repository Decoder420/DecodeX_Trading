"""Groww Trade API Data Provider implementation.

Implements BaseDataProvider interface for historical data, intraday candles,
index values, nearest-month futures resolution, and live feeds.
Strictly read-only: no order execution or modification endpoints.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd
import pytz

from config.loader import ConfigManager, config_manager
from data.base_provider import BaseDataProvider
from data.groww_auth import GrowwAuthManager, IST

logger = logging.getLogger(__name__)


class GrowwProvider(BaseDataProvider):
    """Data provider using the official growwapi Python SDK.
    
    Adheres strictly to read-only capabilities:
    - Market Data (LTP, OHLC)
    - Historical Candles (1m, 5m, 15m, 1d)
    - Option Chain & Greeks
    - WebSocket Live Feed (via GrowwFeed)
    """

    TIMEFRAME_MAP = {
        "1m": "1minute",
        "1min": "1minute",
        "5m": "5minute",
        "5min": "5minute",
        "15m": "15minute",
        "15min": "15minute",
        "30m": "30minute",
        "1h": "1hour",
        "4h": "4hour",
        "1d": "1day",
        "day": "1day",
    }

    def __init__(
        self,
        cfg: Optional[ConfigManager] = None,
        auth_mgr: Optional[GrowwAuthManager] = None,
    ) -> None:
        self.cfg = cfg or config_manager
        self.auth_mgr = auth_mgr or GrowwAuthManager()
        self._api = None
        self._instruments_cache: Optional[pd.DataFrame] = None
        self._instruments_cache_time: Optional[datetime] = None

    @property
    def api(self):
        """Lazy-initialize authenticated GrowwAPI client."""
        if self._api is None:
            from growwapi import GrowwAPI
            token = self.auth_mgr.get_access_token(allow_approval_fallback=True)
            self._api = GrowwAPI(token)
        return self._api

    def get_instruments(self, force_refresh: bool = False) -> pd.DataFrame:
        """Fetch and cache Groww instrument master."""
        now = datetime.now(IST)
        if (
            not force_refresh
            and self._instruments_cache is not None
            and self._instruments_cache_time is not None
            and (now - self._instruments_cache_time).total_seconds() < 86400
        ):
            return self._instruments_cache

        cache_path = Path("data/cache/groww_instrument_master.csv")
        if not force_refresh and cache_path.exists():
            try:
                mtime = datetime.fromtimestamp(cache_path.stat().st_mtime, tz=IST)
                if (now - mtime).total_seconds() < 86400:
                    df = pd.read_csv(cache_path, low_memory=False)
                    self._instruments_cache = df
                    self._instruments_cache_time = now
                    return df
            except Exception as e:
                logger.debug("Failed reading instrument cache: %s", e)

        logger.info("Downloading Groww instrument master CSV...")
        df = self.api.get_all_instruments()
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(cache_path, index=False)
        self._instruments_cache = df
        self._instruments_cache_time = now
        return df

    def resolve_instrument(self, symbol: str) -> Dict[str, Any]:
        """Resolve canonical symbol to Groww parameters."""
        sym = symbol.upper().strip()

        if sym in ["NIFTY", "NIFTY 50", "^NSEI"]:
            return {
                "exchange": "NSE",
                "segment": "CASH",
                "trading_symbol": "NIFTY",
                "groww_symbol": "NSE-NIFTY",
                "exchange_token": "NIFTY",
                "exchange_trading_symbol": "NSE_NIFTY",
            }
        elif sym in ["BANKNIFTY", "BANK NIFTY", "^NSEBANK"]:
            return {
                "exchange": "NSE",
                "segment": "CASH",
                "trading_symbol": "BANKNIFTY",
                "groww_symbol": "NSE-BANKNIFTY",
                "exchange_token": "BANKNIFTY",
                "exchange_trading_symbol": "NSE_BANKNIFTY",
            }
        elif sym in ["SENSEX", "^BSESN"]:
            return {
                "exchange": "BSE",
                "segment": "CASH",
                "trading_symbol": "SENSEX",
                "groww_symbol": "BSE-SENSEX",
                "exchange_token": "1",
                "exchange_trading_symbol": "BSE_SENSEX",
            }
        elif sym in ["INDIAVIX", "INDIA VIX", "^INDIAVIX"]:
            return {
                "exchange": "NSE",
                "segment": "CASH",
                "trading_symbol": "INDIAVIX",
                "groww_symbol": "NSE-INDIAVIX",
                "exchange_token": "INDIAVIX",
                "exchange_trading_symbol": "NSE_INDIAVIX",
            }

        # Check in instrument master for individual stocks or custom scrips
        df = self.get_instruments()
        matches = df[df["trading_symbol"] == sym]
        if not matches.empty:
            row = matches.iloc[0]
            return {
                "exchange": str(row["exchange"]),
                "segment": str(row["segment"]),
                "trading_symbol": str(row["trading_symbol"]),
                "groww_symbol": str(row["groww_symbol"]),
                "exchange_token": str(row["exchange_token"]),
                "exchange_trading_symbol": f"{row['exchange']}_{row['trading_symbol']}",
            }

        raise ValueError(f"Could not resolve instrument symbol '{symbol}' in Groww scrip master.")

    def get_nearest_futures(self, underlying_symbol: str) -> Optional[Dict[str, Any]]:
        """Find the active nearest-month futures contract."""
        df = self.get_instruments()
        today_str = datetime.now(IST).strftime("%Y-%m-%d")
        exchange = "BSE" if underlying_symbol.upper() == "SENSEX" else "NSE"

        fut_rows = df[
            (df["exchange"] == exchange)
            & (df["segment"] == "FNO")
            & (df["instrument_type"] == "FUT")
            & (df["underlying_symbol"] == underlying_symbol.upper())
            & (df["expiry_date"] >= today_str)
        ].sort_values("expiry_date")

        if fut_rows.empty:
            return None

        row = fut_rows.iloc[0]
        return {
            "trading_symbol": str(row["trading_symbol"]),
            "groww_symbol": str(row["groww_symbol"]),
            "expiry_date": str(row["expiry_date"]),
            "exchange_token": str(row["exchange_token"]),
            "exchange": str(row["exchange"]),
            "segment": str(row["segment"]),
            "lot_size": int(row.get("lot_size", 0)),
            "tick_size": float(row.get("tick_size", 0.05)),
        }

    def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str = "1d",
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> pd.DataFrame:
        """Fetch historical candle data from Groww Trade API.
        
        Args:
            symbol: Canonical symbol identifier (e.g. 'NIFTY', 'BANKNIFTY', 'SENSEX').
            timeframe: Candle interval ('1m', '5m', '15m', '1d').
            start: Start datetime (Asia/Kolkata).
            end: End datetime (Asia/Kolkata).

        Returns:
            pd.DataFrame with columns:
            ['timestamp', 'open', 'high', 'low', 'close', 'volume']
        """
        resolved = self.resolve_instrument(symbol)
        interval = self.TIMEFRAME_MAP.get(timeframe.lower(), "1day")

        now = datetime.now(IST)
        end_dt = end or now
        start_dt = start or (end_dt - timedelta(days=30))

        if start_dt.tzinfo is None:
            start_dt = IST.localize(start_dt)
        else:
            start_dt = start_dt.astimezone(IST)

        if end_dt.tzinfo is None:
            end_dt = IST.localize(end_dt)
        else:
            end_dt = end_dt.astimezone(IST)

        start_str = start_dt.strftime("%Y-%m-%d %H:%M:%S")
        end_str = end_dt.strftime("%Y-%m-%d %H:%M:%S")

        logger.info(
            "Fetching Groww candles for %s (%s) from %s to %s",
            resolved["groww_symbol"],
            interval,
            start_str,
            end_str,
        )

        res = self.api.get_historical_candles(
            exchange=resolved["exchange"],
            segment=resolved["segment"],
            groww_symbol=resolved["groww_symbol"],
            start_time=start_str,
            end_time=end_str,
            candle_interval=interval,
        )

        raw_candles = res.get("candles", []) if isinstance(res, dict) else []
        if not raw_candles:
            logger.warning("Groww returned 0 candles for %s (%s)", symbol, interval)
            return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])

        # Format: each candle is [timestamp_epoch_or_str, open, high, low, close, volume]
        records = []
        for c in raw_candles:
            if len(c) >= 5:
                ts_val = c[0]
                if isinstance(ts_val, (int, float)):
                    # Epoch seconds or milliseconds
                    if ts_val > 1e11:
                        ts = datetime.fromtimestamp(ts_val / 1000.0, tz=pytz.UTC).astimezone(IST)
                    else:
                        ts = datetime.fromtimestamp(ts_val, tz=pytz.UTC).astimezone(IST)
                else:
                    ts = pd.to_datetime(ts_val)
                    if ts.tzinfo is None:
                        ts = IST.localize(ts)
                    else:
                        ts = ts.astimezone(IST)

                records.append({
                    "timestamp": ts,
                    "open": float(c[1]),
                    "high": float(c[2]),
                    "low": float(c[3]),
                    "close": float(c[4]),
                    "volume": float(c[5]) if len(c) > 5 else 0.0,
                })

        df = pd.DataFrame(records)
        df = df.sort_values("timestamp").drop_duplicates(subset=["timestamp"]).reset_index(drop=True)
        return df

    def fetch_vix(
        self,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> pd.DataFrame:
        """Fetch India VIX historical candles from Groww."""
        return self.fetch_ohlcv("INDIAVIX", timeframe="1d", start=start, end=end)
