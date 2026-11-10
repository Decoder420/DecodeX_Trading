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
        "NSE:INDIA_VIX": {"token": "99926017", "symbol": "India VIX"},
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
        self.session_cache_path = PROJECT_ROOT / "data" / "cache" / "angel_session.json"
        self.http_session: Optional[requests.Session] = None

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

    def _init_http_session(self) -> None:
        """Initialize a persistent requests.Session with connection pooling."""
        if self.http_session is None:
            self.http_session = requests.Session()
            adapter = requests.adapters.HTTPAdapter(
                pool_connections=10,
                pool_maxsize=10,
                max_retries=3,
            )
            self.http_session.mount("https://", adapter)
            self.http_session.mount("http://", adapter)

    def _patch_client_session(self) -> None:
        """Patch client._request to route through persistent keep-alive session with browser headers."""
        if not self.client:
            return

        self._init_http_session()

        orig_rh = self.client.requestHeaders

        def _patched_request_headers():
            h = orig_rh()
            h["Content-Type"] = "application/json"
            h["Content-type"] = "application/json"
            h["User-Agent"] = (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
            )
            return h

        self.client.requestHeaders = _patched_request_headers

        from urllib.parse import urljoin

        def _session_request(route, method, parameters=None):
            params = parameters.copy() if parameters else {}
            uri = self.client._routes[route].format(**params)
            url = urljoin(self.client.root, uri)
            headers = self.client.requestHeaders()
            if self.client.access_token:
                headers["Authorization"] = f"Bearer {self.client.access_token}"

            last_exc = None
            for attempt in range(4):
                try:
                    resp = self.http_session.request(
                        method,
                        url,
                        data=json.dumps(params) if method in ["POST", "PUT"] else None,
                        params=json.dumps(params) if method in ["GET", "DELETE"] else None,
                        headers=headers,
                        timeout=self.client.timeout or 10,
                    )
                    data = resp.json()
                    return data
                except Exception as exc:
                    last_exc = exc
                    if attempt < 3:
                        time.sleep(0.75 * (attempt + 1))
            raise last_exc

        self.client._request = _session_request

    def connect(self, force_login: bool = False) -> bool:
        """Authenticate with Angel One SmartAPI using cached token or TOTP."""
        if self.authenticated and self.client:
            return True

        self._init_http_session()

        # Check cached session token first (valid up to 14 hours)
        if not force_login and self.session_cache_path.exists():
            try:
                with open(self.session_cache_path, "r", encoding="utf-8") as f:
                    cached_sess = json.load(f)
                age = time.time() - cached_sess.get("created_at", 0)
                jwt_tok = cached_sess.get("jwtToken")
                if jwt_tok and age < 14 * 3600:
                    from SmartApi import SmartConnect

                    self.client = SmartConnect(api_key=self.api_key)
                    self._patch_client_session()
                    self.client.setAccessToken(jwt_tok)
                    if cached_sess.get("refreshToken"):
                        self.client.setRefreshToken(cached_sess["refreshToken"])
                    if cached_sess.get("feedToken"):
                        self.client.setFeedToken(cached_sess["feedToken"])
                    self.client.setUserId(cached_sess.get("clientcode", self.client_id))
                    self.authenticated = True
                    logger.info("Reusing cached Angel One session token (age: %.1f min).", age / 60)
                    return True
            except Exception as e:
                logger.warning("Error loading cached session: %s. Proceeding with TOTP login.", e)

        try:
            import pyotp
            from SmartApi import SmartConnect

            self.client = SmartConnect(api_key=self.api_key)
            self._patch_client_session()

            totp = pyotp.TOTP(self.totp_secret).now()
            session = self.client.generateSession(self.client_id, self.mpin, totp)

            if session.get("status"):
                self.authenticated = True
                data = session.get("data") or {}
                # Cache session token
                try:
                    self.session_cache_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(self.session_cache_path, "w", encoding="utf-8") as f:
                        json.dump(
                            {
                                "jwtToken": self.client.access_token
                                or data.get("jwtToken", "").replace("Bearer ", ""),
                                "refreshToken": self.client.refresh_token or data.get("refreshToken"),
                                "feedToken": self.client.feed_token or data.get("feedToken"),
                                "clientcode": self.client.userId or self.client_id,
                                "created_at": time.time(),
                            },
                            f,
                            indent=2,
                        )
                except Exception as se:
                    logger.warning("Could not persist session cache: %s", se)

                logger.info("Successfully authenticated with Angel One SmartAPI and saved session cache.")
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
            chunk_days = 60
        elif timeframe in ["5m", "5min"]:
            interval = "FIVE_MINUTE"
            chunk_days = 30
        elif timeframe in ["1m", "1min"]:
            interval = "ONE_MINUTE"
            chunk_days = 20
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
