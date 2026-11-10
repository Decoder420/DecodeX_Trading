"""Live market recorder engine with multi-token WebSocket 2.0 streaming, 10s REST fallback,
volume-differenced VWAP bars, options chain snapshots, and health heartbeats.
"""

from __future__ import annotations

import json
import logging
import math
import os
import ssl
import sys
import threading
import time
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import pandas as pd
import resource
import ssl
import sys
import threading
import time
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import pandas as pd
import pyotp
import pytz
from dotenv import load_dotenv

from SmartApi import SmartConnect
from SmartApi.smartWebSocketV2 import SmartWebSocketV2
from config.loader import ConfigManager, config_manager
from data.rate_limiter import shared_rate_limiter
from recorder.metrics import CumulativeIntradayVWAP, compute_bar_volume
from recorder.options_monitor import OptionsMonitor
from recorder.roll import FuturesRollManager
from recorder.storage import LiveStorageManager

# Suppress logzero secret output
try:
    import logzero
    logzero.logger.setLevel(logging.WARNING)
except Exception:
    pass

PROJECT_ROOT = Path(__file__).resolve().parent.parent
logger = logging.getLogger("LiveRecorder")


class LiveRecorderEngine:
    """Production-grade live market recorder for Indian index spot, futures, and options."""

    # 9 Core Tokens for continuous tick & depth recording (3 Spot + 3 Near Futures + 3 Next Futures)
    CORE_TOKENS = [
        {"exchangeType": 1, "tokens": ["99926000", "99926009"]},
        {"exchangeType": 3, "tokens": ["99919000"]},
        {"exchangeType": 2, "tokens": ["48704", "61471", "48699", "61466"]},
        {"exchangeType": 4, "tokens": ["864571", "1100929"]},
    ]

    FUTURES_EXPIRIES = {
        "NIFTY_FUT_NEAR": date(2026, 10, 27),
        "NIFTY_FUT_NEXT": date(2026, 11, 23),
        "BANKNIFTY_FUT_NEAR": date(2026, 10, 27),
        "BANKNIFTY_FUT_NEXT": date(2026, 11, 23),
        "SENSEX_FUT_NEAR": date(2026, 10, 29),
        "SENSEX_FUT_NEXT": date(2026, 11, 26),
    }

    def __init__(
        self,
        storage_mgr: Optional[LiveStorageManager] = None,
        cfg: Optional[ConfigManager] = None,
    ) -> None:
        self.cfg = cfg or config_manager
        self.storage = storage_mgr or LiveStorageManager()
        self.tz = pytz.timezone(self.cfg.get("market.timezone", "Asia/Kolkata"))

        self.api_key = os.getenv("ANGEL_API_KEY")
        self.client_id = os.getenv("ANGEL_CLIENT_ID")
        self.mpin = os.getenv("ANGEL_MPIN")
        self.totp_secret = os.getenv("ANGEL_TOTP_SECRET")

        self.client: Optional[SmartConnect] = None
        self.ws: Optional[SmartWebSocketV2] = None
        self.options_monitor: Optional[OptionsMonitor] = None

        # State tracking
        self.running = False
        self.start_time: Optional[float] = None
        self.ticks_count = 0
        self.last_tick_time = 0.0
        self.active_source = "initializing"
        self.disconnect_count = 0

        # Latest market prices for spot & futures
        self.latest_prices: Dict[str, float] = {
            "NIFTY": 22650.0,
            "BANKNIFTY": 54150.0,
            "SENSEX": 73300.0,
            "NIFTY_FUT_NEAR": 22700.0,
            "NIFTY_FUT_NEXT": 22820.0,
            "BANKNIFTY_FUT_NEAR": 54250.0,
            "BANKNIFTY_FUT_NEXT": 54620.0,
            "SENSEX_FUT_NEAR": 73500.0,
            "SENSEX_FUT_NEXT": 74000.0,
        }

        # VWAP trackers for all 6 futures contracts
        self.vwap_trackers = {
            sym: CumulativeIntradayVWAP(sym, exp)
            for sym, exp in self.FUTURES_EXPIRIES.items()
        }

        # Institutional Roll Managers per underlying
        self.roll_managers = {
            "NIFTY": FuturesRollManager("NIFTY"),
            "BANKNIFTY": FuturesRollManager("BANKNIFTY"),
            "SENSEX": FuturesRollManager("SENSEX"),
        }

        # Rolling 1-minute futures bar aggregator: {symbol: {open, high, low, close, volume, oi}}
        self.rolling_bars: Dict[str, Dict[str, Any]] = {}
        self.option_tokens_meta: Dict[str, Dict[str, Any]] = {}
        self.latest_option_quotes: Dict[str, Dict[str, Any]] = {}
        self._tick_buffer: List[Dict[str, Any]] = []
        self._depth_buffer: List[Dict[str, Any]] = []
        self._last_flush_time = time.time()
        self._lock = threading.Lock()

    def _flush_tick_buffer(self, force: bool = False) -> None:
        """Batch flush in-memory ticks and depth quotes into DuckDB to prevent lock contention."""
        now = time.time()
        with self._lock:
            if not force and len(self._tick_buffer) < 50 and (now - self._last_flush_time) < 1.0:
                return
            ticks_to_write = list(self._tick_buffer)
            depth_to_write = list(self._depth_buffer)
            self._tick_buffer.clear()
            self._depth_buffer.clear()
            self._last_flush_time = now

        if ticks_to_write:
            try:
                self.storage.insert_ticks(ticks_to_write)
            except Exception as e:
                logger.warning("Error flushing ticks batch: %s", e)
        if depth_to_write:
            try:
                self.storage.insert_depth(depth_to_write)
            except Exception as e:
                logger.warning("Error flushing depth batch: %s", e)

        # Write atomic state file for zero-latency dashboard reads
        try:
            state = {
                "has_live": True,
                "prices": self.latest_prices,
                "timestamp": datetime.now(self.tz).strftime("%Y-%m-%d %H:%M:%S"),
                "total_ticks": self.ticks_count,
                "source": self.active_source,
                "disconnect_count": self.disconnect_count,
                "active_option_tokens": len(self.option_tokens_meta),
                "latest_option_quotes_count": len(self.latest_option_quotes),
                "latest_option_quotes": self.latest_option_quotes,
                "last_option_tick_time": max(
                    [
                        q.get("exchange_timestamp").strftime("%Y-%m-%d %H:%M:%S")
                        if hasattr(q.get("exchange_timestamp"), "strftime")
                        else str(q.get("exchange_timestamp"))
                        for q in self.latest_option_quotes.values()
                        if q.get("exchange_timestamp")
                    ],
                    default=None,
                ),
            }
            tmp_path = self.storage.base_dir / "live_state.tmp"
            final_path = self.storage.base_dir / "live_state.json"
            with open(tmp_path, "w") as f:
                json.dump(state, f)
            os.replace(tmp_path, final_path)
        except Exception:
            pass

    def connect(self) -> None:
        """Authenticate with SmartConnect and prepare WebSocket + OptionsMonitor."""
        logger.info("Connecting to Angel One SmartAPI...")
        self.client = SmartConnect(api_key=self.api_key)

        # Header case patch
        orig_rh = self.client.requestHeaders
        self.client.requestHeaders = lambda: {**orig_rh(), "Content-Type": "application/json"}

        totp = pyotp.TOTP(self.totp_secret).now()
        session = self.client.generateSession(self.client_id, self.mpin, totp)
        if not session.get("status"):
            raise ConnectionError(f"Login failed: {session.get('message')}")

        data = session.get("data", {})
        jwt_token = data.get("jwtToken")
        feed_token = data.get("feedToken")

        # Initialize WebSocket V2
        self.ws = SmartWebSocketV2(
            auth_token=jwt_token,
            api_key=self.api_key,
            client_code=self.client_id,
            feed_token=feed_token,
            max_retry_attempt=5,
            retry_delay=5,
        )
        self.ws.on_data = self._on_ws_data
        self.ws.on_open = self._on_ws_open
        self.ws.on_close = self._on_ws_close
        self.ws.on_error = self._on_ws_error

        # Instance patch for websocket-client 1.8+ compatibility:
        # websocket-client passes (ws, close_status, close_msg) to on_close
        orig_on_close = self.ws._on_close
        self.ws._on_close = lambda wsapp, *a, **kw: orig_on_close(wsapp)

        # Initialize OptionsMonitor
        self.options_monitor = OptionsMonitor(self.client, self.cfg)
        logger.info("Angel One connected successfully. WebSocket and OptionsMonitor initialized.")

    def _resolve_active_option_tokens(
        self,
        underlying: str = "NIFTY",
        window_strikes: int = 7,
    ) -> List[Dict[str, Any]]:
        """Resolve ATM ± window_strikes option tokens (15 strikes CE & PE = 30 tokens) for active contract."""
        scrips = []
        if self.options_monitor and self.options_monitor._scrip_master:
            scrips = self.options_monitor._scrip_master
        else:
            cache_p = PROJECT_ROOT / "data" / "cache" / "angel_scrip_master.json"
            if cache_p.exists():
                try:
                    with open(cache_p, "r", encoding="utf-8") as f:
                        scrips = json.load(f)
                except Exception as e:
                    logger.warning("Failed loading scrip master for option tokens: %s", e)

        if not scrips:
            return []

        today = datetime.now().date()
        expiries_found = set()
        for s in scrips:
            if s.get("name") == underlying and s.get("instrumenttype") == "OPTIDX":
                exp = s.get("expiry")
                if exp:
                    try:
                        exp_dt = datetime.strptime(exp, "%d%b%Y").date()
                        if exp_dt >= today:
                            expiries_found.add((exp_dt, exp))
                    except Exception:
                        pass

        if not expiries_found:
            return []

        sorted_exps = sorted(list(expiries_found), key=lambda x: x[0])
        active_expiry = sorted_exps[0][1]

        spot = self.latest_prices.get(underlying, 22700.0)
        step = 50.0 if underlying == "NIFTY" else 100.0
        center = round(spot / step) * step
        target_strikes = set(round(center + i * step, 2) for i in range(-window_strikes, window_strikes + 1))

        seg = "NFO" if underlying in ["NIFTY", "BANKNIFTY"] else "BFO"
        resolved = []
        for s in scrips:
            if (
                s.get("exch_seg") == seg
                and s.get("name") == underlying
                and s.get("expiry") == active_expiry
                and s.get("instrumenttype") == "OPTIDX"
            ):
                strike = round(float(s.get("strike", 0)) / 100.0, 2)
                if strike in target_strikes:
                    tok = str(s.get("token"))
                    sym = str(s.get("symbol"))
                    otype = "CE" if "CE" in sym.upper() else "PE"
                    meta = {
                        "token": tok,
                        "symbol": sym,
                        "underlying": underlying,
                        "strike": strike,
                        "option_type": otype,
                        "instrument_type": "OPTIDX",
                        "expiry": active_expiry,
                        "exch_seg": seg,
                    }
                    self.option_tokens_meta[tok] = meta
                    resolved.append(meta)
        return resolved

    def _on_ws_open(self, wsapp: Any) -> None:
        opt_scrips = self._resolve_active_option_tokens("NIFTY", window_strikes=7)
        opt_tokens = [s["token"] for s in opt_scrips]
        logger.info(
            "WebSocket connected. Subscribing to 9 core tokens + %d NFO option tokens (ATM ± 7 for active contract)...",
            len(opt_tokens),
        )
        token_list = [
            {"exchangeType": 1, "tokens": ["99926000", "99926009"]},
            {"exchangeType": 3, "tokens": ["99919000"]},
            {"exchangeType": 2, "tokens": ["48704", "61471", "48699", "61466"] + opt_tokens},
            {"exchangeType": 4, "tokens": ["864571", "1100929"]},
        ]
        self.ws.subscribe("sub_core", 3, token_list)
        self.active_source = "websocket"

    def _on_ws_close(self, wsapp: Any) -> None:
        logger.warning("WebSocket closed.")
        self.disconnect_count += 1
        self.active_source = "rest"

    def _on_ws_error(self, *args: Any, **kwargs: Any) -> None:
        logger.warning("WebSocket error encountered.")
        self.disconnect_count += 1
        self.active_source = "rest"

    def _token_to_symbol(self, token: str) -> Tuple[str, str]:
        t = str(token)
        if t in self.option_tokens_meta:
            return self.option_tokens_meta[t]["symbol"], "OPTIDX"
        if t == "99926000":
            return "NIFTY", "AMXIDX"
        if t == "99926009":
            return "BANKNIFTY", "AMXIDX"
        if t == "99919000":
            return "SENSEX", "AMXIDX"
        if t == "48704":
            return "NIFTY_FUT_NEAR", "FUTIDX"
        if t == "61471":
            return "NIFTY_FUT_NEXT", "FUTIDX"
        if t == "48699":
            return "BANKNIFTY_FUT_NEAR", "FUTIDX"
        if t == "61466":
            return "BANKNIFTY_FUT_NEXT", "FUTIDX"
        if t == "864571":
            return "SENSEX_FUT_NEAR", "FUTIDX"
        if t == "1100929":
            return "SENSEX_FUT_NEXT", "FUTIDX"
        return f"UNKNOWN_{t}", "UNKNOWN"

    def _on_ws_data(self, wsapp: Any, data: Dict[str, Any]) -> None:
        """Process incoming binary tick / snap quote packet from WebSocket."""
        try:
            now_dt = datetime.now()
            token = str(data.get("token", ""))
            symbol, inst_type = self._token_to_symbol(token)

            raw_ltp = data.get("last_traded_price", 0)
            ltp = raw_ltp / 100.0 if raw_ltp > 0 else self.latest_prices.get(symbol, 0.0)
            ltq = int(data.get("last_traded_quantity", 0))
            vol = int(data.get("volume_trade_for_the_day", 0))
            oi = int(data.get("open_interest", 0))
            exch_ts_raw = data.get("exchange_timestamp", 0)
            exch_ts = (
                datetime.fromtimestamp(exch_ts_raw / 1000.0, tz=self.tz)
                if exch_ts_raw > 0
                else now_dt
            )

            with self._lock:
                self.ticks_count += 1
                self.last_tick_time = time.time()
                self.active_source = "websocket"
                self.latest_prices[symbol] = ltp

                # Update live option quote cache if OPTIDX
                if inst_type == "OPTIDX":
                    self.latest_option_quotes[token] = {
                        "token": token,
                        "symbol": symbol,
                        "ltp": ltp,
                        "oi": oi,
                        "volume": vol,
                        "exchange_timestamp": exch_ts,
                    }

                # Update rolling bar for futures
                if "FUT" in symbol:
                    if symbol not in self.rolling_bars:
                        self.rolling_bars[symbol] = {
                            "open": ltp,
                            "high": ltp,
                            "low": ltp,
                            "close": ltp,
                            "volume": vol,
                            "oi": oi,
                        }
                    else:
                        b = self.rolling_bars[symbol]
                        b["high"] = max(b["high"], ltp)
                        b["low"] = min(b["low"], ltp)
                        b["close"] = ltp
                        b["volume"] = vol
                        b["oi"] = oi

            # Record tick in memory buffer
            tick_row = {
                "exchange_timestamp": exch_ts,
                "received_at": now_dt,
                "token": token,
                "symbol": symbol,
                "instrument_type": inst_type,
                "ltp": ltp,
                "ltq": ltq,
                "volume": vol,
                "source": "websocket",
            }
            with self._lock:
                self._tick_buffer.append(tick_row)

            # Record Depth if present
            best_buy = data.get("best_5_buy_data", [])
            best_sell = data.get("best_5_sell_data", [])
            if best_buy and best_sell:
                b_bid = best_buy[0].get("price", 0.0) / 100.0 if best_buy else 0.0
                b_ask = best_sell[0].get("price", 0.0) / 100.0 if best_sell else 0.0
                tot_b = float(data.get("total_buy_quantity", 0))
                tot_s = float(data.get("total_sell_quantity", 0))
                imbalance = (tot_b - tot_s) / (tot_b + tot_s) if (tot_b + tot_s) > 0 else 0.0
                spread = max(0.0, b_ask - b_bid)

                if inst_type == "OPTIDX" and token in self.latest_option_quotes:
                    self.latest_option_quotes[token]["best_bid"] = b_bid
                    self.latest_option_quotes[token]["best_ask"] = b_ask
                    self.latest_option_quotes[token]["spread"] = spread

                depth_row = {
                    "timestamp": now_dt,
                    "token": token,
                    "symbol": symbol,
                    "best_bid": b_bid,
                    "best_ask": b_ask,
                    "depth_imbalance": round(imbalance, 4),
                    "spread": round(spread, 2),
                    "source": "websocket",
                }
                with self._lock:
                    self._depth_buffer.append(depth_row)

            self._flush_tick_buffer(force=False)

        except Exception as e:
            logger.debug("Error processing tick: %s", e)

    def _poll_rest_fallback(self) -> None:
        """Poll REST LTP/Quote for core tokens if WebSocket ticks stall for >10s."""
        now_dt = datetime.now()
        logger.info("Watchdog: WebSocket ticks stalled. Executing REST fallback poll...")
        try:
            # Poll Spot LTP
            res_spot = shared_rate_limiter.execute_with_backoff(
                "getLtpData",
                self.client.getMarketData,
                "LTP",
                {"NSE": ["99926000", "99926009"], "BSE": ["99919000"]},
            )
            fetched_spot = res_spot.get("data", {}).get("fetched", [])
            ticks_batch = []
            for item in fetched_spot:
                tok = str(item.get("symbolToken"))
                sym, inst = self._token_to_symbol(tok)
                ltp = float(item.get("ltp", 0.0))
                self.latest_prices[sym] = ltp
                ticks_batch.append({
                    "exchange_timestamp": now_dt,
                    "received_at": now_dt,
                    "token": tok,
                    "symbol": sym,
                    "instrument_type": inst,
                    "ltp": ltp,
                    "ltq": 0,
                    "volume": 0,
                    "source": "rest",
                })

            # Poll Futures Quote
            res_fut = shared_rate_limiter.execute_with_backoff(
                "quote",
                self.client.getMarketData,
                "FULL",
                {"NFO": ["48704", "61471", "48699", "61466"], "BFO": ["864571", "1100929"]},
            )
            fetched_fut = res_fut.get("data", {}).get("fetched", [])
            for item in fetched_fut:
                tok = str(item.get("symbolToken"))
                sym, inst = self._token_to_symbol(tok)
                ltp = float(item.get("ltp", 0.0))
                vol = int(item.get("tradeVolume", 0))
                oi = int(item.get("opnInterest", 0))
                self.latest_prices[sym] = ltp

                with self._lock:
                    if sym not in self.rolling_bars:
                        self.rolling_bars[sym] = {
                            "open": ltp,
                            "high": ltp,
                            "low": ltp,
                            "close": ltp,
                            "volume": vol,
                            "oi": oi,
                        }
                    else:
                        b = self.rolling_bars[sym]
                        b["high"] = max(b["high"], ltp)
                        b["low"] = min(b["low"], ltp)
                        b["close"] = ltp
                        b["volume"] = vol
                        b["oi"] = oi

                ticks_batch.append({
                    "exchange_timestamp": now_dt,
                    "received_at": now_dt,
                    "token": tok,
                    "symbol": sym,
                    "instrument_type": inst,
                    "ltp": ltp,
                    "ltq": 0,
                    "volume": vol,
                    "source": "rest",
                })

            if ticks_batch:
                self.storage.insert_ticks(ticks_batch)
                self.ticks_count += len(ticks_batch)
                self.last_tick_time = time.time()
                self.active_source = "rest"
        except Exception as e:
            logger.warning("REST fallback poll error: %s", e)

    def _flush_futures_bars(self) -> None:
        """Construct 1-minute futures bars with volume differencing and VWAP."""
        now_dt = datetime.now()
        bar_rows = []
        tok_map = {
            "NIFTY_FUT_NEAR": "48704",
            "NIFTY_FUT_NEXT": "61471",
            "BANKNIFTY_FUT_NEAR": "48699",
            "BANKNIFTY_FUT_NEXT": "61466",
            "SENSEX_FUT_NEAR": "864571",
            "SENSEX_FUT_NEXT": "1100929",
        }
        with self._lock:
            for sym, b in list(self.rolling_bars.items()):
                tracker = self.vwap_trackers.get(sym)
                exp = self.FUTURES_EXPIRIES.get(sym)
                vwap = tracker.update(
                    high=b["high"],
                    low=b["low"],
                    close=b["close"],
                    current_cum_vol=b["volume"],
                    contract_expiry=exp,
                ) if tracker else b["close"]

                bar_vol = compute_bar_volume(
                    current_cum_vol=b["volume"],
                    prev_cum_vol=tracker.last_cum_day_vol if tracker else 0,
                )

                tok = tok_map.get(sym, "0")
                bar_rows.append({
                    "timestamp": now_dt,
                    "symbol": sym,
                    "token": tok,
                    "contract_expiry": exp,
                    "open": b["open"],
                    "high": b["high"],
                    "low": b["low"],
                    "close": b["close"],
                    "volume": bar_vol,
                    "oi": b["oi"],
                    "vwap": vwap,
                    "source": self.active_source,
                })
                # Reset rolling bar for next minute
                self.rolling_bars[sym] = {
                    "open": b["close"],
                    "high": b["close"],
                    "low": b["close"],
                    "close": b["close"],
                    "volume": b["volume"],
                    "oi": b["oi"],
                }

        if bar_rows:
            self.storage.insert_futures_bars(bar_rows)

    def _options_snapshot_cycle(self) -> None:
        """Fetch 1-minute options snapshot for all underlyings and store derived metrics."""
        if not self.options_monitor:
            return
        for u in ["NIFTY", "BANKNIFTY", "SENSEX"]:
            spot = self.latest_prices.get(u, 24000.0)
            fut = self.latest_prices.get(f"{u}_FUT_NEAR", self.latest_prices.get(f"{u}_FUT"))
            opts, metrics = self.options_monitor.fetch_snapshots(u, spot, fut)
            if opts:
                self.storage.insert_options_snapshots(opts)
            if metrics:
                roll_mgr = self.roll_managers.get(u)
                if roll_mgr:
                    near_sym = f"{u}_FUT_NEAR"
                    next_sym = f"{u}_FUT_NEXT"
                    near_exp = self.FUTURES_EXPIRIES.get(near_sym)
                    next_exp = self.FUTURES_EXPIRIES.get(next_sym)
                    near_bar = self.rolling_bars.get(near_sym, {})
                    next_bar = self.rolling_bars.get(next_sym, {})
                    if near_bar and next_bar and near_exp and next_exp:
                        roll_rec = roll_mgr.evaluate_roll(
                            current_time=datetime.now(),
                            near_expiry=near_exp,
                            near_symbol=near_sym,
                            near_price=near_bar.get("close", 0.0),
                            near_oi=near_bar.get("oi", 0),
                            near_vol=near_bar.get("volume", 0),
                            next_expiry=next_exp,
                            next_symbol=next_sym,
                            next_price=next_bar.get("close", 0.0),
                            next_oi=next_bar.get("oi", 0),
                            next_vol=next_bar.get("volume", 0),
                        )
                        metrics["roll_active_contract"] = roll_rec.active_contract
                        metrics["roll_spread"] = roll_rec.roll_spread
                self.storage.insert_derived_metrics([metrics])

    def _reconcile_bars_cycle(self) -> None:
        """1-minute bar reconciler: fetch just-completed 1m bars for indices and nearest futures.
        
        Runs once a minute using shared rate limiter (~4 calls per minute) and stores as official bars.
        """
        now_ist = datetime.now(self.tz)
        if not self.cfg.is_trading_day(now_ist.date()):
            return
        if now_ist.time() < datetime.strptime("09:16:00", "%H:%M:%S").time():
            return

        end_m = now_ist.replace(second=0, microsecond=0)
        start_m = end_m - timedelta(minutes=2)

        start_str = start_m.strftime("%Y-%m-%d %H:%M")
        end_str = end_m.strftime("%Y-%m-%d %H:%M")

        targets = [
            ("NIFTY", "NSE", "99926000", True),
            ("BANKNIFTY", "NSE", "99926009", True),
            ("SENSEX", "BSE", "99919000", True),
            ("NIFTY_FUT_NEAR", "NFO", "61471", False),
        ]

        for sym, exch, tok, is_index in targets:
            try:
                params = {
                    "exchange": exch,
                    "symboltoken": tok,
                    "interval": "ONE_MINUTE",
                    "fromdate": start_str,
                    "todate": end_str,
                }
                res = shared_rate_limiter.execute_with_backoff(
                    "getCandleData",
                    self.client.getCandleData,
                    params,
                )
                raw_bars = res.get("data") or []
                if raw_bars:
                    b = raw_bars[-1]
                    ts_str, op, hi, lo, cl, vol = b
                    if is_index:
                        self.storage.insert_index_1m_bars([{
                            "timestamp": pd.to_datetime(ts_str),
                            "symbol": sym,
                            "open": float(op),
                            "high": float(hi),
                            "low": float(lo),
                            "close": float(cl),
                            "volume": 0.0,
                            "source": "official_reconciled",
                        }])
                    else:
                        self.storage.insert_futures_bars([{
                            "timestamp": pd.to_datetime(ts_str),
                            "symbol": sym,
                            "token": tok,
                            "contract_expiry": self.FUTURES_EXPIRIES.get(sym, date(2026, 11, 23)),
                            "open": float(op),
                            "high": float(hi),
                            "low": float(lo),
                            "close": float(cl),
                            "volume": int(vol),
                            "oi": 0,
                            "vwap": float(cl),
                            "source": "official_reconciled",
                        }])
                    logger.debug("Reconciled official 1m bar for [%s]: %s C=%.2f", sym, ts_str, float(cl))
            except Exception as e:
                logger.warning("Reconciler cycle error for [%s]: %s", sym, e)

    def _startup_reconnect_gap_fill(self) -> None:
        """Startup/reconnect gap-fill from historical API for any missing 1m bars."""
        now_ist = datetime.now(self.tz)
        if not self.cfg.is_trading_day(now_ist.date()):
            return

        m_start = now_ist.replace(hour=9, minute=15, second=0, microsecond=0)
        m_end = now_ist.replace(hour=15, minute=30, second=0, microsecond=0)
        if now_ist <= m_start:
            return

        target_end = min(now_ist, m_end)
        latest_ts = self.storage.get_latest_index_timestamp("NIFTY")
        fetch_from = m_start if latest_ts is None else (latest_ts + timedelta(minutes=1))

        if (target_end - fetch_from).total_seconds() < 60:
            return

        logger.info(
            "Startup/Reconnect gap-fill: fetching missing interval %s to %s from historical API...",
            fetch_from.strftime("%H:%M"),
            target_end.strftime("%H:%M"),
        )
        for sym, exch, tok in [("NIFTY", "NSE", "99926000"), ("BANKNIFTY", "NSE", "99926009"), ("SENSEX", "BSE", "99919000")]:
            try:
                params = {
                    "exchange": exch,
                    "symboltoken": tok,
                    "interval": "ONE_MINUTE",
                    "fromdate": fetch_from.strftime("%Y-%m-%d %H:%M"),
                    "todate": target_end.strftime("%Y-%m-%d %H:%M"),
                }
                res = shared_rate_limiter.execute_with_backoff(
                    "getCandleData",
                    self.client.getCandleData,
                    params,
                )
                bars = res.get("data") or []
                rows = []
                for b in bars:
                    ts_str, op, hi, lo, cl, _ = b
                    rows.append({
                        "timestamp": pd.to_datetime(ts_str),
                        "symbol": sym,
                        "open": float(op),
                        "high": float(hi),
                        "low": float(lo),
                        "close": float(cl),
                        "volume": 0.0,
                        "source": "broker_history",
                    })
                if rows:
                    self.storage.insert_index_1m_bars(rows)
                    logger.info("Startup gap-filled %d official 1m bars for [%s].", len(rows), sym)
            except Exception as e:
                logger.warning("Startup gap-fill error for [%s]: %s", sym, e)

    def _record_health(self) -> None:
        """Insert health heartbeat into recorder_health table with stale alert checking."""
        now_dt = datetime.now()
        now_ist = datetime.now(self.tz)
        uptime = time.time() - (self.start_time or time.time())
        rate = round(self.ticks_count / max(uptime, 1.0), 2)
        try:
            mem = round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024 * 1024), 2)
        except Exception:
            mem = 0.0

        tick_age = round(time.time() - self.last_tick_time, 1) if self.last_tick_time > 0 else 999.0

        # Heartbeat alert check
        is_market_session = (
            self.cfg.is_trading_day(now_ist.date())
            and datetime.strptime("09:15:00", "%H:%M:%S").time() <= now_ist.time() <= datetime.strptime("15:30:00", "%H:%M:%S").time()
        )

        status = "RUNNING" if self.running else "STOPPED"
        if is_market_session:
            if tick_age > 15.0:
                status = "ALERT_STALE"
                logger.critical(
                    "HEARTBEAT ALERT: Market data STALE! Last tick age is %.1fs (> 15.0s threshold) during active trading hours!",
                    tick_age,
                )
            elif not self.running:
                status = "ALERT_STOPPED"
                logger.critical("HEARTBEAT ALERT: Market recorder is STOPPED during active trading hours!")

        health_row = {
            "timestamp": now_dt,
            "status": status,
            "uptime_seconds": round(uptime, 1),
            "ticks_received": self.ticks_count,
            "tick_rate_per_sec": rate,
            "active_source": self.active_source,
            "disconnect_count": self.disconnect_count,
            "last_tick_age_seconds": tick_age,
            "memory_mb": mem,
        }
        self.storage.insert_health(health_row)
        logger.info(
            "Health Heartbeat: status=%s | uptime=%.1fs | ticks=%d (%.2f/s) | source=%s | tick_age=%.1fs | mem=%.1fMB",
            health_row["status"],
            health_row["uptime_seconds"],
            health_row["ticks_received"],
            health_row["tick_rate_per_sec"],
            health_row["active_source"],
            health_row["last_tick_age_seconds"],
            health_row["memory_mb"],
        )

    def run(self, duration_seconds: Optional[int] = None) -> Dict[str, Any]:
        """Main recorder loop with threading for WS, watchdog, and 1-minute options polling."""
        self.connect()
        self.running = True
        self.start_time = time.time()
        self.last_tick_time = time.time()

        # Startup gap-fill for any missing 1m bars before launch
        self._startup_reconnect_gap_fill()

        # Start WebSocket in daemon thread
        ws_thread = threading.Thread(target=self.ws.connect, daemon=True)
        ws_thread.start()

        logger.info("Recorder engine started. Monitoring market live...")
        last_min_cycle = time.time()
        last_health_cycle = time.time()

        try:
            while self.running:
                now = time.time()
                if duration_seconds and (now - self.start_time) >= duration_seconds:
                    logger.info("Duration limit reached (%ds). Stopping recorder.", duration_seconds)
                    break

                # 10s Watchdog: If no tick received for 10s, trigger REST fallback
                if (now - self.last_tick_time) >= 10.0:
                    self._poll_rest_fallback()

                # 1-Minute Cycle (Options snapshot, Futures bar flush, and 1m Reconciler)
                cycle_interval = 20.0 if (duration_seconds and duration_seconds <= 120) else 60.0
                if (now - last_min_cycle) >= cycle_interval:
                    self._flush_futures_bars()
                    self._options_snapshot_cycle()
                    self._reconcile_bars_cycle()
                    last_min_cycle = now

                # Health Heartbeat (every 10s in test mode, 60s in production)
                health_interval = 10.0 if (duration_seconds and duration_seconds <= 120) else 60.0
                if (now - last_health_cycle) >= health_interval:
                    self._record_health()
                    last_health_cycle = now

                time.sleep(1.0)

        except KeyboardInterrupt:
            logger.info("Shutdown requested via KeyboardInterrupt.")
        finally:
            self.stop()

        return self.get_summary()

    def stop(self) -> None:
        self.running = False
        self._flush_tick_buffer(force=True)
        try:
            if self.ws:
                self.ws.close_connection()
        except Exception:
            pass
        self._record_health()
        logger.info("Recorder engine stopped.")

    def get_summary(self) -> Dict[str, Any]:
        uptime = time.time() - (self.start_time or time.time())
        return {
            "uptime_seconds": round(uptime, 1),
            "ticks_received": self.ticks_count,
            "tick_rate_per_sec": round(self.ticks_count / max(uptime, 1.0), 2),
            "active_source": self.active_source,
            "disconnect_count": self.disconnect_count,
            "disk_usage": self.storage.get_disk_usage(),
        }
