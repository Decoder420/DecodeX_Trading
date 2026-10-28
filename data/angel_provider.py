"""Angel One SmartAPI data provider with dynamic scrip resolution, rate-limiting, and chunking."""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
import pandas as pd
import pytz
import requests
from dotenv import load_dotenv

from config.loader import ConfigManager, config_manager
from data.base_provider import BaseDataProvider
from data.rate_limiter import shared_rate_limiter

logger = logging.getLogger(__name__)

# Load workspace .env explicitly without scanning parent directories
PROJECT_ROOT = Path(__file__).resolve().parent.parent
WORKSPACE_ENV = PROJECT_ROOT / ".env"
if WORKSPACE_ENV.exists():
    load_dotenv(dotenv_path=WORKSPACE_ENV)


class AngelOneProvider(BaseDataProvider):
    """Angel One SmartAPI Provider with dynamic scrip master token resolution."""

    # Fallback tokens for offline or sandbox mode if remote scrip master is unreachable
    STATIC_FALLBACK_TOKENS: Dict[str, Dict[str, str]] = {
        "NSE:NIFTY": {"token": "99926000", "symbol": "Nifty 50"},
        "NSE:BANKNIFTY": {"token": "99926009", "symbol": "Nifty Bank"},
        "BSE:SENSEX": {"token": "99919000", "symbol": "Sensex"},
        "NSE:INDIA VIX": {"token": "99926017", "symbol": "India VIX"},
        "NSE:VIX": {"token": "99926017", "symbol": "India VIX"},
    }

    def __init__(self, cfg: Optional[ConfigManager] = None) -> None:
        self.cfg = cfg or config_manager
        self.tz = pytz.timezone(self.cfg.get("market.timezone", "Asia/Kolkata"))
        self.api_key = os.getenv("ANGEL_API_KEY")
        self.client_id = os.getenv("ANGEL_CLIENT_ID")
        self.mpin = os.getenv("ANGEL_MPIN")
        self.totp_secret = os.getenv("ANGEL_TOTP_SECRET")

        self.scrip_master_url = self.cfg.get(
            "data.provider.angelone.scrip_master_url",
            "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json",
        )
        self.cache_path = Path(
            self.cfg.get("data.provider.angelone.cache_path", "data/cache/angel_scrip_master.json")
        )
        self.cache_ttl_hours = self.cfg.get("data.provider.angelone.cache_ttl_hours", 24)

        self.client: Any = None
        self.authenticated = False
        self._scrip_master: Optional[List[Dict[str, Any]]] = None

        self._validate_credentials()

    def _validate_credentials(self) -> None:
        """Verify environment credentials exist; raise descriptive error if missing."""
        missing = []
        if not self.api_key:
            missing.append("ANGEL_API_KEY")
        if not self.client_id:
            missing.append("ANGEL_CLIENT_ID")
        if not self.mpin:
            missing.append("ANGEL_MPIN")
        if not self.totp_secret:
            missing.append("ANGEL_TOTP_SECRET")

        if missing:
            msg = (
                f"Angel One credentials missing from environment (.env): {', '.join(missing)}. "
                "Cannot initialize live AngelOneProvider; falling back to alternative provider."
            )
            logger.warning(msg)
            raise ValueError(msg)

    def connect(self) -> bool:
        """Authenticate with Angel One SmartAPI using TOTP."""
        if self.authenticated and self.client:
            return True

        try:
            import pyotp
            from SmartApi import SmartConnect

            self.client = SmartConnect(api_key=self.api_key)

            # Instance-level patch: Ensure standard capitalized Content-Type header
            # to resolve Cloudflare WAF / Kong 403 error without modifying library files in .venv
            orig_rh = self.client.requestHeaders

            def _patched_request_headers():
                h = orig_rh()
                h["Content-Type"] = "application/json"
                return h

            self.client.requestHeaders = _patched_request_headers

            totp = pyotp.TOTP(self.totp_secret).now()
            session = self.client.generateSession(self.client_id, self.mpin, totp)

            if session.get("status"):
                self.authenticated = True
                logger.info("Successfully authenticated with Angel One SmartAPI.")
                return True
            else:
                msg = f"Angel One authentication rejected: {session.get('message')}"
                logger.error(msg)
                raise ConnectionError(msg)
        except Exception as e:
            logger.error("Angel One connection failed: %s", e)
            raise

    def _load_scrip_master(self) -> List[Dict[str, Any]]:
        """Load and cache Angel One scrip master for dynamic symbol-to-token resolution."""
        if self._scrip_master is not None:
            return self._scrip_master

        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        need_download = True

        if self.cache_path.exists():
            file_age = time.time() - self.cache_path.stat().st_mtime
            if file_age < self.cache_ttl_hours * 3600:
                try:
                    with open(self.cache_path, "r", encoding="utf-8") as f:
                        self._scrip_master = json.load(f)
                    logger.info("Loaded cached Angel One scrip master from %s", self.cache_path)
                    need_download = False
                except Exception as e:
                    logger.warning("Error reading cached scrip master: %s. Re-downloading.", e)

        if need_download:
            try:
                logger.info("Downloading Angel One scrip master from %s...", self.scrip_master_url)
                resp = requests.get(self.scrip_master_url, timeout=30)
                resp.raise_for_status()
                data = resp.json()
                with open(self.cache_path, "w", encoding="utf-8") as f:
                    json.dump(data, f)
                self._scrip_master = data
                logger.info("Saved Angel One scrip master to cache (%d records)", len(data))
            except Exception as e:
                logger.warning(
                    "Failed to download Angel One scrip master: %s. Using static fallback mapping.", e
                )
                self._scrip_master = []

        return self._scrip_master or []

    def resolve_token(self, symbol: str, exchange: str = "NSE") -> str:
        """Dynamically resolve Angel One token for a given symbol and exchange."""
        key = f"{exchange.upper()}:{symbol.upper()}"
        if key in self.STATIC_FALLBACK_TOKENS:
            return self.STATIC_FALLBACK_TOKENS[key]["token"]

        scrips = self._load_scrip_master()
        target_sym = symbol.upper().strip()
        target_exch = exchange.upper().strip()

        for s in scrips:
            if s.get("exch_seg") == target_exch and (
                s.get("name", "").upper() == target_sym
                or s.get("symbol", "").upper().startswith(target_sym)
            ):
                return str(s.get("token"))

        raise ValueError(f"Could not resolve Angel One token for {exchange}:{symbol}")

    def _execute_with_retry(self, func_or_endpoint: Any, *args: Any, **kwargs: Any) -> Any:
        """Execute SmartAPI call routed through shared rate limiter with exponential backoff."""
        if isinstance(func_or_endpoint, str):
            endpoint = func_or_endpoint
            func = args[0]
            call_args = args[1:]
        else:
            func = func_or_endpoint
            call_args = args
            endpoint = getattr(func, "__name__", "getCandleData")
            if endpoint not in shared_rate_limiter.buckets:
                endpoint = "getCandleData"

        return shared_rate_limiter.execute_with_backoff(endpoint, func, *call_args, **kwargs)

    def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str = "1d",
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> pd.DataFrame:
        """Fetch historical candles with chunking for large date ranges."""
        self.connect()

        # Map interval
        if timeframe in ["1d", "D", "day"]:
            interval = "ONE_DAY"
            chunk_days = 365
        elif timeframe in ["15m", "15min"]:
            interval = "FIFTEEN_MINUTE"
            chunk_days = self.cfg.get("data.provider.rate_limits.intraday_chunk_days", 30)
        elif timeframe in ["5m", "5min"]:
            interval = "FIVE_MINUTE"
            chunk_days = 10
        elif timeframe in ["1m", "1min"]:
            interval = "ONE_MINUTE"
            chunk_days = 5
        else:
            raise ValueError(f"Unsupported timeframe: {timeframe}")

        # Resolve exchange and symbol config
        inst_cfg = self.cfg.get(f"instruments.{symbol}") or {}
        exchange = inst_cfg.get("exchange", "NSE")
        token = self.resolve_token(symbol, exchange)

        if end is None:
            end = datetime.now()
        if start is None:
            start = end - timedelta(days=365 if interval == "ONE_DAY" else 60)

        # Split into date chunks
        current_start = start
        all_bars: List[List[Any]] = []

        while current_start < end:
            current_end = min(current_start + timedelta(days=chunk_days), end)
            params = {
                "exchange": exchange,
                "symboltoken": str(token),
                "interval": interval,
                "fromdate": current_start.strftime("%Y-%m-%d %H:%M"),
                "todate": current_end.strftime("%Y-%m-%d %H:%M"),
            }

            logger.info("Angel One fetch chunk: %s to %s for %s", params["fromdate"], params["todate"], symbol)
            response = self._execute_with_retry(self.client.getCandleData, params)

            if response and response.get("status") and response.get("data"):
                all_bars.extend(response["data"])

            current_start = current_end + timedelta(minutes=1)

        if not all_bars:
            return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])

        # Format DataFrame: [timestamp, open, high, low, close, volume]
        df = pd.DataFrame(all_bars, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        if df["timestamp"].dt.tz is None:
            df["timestamp"] = df["timestamp"].dt.tz_localize(self.tz)
        else:
            df["timestamp"] = df["timestamp"].dt.tz_convert(self.tz)

        df = df.drop_duplicates(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)
        return df

    def fetch_vix(
        self,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> pd.DataFrame:
        """Fetch India VIX historical candles."""
        return self.fetch_ohlcv(symbol="INDIA VIX", timeframe="1d", start=start, end=end)
