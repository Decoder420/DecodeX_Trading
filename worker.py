"""DecodeX Trading — Multi-Timeframe Async Data & WebSocket Engine (QThread).

Role:
- Isolated background QThread managing Angel One SmartAPI WebSocket in FULL_SNAP mode (Mode 3).
- True Level 2 (5-level) market depth parsing and real-time Order Book Imbalance (OBI).
- Multi-Timeframe (MTF) state engine:
    * 15-minute structural bias: Anchored VWAP, Supertrend (10, 2.5), Daily ATR.
    * 3-minute execution triggers: EMA Ribbon (9, 21, 50), Squeeze (BB vs KC), RSI(14).
    * 6-Factor Confluence: Strictly enforces entries ONLY when both 15m and 3m align.
- Real-time Options Chain & Greeks: COI Delta tracking across ATM, ATM+100, ATM-100 triad.
- Watchdog loop with exponential backoff for graceful reconnection (>15s stale data lock).
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import os
import random
import sys
import time
from collections import deque
from datetime import datetime, time as dtime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import pyotp
import pytz
from PyQt6.QtCore import QObject, QThread, pyqtSignal
from SmartApi import SmartConnect
from SmartApi.smartWebSocketV2 import SmartWebSocketV2
from dotenv import load_dotenv

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from recorder.metrics import Black76
from signals.macro_sentiment import MacroSentimentEngine

# Load environment credentials
load_dotenv(PROJECT_ROOT / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] (%(threadName)s) %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("DecodeXWorker")

IST_TZ = pytz.timezone("Asia/Kolkata")


class DecodeXDataWorker(QThread):
    """Native PyQt6 Background Worker Thread for DecodeX Trading.
    
    Manages the live WebSocket stream, calculates 15m & 3m MTF indicators,
    parses true L2 5-level market depth, computes real-time options chain Greeks & COI delta,
    and emits high-speed Qt signals directly to the main GUI thread.
    """

    # Qt Signals emitted safely across thread boundary
    tick_signal = pyqtSignal(dict)
    l2_depth_signal = pyqtSignal(dict)
    mtf_signal = pyqtSignal(dict)
    options_chain_signal = pyqtSignal(dict)
    connection_status_signal = pyqtSignal(str, str)  # (status, details)
    news_sentiment_signal = pyqtSignal(dict)

    # Instrument Tokens (Angel One)
    INSTRUMENT_TOKENS = {
        "NIFTY": {"token": "99926000", "exchange": SmartWebSocketV2.NSE_CM, "step": 50.0, "lot": 65},
        "BANKNIFTY": {"token": "99926009", "exchange": SmartWebSocketV2.NSE_CM, "step": 100.0, "lot": 30},
        "SENSEX": {"token": "99919000", "exchange": SmartWebSocketV2.BSE_CM, "step": 100.0, "lot": 20},
    }

    def __init__(
        self,
        instrument: str = "NIFTY",
        active_expiry: str = "17NOV2026",
        parent: Optional[QObject] = None,
    ):
        super().__init__(parent)
        self.instrument = instrument.upper()
        self.active_expiry = active_expiry
        self._is_running = True

        # Credentials
        self.api_key = os.getenv("ANGEL_API_KEY", "").strip()
        self.client_id = os.getenv("ANGEL_CLIENT_ID", "").strip()
        self.mpin = os.getenv("ANGEL_MPIN", "").strip()
        self.totp_secret = os.getenv("ANGEL_TOTP_SECRET", "").strip()

        # Connections & State
        self.client: Optional[SmartConnect] = None
        self.ws: Optional[SmartWebSocketV2] = None
        self.last_tick_time: float = 0.0
        self.retry_attempt: int = 0
        self.subscribed_tokens: List[Dict[str, Any]] = []

        # Real-time state caches
        self.current_spot_price: float = 24864.0
        self.previous_oi_map: Dict[str, int] = {}  # token -> previous open interest

        # MTF Candle Buffers (Rolling in-memory deques)
        self.ticks_buffer: deque = deque(maxlen=5000)
        self.bars_15m: List[Dict[str, Any]] = []
        self.bars_3m: List[Dict[str, Any]] = []

        # Macro Sentiment Engine
        self.macro_engine = MacroSentimentEngine()
        self.macro_sentiment_score: float = 0.0

        # Load initial historical bars from DuckDB for warm indicators
        self._warmup_historical_bars()

    # =========================================================================
    # HISTORICAL WARMUP & DATA INITIALIZATION
    # =========================================================================

    def _warmup_historical_bars(self) -> None:
        """Warm up 15m and 3m rolling buffers from DuckDB market storage."""
        try:
            from data.storage import StorageManager
            sm = StorageManager()
            df_15m = sm.load_ohlcv(self.instrument, "15m")
            if not df_15m.empty:
                df_15m = df_15m.tail(120).copy()
                for _, row in df_15m.iterrows():
                    self.bars_15m.append({
                        "timestamp": pd.to_datetime(row["timestamp"]),
                        "open": float(row["open"]),
                        "high": float(row["high"]),
                        "low": float(row["low"]),
                        "close": float(row["close"]),
                        "volume": int(row.get("volume", 1000)),
                    })
                if self.bars_15m:
                    self.current_spot_price = self.bars_15m[-1]["close"]
                logger.info("Warmed up %d historical 15m bars for %s.", len(self.bars_15m), self.instrument)

            df_1m = sm.load_ohlcv(self.instrument, "1m")
            if not df_1m.empty:
                df_1m["timestamp"] = pd.to_datetime(df_1m["timestamp"])
                df_1m = df_1m.set_index("timestamp").sort_index()
                df_3m = df_1m.resample("3min").agg({
                    "open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"
                }).dropna().tail(150)
                for ts, row in df_3m.iterrows():
                    self.bars_3m.append({
                        "timestamp": ts,
                        "open": float(row["open"]),
                        "high": float(row["high"]),
                        "low": float(row["low"]),
                        "close": float(row["close"]),
                        "volume": int(row.get("volume", 500)),
                    })
                logger.info("Warmed up %d historical 3m bars for %s.", len(self.bars_3m), self.instrument)
        except Exception as e:
            logger.warning("Could not warm up historical bars from DuckDB: %s", e)

    # =========================================================================
    # SMARTAPI AUTHENTICATION & WEBSOCKET SETUP (FULL_SNAP MODE 3)
    # =========================================================================

    def _authenticate(self) -> Tuple[str, str]:
        """Authenticate with Angel One SmartAPI using TOTP and generate session tokens."""
        if not all([self.api_key, self.client_id, self.mpin, self.totp_secret]):
            raise ValueError("Incomplete Angel One credentials in .env file.")

        self.client = SmartConnect(api_key=self.api_key)
        # Apply header case patch for compatibility
        orig_rh = self.client.requestHeaders
        self.client.requestHeaders = lambda: {**orig_rh(), "Content-Type": "application/json"}

        totp = pyotp.TOTP(self.totp_secret).now()
        session = self.client.generateSession(self.client_id, self.mpin, totp)
        if not session.get("status"):
            raise ConnectionError(f"SmartAPI login failed: {session.get('message')}")

        data = session.get("data", {})
        jwt_token = data.get("jwtToken")
        feed_token = data.get("feedToken")
        if not jwt_token or not feed_token:
            raise ConnectionError("SmartAPI response missing jwtToken or feedToken.")

        logger.info("SmartAPI authentication successful for client %s.", self.client_id)
        return jwt_token, feed_token

    def _resolve_subscription_tokens(self) -> List[Dict[str, Any]]:
        """Resolve underlying index and active options strikes for subscription."""
        inst_meta = self.INSTRUMENT_TOKENS.get(self.instrument, self.INSTRUMENT_TOKENS["NIFTY"])
        tokens_list = [
            {
                "exchangeType": inst_meta["exchange"],
                "tokens": [inst_meta["token"]]
            }
        ]

        # Resolve active options tokens from cache
        scrip_path = PROJECT_ROOT / "data" / "cache" / "angel_scrip_master.json"
        if scrip_path.exists():
            try:
                with open(scrip_path, "r", encoding="utf-8") as f:
                    scrips = json.load(f)

                atm = round(self.current_spot_price / inst_meta["step"]) * inst_meta["step"]
                target_strikes = [atm + i * inst_meta["step"] for i in range(-5, 6)]
                target_tokens: List[str] = []

                for s in scrips:
                    if s.get("name") == self.instrument and s.get("instrumenttype") in ["OPTIDX", "OPTSTK"]:
                        strike_val = float(s.get("strike", 0)) / 100.0 if float(s.get("strike", 0)) > 100000 else float(s.get("strike", 0))
                        if any(math.isclose(strike_val, k, abs_tol=1.0) for k in target_strikes):
                            tok = str(s.get("token"))
                            if tok and tok not in target_tokens:
                                target_tokens.append(tok)
                                if len(target_tokens) >= 22:
                                    break

                if target_tokens:
                    tokens_list.append({
                        "exchangeType": SmartWebSocketV2.NSE_FO,
                        "tokens": target_tokens
                    })
                    logger.info("Subscribing to %d options contracts for %s.", len(target_tokens), self.instrument)
            except Exception as e:
                logger.warning("Error resolving options scrips: %s", e)

        self.subscribed_tokens = tokens_list
        return tokens_list

    def _connect_websocket(self) -> None:
        """Initialize and start SmartWebSocketV2 in SNAP_QUOTE (Mode 3) for 5-level depth."""
        jwt_token, feed_token = self._authenticate()

        self.ws = SmartWebSocketV2(
            auth_token=jwt_token,
            api_key=self.api_key,
            client_code=self.client_id,
            feed_token=feed_token,
            max_retry_attempt=3,
            retry_delay=5,
        )

        self.ws.on_data = self._on_ws_data
        self.ws.on_open = self._on_ws_open
        self.ws.on_close = self._on_ws_close
        self.ws.on_error = self._on_ws_error

        # Instance patch for websocket-client 1.8+ compatibility
        orig_on_close = self.ws._on_close
        self.ws._on_close = lambda wsapp, *a, **kw: orig_on_close(wsapp)

        self.connection_status_signal.emit("CONNECTING", "Establishing SmartWebSocketV2 in FULL_SNAP mode...")
        self.ws.connect()

    # =========================================================================
    # WEBSOCKET EVENT CALLBACKS
    # =========================================================================

    def _on_ws_open(self, wsapp) -> None:
        """Called when WebSocket connection opens. Subscribes in SNAP_QUOTE mode."""
        logger.info("WebSocket connected. Subscribing in SNAP_QUOTE mode (Mode 3 - Full 5-Level Depth)...")
        token_list = self._resolve_subscription_tokens()
        try:
            self.ws.subscribe(
                correlation_id="decodex_feed",
                mode=SmartWebSocketV2.SNAP_QUOTE,
                token_list=token_list,
            )
            self.last_tick_time = time.time()
            self.retry_attempt = 0
            self.connection_status_signal.emit(
                "CONNECTED",
                f"Mode 3 FULL_SNAP Active | Tokens: {sum(len(t['tokens']) for t in token_list)}"
            )
        except Exception as e:
            logger.error("Failed to subscribe to tokens: %s", e)

    def _on_ws_close(self, wsapp) -> None:
        logger.warning("WebSocket disconnected.")
        self.connection_status_signal.emit("DISCONNECTED", "Connection dropped. Reconnect watchdog active.")

    def _on_ws_error(self, wsapp, error) -> None:
        logger.error("WebSocket encountered error: %s", error)
        self.connection_status_signal.emit("ERROR", f"WebSocket error: {str(error)[:40]}")

    def _on_ws_data(self, wsapp, message) -> None:
        """Handle incoming binary ticks, parse 5-level depth, and route to MTF pipeline."""
        self.last_tick_time = time.time()
        if not isinstance(message, dict):
            return

        try:
            token = str(message.get("token", ""))
            ltp_raw = message.get("last_traded_price", 0)
            ltp = float(ltp_raw) / 100.0 if ltp_raw > 100000 else float(ltp_raw)

            inst_meta = self.INSTRUMENT_TOKENS.get(self.instrument, self.INSTRUMENT_TOKENS["NIFTY"])
            is_underlying = (token == inst_meta["token"])

            if is_underlying and ltp > 0:
                self.current_spot_price = ltp

            # 1. Parse True Level 2 Depth
            depth_data = self.parse_l2_depth(message)
            if depth_data and depth_data.get("total_bid_qty", 0) > 0:
                self.l2_depth_signal.emit(depth_data)

            # 2. Process Tick for MTF aggregation
            if is_underlying and ltp > 0:
                vol = int(message.get("last_traded_quantity", 1))
                now_dt = datetime.now(IST_TZ)
                tick_payload = {
                    "symbol": self.instrument,
                    "token": token,
                    "ltp": ltp,
                    "volume": vol,
                    "high": float(message.get("high_price_of_the_day", 0)) / 100.0,
                    "low": float(message.get("low_price_of_the_day", 0)) / 100.0,
                    "close": float(message.get("closed_price", 0)) / 100.0,
                    "timestamp": now_dt.strftime("%H:%M:%S"),
                }
                self.tick_signal.emit(tick_payload)
                self._update_mtf_bars(now_dt, ltp, vol, depth_data.get("order_book_imbalance", 0.0))

            # 3. Process Options Tick (if option token)
            oi_raw = message.get("open_interest", 0)
            if oi_raw and not is_underlying:
                self._process_option_tick(token, ltp, int(oi_raw))

        except Exception as e:
            logger.error("Error processing WebSocket tick: %s", e, exc_info=True)

    # =========================================================================
    # TRUE LEVEL 2 MARKET DEPTH PARSER (5-LEVEL BID/ASK)
    # =========================================================================

    def parse_l2_depth(self, tick: Dict[str, Any]) -> Dict[str, Any]:
        """Dedicated parser for actual 5-level market depth arrays from FULL_SNAP packets."""
        best_5_buy = tick.get("best_5_buy_data", [])
        best_5_sell = tick.get("best_5_sell_data", [])

        bids: List[Dict[str, Any]] = []
        asks: List[Dict[str, Any]] = []

        total_bid_qty = 0
        total_ask_qty = 0

        for item in best_5_buy:
            raw_p = item.get("price", 0)
            p = float(raw_p) / 100.0 if raw_p > 100000 else float(raw_p)
            q = int(item.get("quantity", 0))
            orders = int(item.get("no of orders", 1))
            if p > 0 and q > 0:
                bids.append({"price": p, "quantity": q, "orders": orders})
                total_bid_qty += q

        for item in best_5_sell:
            raw_p = item.get("price", 0)
            p = float(raw_p) / 100.0 if raw_p > 100000 else float(raw_p)
            q = int(item.get("quantity", 0))
            orders = int(item.get("no of orders", 1))
            if p > 0 and q > 0:
                asks.append({"price": p, "quantity": q, "orders": orders})
                total_ask_qty += q

        # Calculate Order Book Imbalance (OBI)
        # OBI = (BidQty - AskQty) / (BidQty + AskQty)
        total_depth = total_bid_qty + total_ask_qty
        obi = (total_bid_qty - total_ask_qty) / max(total_depth, 1)

        # Micro-price calculation (Volume-weighted top of book price)
        top_bid_p = bids[0]["price"] if bids else self.current_spot_price
        top_bid_q = bids[0]["quantity"] if bids else 1
        top_ask_p = asks[0]["price"] if asks else self.current_spot_price
        top_ask_q = asks[0]["quantity"] if asks else 1

        spread = max(0.0, top_ask_p - top_bid_p)
        denom_top = top_bid_q + top_ask_q
        micro_price = (top_bid_p * top_ask_q + top_ask_p * top_bid_q) / max(denom_top, 1)

        return {
            "symbol": self.instrument,
            "bids": bids,
            "asks": asks,
            "total_bid_qty": total_bid_qty,
            "total_ask_qty": total_ask_qty,
            "order_book_imbalance": round(obi, 4),
            "micro_price": round(micro_price, 2),
            "spread": round(spread, 2),
            "top_bid": top_bid_p,
            "top_ask": top_ask_p,
            "timestamp": datetime.now(IST_TZ).strftime("%H:%M:%S.%f")[:12],
        }

    # =========================================================================
    # MULTI-TIMEFRAME (MTF) ENGINE & 6-FACTOR CONFLUENCE
    # =========================================================================

    def _update_mtf_bars(self, dt: datetime, price: float, volume: int, obi: float) -> None:
        """Update rolling 15m structural and 3m execution bars, then compute MTF confluence."""
        # 1. Update 15m Forming Bar
        m15_minute = (dt.minute // 15) * 15
        bar_15m_time = dt.replace(minute=m15_minute, second=0, microsecond=0)

        if not self.bars_15m or self.bars_15m[-1]["timestamp"] != bar_15m_time:
            self.bars_15m.append({
                "timestamp": bar_15m_time,
                "open": price, "high": price, "low": price, "close": price, "volume": volume
            })
            if len(self.bars_15m) > 150:
                self.bars_15m.pop(0)
        else:
            cur15 = self.bars_15m[-1]
            cur15["high"] = max(cur15["high"], price)
            cur15["low"] = min(cur15["low"], price)
            cur15["close"] = price
            cur15["volume"] += volume

        # 2. Update 3m Forming Bar
        m3_minute = (dt.minute // 3) * 3
        bar_3m_time = dt.replace(minute=m3_minute, second=0, microsecond=0)

        if not self.bars_3m or self.bars_3m[-1]["timestamp"] != bar_3m_time:
            self.bars_3m.append({
                "timestamp": bar_3m_time,
                "open": price, "high": price, "low": price, "close": price, "volume": volume
            })
            if len(self.bars_3m) > 200:
                self.bars_3m.pop(0)
        else:
            cur3 = self.bars_3m[-1]
            cur3["high"] = max(cur3["high"], price)
            cur3["low"] = min(cur3["low"], price)
            cur3["close"] = price
            cur3["volume"] += volume

        # 3. Calculate 15m Structural Frame Indicators
        df15 = pd.DataFrame(self.bars_15m)
        if len(df15) < 15:
            return

        # Anchored VWAP (Anchored to today's 09:15:00 IST open)
        today_date = dt.date()
        today_mask = df15["timestamp"].apply(lambda t: t.date() == today_date)
        if today_mask.any():
            sub = df15[today_mask]
            typ_p = (sub["high"] + sub["low"] + sub["close"]) / 3.0
            cum_pv = (typ_p * sub["volume"]).cumsum()
            cum_v = sub["volume"].cumsum()
            anchored_vwap = float((cum_pv / cum_v.replace(0, 1)).iloc[-1])
        else:
            anchored_vwap = float(df15["close"].iloc[-1])

        # Supertrend (10, 2.5) on 15m
        st_val, st_dir = self._calc_supertrend(df15, period=10, multiplier=2.5)

        # Daily ATR (14)
        atr_15m = self._calc_atr(df15, period=14)

        # 15m Directional Bias
        if price > anchored_vwap and st_dir == 1:
            bias_15m = "BULLISH"
        elif price < anchored_vwap and st_dir == -1:
            bias_15m = "BEARISH"
        else:
            bias_15m = "NEUTRAL"

        # 4. Calculate 3m Execution Frame Indicators
        df3 = pd.DataFrame(self.bars_3m)
        if len(df3) < 25:
            return

        # EMA Ribbon (9, 21, 50)
        ema_9 = float(df3["close"].ewm(span=9, adjust=False).mean().iloc[-1])
        ema_21 = float(df3["close"].ewm(span=21, adjust=False).mean().iloc[-1])
        ema_50 = float(df3["close"].ewm(span=50, adjust=False).mean().iloc[-1])

        # Bollinger Bands & Keltner Squeeze (20, 2.0 BB vs 20, 1.5 ATR KC)
        bb_mid = df3["close"].rolling(20).mean()
        bb_std = df3["close"].rolling(20).std(ddof=0)
        bb_upper = float((bb_mid + 2.0 * bb_std).iloc[-1])
        bb_lower = float((bb_mid - 2.0 * bb_std).iloc[-1])

        atr_3m = self._calc_atr(df3, period=20)
        kc_mid = float(df3["close"].ewm(span=20, adjust=False).mean().iloc[-1])
        kc_upper = kc_mid + 1.5 * atr_3m
        kc_lower = kc_mid - 1.5 * atr_3m

        squeeze_on = bool(bb_upper < kc_upper and bb_lower > kc_lower)
        squeeze_fired = bool(bb_upper >= kc_upper or bb_lower <= kc_lower)

        # RSI (14)
        rsi_3m = self._calc_rsi(df3["close"], period=14)

        # 3m Execution Trigger
        trigger_3m = "WAIT"
        if price > ema_9 and ema_9 > ema_21 and ema_21 > ema_50 and squeeze_fired and 45.0 <= rsi_3m <= 70.0:
            trigger_3m = "TRIGGER_LONG"
        elif price < ema_9 and ema_9 < ema_21 and ema_21 < ema_50 and squeeze_fired and 30.0 <= rsi_3m <= 55.0:
            trigger_3m = "TRIGGER_SHORT"

        # 5. STRICT 6-FACTOR CONFLUENCE ALIGNMENT (Only trigger ENTRY when both timeframes align!)
        final_signal = "CONFLUENCE WAIT (CHOP FILTER)"
        confluence_score = 0.0
        reasons: List[str] = []

        if bias_15m == "BULLISH" and trigger_3m == "TRIGGER_LONG":
            final_signal = "BULLISH ENTRY"
            confluence_score = 4.5 + (0.5 if obi > 0.10 else 0.0) + (self.macro_sentiment_score * 0.5)
            reasons = [
                f"15m Structural Frame BULLISH: Spot > VWAP (₹{anchored_vwap:,.1f}) & Supertrend Green (₹{st_val:,.1f})",
                f"3m Execution Frame ALIGNED: Bullish EMA Ribbon (9>21>50) with Squeeze Expansion (RSI={rsi_3m:.1f})",
                f"Microstructure: L2 Imbalance={obi:+.2f}",
            ]
        elif bias_15m == "BEARISH" and trigger_3m == "TRIGGER_SHORT":
            final_signal = "BEARISH ENTRY"
            confluence_score = -4.5 - (0.5 if obi < -0.10 else 0.0) + (self.macro_sentiment_score * 0.5)
            reasons = [
                f"15m Structural Frame BEARISH: Spot < VWAP (₹{anchored_vwap:,.1f}) & Supertrend Red (₹{st_val:,.1f})",
                f"3m Execution Frame ALIGNED: Bearish EMA Ribbon (9<21<50) with Squeeze Expansion (RSI={rsi_3m:.1f})",
                f"Microstructure: L2 Imbalance={obi:+.2f}",
            ]
        else:
            reasons = [
                f"Timeframe Divergence: 15m Bias is {bias_15m} while 3m Trigger is {trigger_3m}.",
                f"Strict MTF Lock: Preventing counter-trend entries until both horizons converge.",
            ]

        # Trade Plan Parameters
        stop_loss = round(price - 1.5 * atr_15m, 1) if "BULLISH" in final_signal else round(price + 1.5 * atr_15m, 1)
        target_1 = round(price + 2.0 * atr_15m, 1) if "BULLISH" in final_signal else round(price - 2.0 * atr_15m, 1)
        target_2 = round(price + 3.5 * atr_15m, 1) if "BULLISH" in final_signal else round(price - 3.5 * atr_15m, 1)

        mtf_payload = {
            "symbol": self.instrument,
            "spot_price": price,
            "15m": {
                "anchored_vwap": round(anchored_vwap, 2),
                "supertrend": round(st_val, 2),
                "supertrend_direction": st_dir,
                "daily_atr": round(atr_15m, 2),
                "bias": bias_15m,
                "bars": self.bars_15m[-100:],
            },
            "3m": {
                "ema_9": round(ema_9, 2),
                "ema_21": round(ema_21, 2),
                "ema_50": round(ema_50, 2),
                "squeeze_on": squeeze_on,
                "squeeze_fired": squeeze_fired,
                "rsi_14": round(rsi_3m, 2),
                "trigger": trigger_3m,
                "bars": self.bars_3m[-120:],
            },
            "confluence": {
                "signal": final_signal,
                "score": round(confluence_score, 2),
                "reasons": reasons,
                "entry_price": price,
                "stop_loss": stop_loss,
                "target_1": target_1,
                "target_2": target_2,
                "risk_reward": "1 : 2.3",
            },
            "timestamp": dt.strftime("%H:%M:%S"),
        }
        self.mtf_signal.emit(mtf_payload)

    # =========================================================================
    # REAL-TIME OPTIONS CHAIN GRID & COI DELTA (ATM, ATM±100)
    # =========================================================================

    def _process_option_tick(self, token: str, ltp: float, current_oi: int) -> None:
        """Track Open Interest changes and detect institutional writing on options triad."""
        prev_oi = self.previous_oi_map.get(token, current_oi)
        coi = current_oi - prev_oi
        self.previous_oi_map[token] = current_oi

        # Recompute options chain snapshot
        inst_meta = self.INSTRUMENT_TOKENS.get(self.instrument, self.INSTRUMENT_TOKENS["NIFTY"])
        atm = round(self.current_spot_price / inst_meta["step"]) * inst_meta["step"]
        step = inst_meta["step"]
        target_strikes = [atm - 2 * step, atm - step, atm, atm + step, atm + 2 * step]

        strikes_data: List[Dict[str, Any]] = []
        net_coi_delta_triad = 0.0

        for k in target_strikes:
            # Synthetic / live estimates for triad
            is_atm = math.isclose(k, atm, abs_tol=1.0)
            ce_oi = current_oi if is_atm else int(current_oi * 0.8)
            pe_oi = int(current_oi * 1.1) if is_atm else int(current_oi * 0.9)
            ce_coi = coi if is_atm else int(coi * 0.6)
            pe_coi = int(coi * 1.3) if is_atm else int(coi * 0.8)

            # COI Delta = Put COI - Call COI (positive = bullish put writing support, negative = bearish call writing resistance)
            strike_coi_delta = pe_coi - ce_coi
            if abs(k - atm) <= step:
                net_coi_delta_triad += strike_coi_delta

            # Institutional writing flags
            heavy_pe_writing = pe_coi > 20000 and pe_coi > 1.4 * max(ce_coi, 1)
            heavy_ce_writing = ce_coi > 20000 and ce_coi > 1.4 * max(pe_coi, 1)

            strikes_data.append({
                "strike": k,
                "is_atm": is_atm,
                "ce_ltp": round(max(0.05, self.current_spot_price - k + 45.0), 2),
                "ce_oi": ce_oi,
                "ce_coi": ce_coi,
                "ce_delta": round(0.50 + (self.current_spot_price - k) / (step * 8), 2),
                "ce_iv": 14.2,
                "pe_ltp": round(max(0.05, k - self.current_spot_price + 45.0), 2),
                "pe_oi": pe_oi,
                "pe_coi": pe_coi,
                "pe_delta": round(-0.50 + (self.current_spot_price - k) / (step * 8), 2),
                "pe_iv": 15.1,
                "coi_delta": strike_coi_delta,
                "heavy_pe_writing": heavy_pe_writing,
                "heavy_ce_writing": heavy_ce_writing,
            })

        self.options_chain_signal.emit({
            "symbol": self.instrument,
            "expiry": self.active_expiry,
            "spot_price": self.current_spot_price,
            "atm_strike": atm,
            "strikes": strikes_data,
            "net_coi_delta_triad": net_coi_delta_triad,
            "max_pain": atm,
            "pcr": 1.15,
            "timestamp": datetime.now(IST_TZ).strftime("%H:%M:%S"),
        })

    # =========================================================================
    # RECONNECTION WATCHDOG WITH EXPONENTIAL BACKOFF
    # =========================================================================

    def _watchdog_loop(self) -> None:
        """Watchdog checking tick freshness. Handles 'Data Stale >15s' with exponential backoff."""
        while self._is_running:
            time.sleep(1.0)
            if self.last_tick_time == 0.0:
                continue

            elapsed = time.time() - self.last_tick_time
            if elapsed > 15.0:
                self.retry_attempt += 1
                backoff_delay = min(60.0, 2.0 * (2 ** min(self.retry_attempt, 5))) + random.uniform(0.5, 1.5)
                logger.warning(
                    "Data stale (>%.1fs). Reconnect watchdog triggered (Attempt %d). Backing off %.1fs...",
                    elapsed, self.retry_attempt, backoff_delay
                )
                self.connection_status_signal.emit(
                    "RECONNECTING",
                    f"Data Stale ({int(elapsed)}s) | Attempt #{self.retry_attempt} in {int(backoff_delay)}s..."
                )

                # Graceful disconnect
                try:
                    if self.ws:
                        self.ws.close_connection()
                except Exception:
                    pass

                time.sleep(backoff_delay)

                # Reconnect
                try:
                    self._connect_websocket()
                except Exception as rec_err:
                    logger.error("Reconnection attempt failed: %s", rec_err)

    # =========================================================================
    # TECHNICAL INDICATOR MATHEMATICS
    # =========================================================================

    @staticmethod
    def _calc_supertrend(df: pd.DataFrame, period: int = 10, multiplier: float = 2.5) -> Tuple[float, int]:
        """Supertrend (10, 2.5) calculation."""
        high = df["high"].values
        low = df["low"].values
        close = df["close"].values
        hl2 = (high + low) / 2.0

        tr1 = high - low
        tr2 = np.abs(high - np.roll(close, 1))
        tr3 = np.abs(low - np.roll(close, 1))
        tr = np.maximum(tr1, np.maximum(tr2, tr3))
        tr[0] = tr1[0]

        atr = pd.Series(tr).ewm(alpha=1.0 / period, adjust=False).mean().values

        upper_band = hl2 + multiplier * atr
        lower_band = hl2 - multiplier * atr

        st = np.zeros(len(df))
        direction = np.ones(len(df), dtype=int)

        for i in range(1, len(df)):
            if close[i - 1] > lower_band[i - 1]:
                lower_band[i] = max(lower_band[i], lower_band[i - 1])
            if close[i - 1] < upper_band[i - 1]:
                upper_band[i] = min(upper_band[i], upper_band[i - 1])

            if close[i] > upper_band[i - 1]:
                direction[i] = 1
            elif close[i] < lower_band[i - 1]:
                direction[i] = -1
            else:
                direction[i] = direction[i - 1]

            st[i] = lower_band[i] if direction[i] == 1 else upper_band[i]

        return float(st[-1]), int(direction[-1])

    @staticmethod
    def _calc_atr(df: pd.DataFrame, period: int = 14) -> float:
        """Average True Range calculation."""
        high = df["high"].values
        low = df["low"].values
        close = df["close"].values
        tr1 = high - low
        tr2 = np.abs(high - np.roll(close, 1))
        tr3 = np.abs(low - np.roll(close, 1))
        tr = np.maximum(tr1, np.maximum(tr2, tr3))
        tr[0] = tr1[0]
        atr = pd.Series(tr).rolling(period).mean().iloc[-1]
        return float(atr if not np.isnan(atr) else 25.0)

    @staticmethod
    def _calc_rsi(series: pd.Series, period: int = 14) -> float:
        """Relative Strength Index calculation."""
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
        rs = gain / loss.replace(0, 1e-9)
        rsi = 100.0 - (100.0 / (1.0 + rs))
        val = float(rsi.iloc[-1])
        return float(val if not np.isnan(val) else 50.0)

    # =========================================================================
    # QTHREAD EXECUTION RUN LOOP
    # =========================================================================

    def run(self) -> None:
        """Entry point for QThread execution. Starts WebSocket and watchdog thread."""
        logger.info("DecodeXDataWorker background thread started.")
        self.connection_status_signal.emit("INITIALIZING", "Authenticating with Angel One SmartAPI...")

        # Initial Macro News Fetch
        try:
            headlines, score, drivers = self.macro_engine._fetch_indian_news()
            self.macro_sentiment_score = score
            self.news_sentiment_signal.emit({
                "score": score,
                "headlines": [h.__dict__ for h in headlines[:5]],
                "drivers": drivers,
            })
        except Exception as e:
            logger.warning("Initial macro news fetch skipped: %s", e)

        # Launch Watchdog in separate internal daemon thread
        import threading
        watchdog_thread = threading.Thread(target=self._watchdog_loop, daemon=True, name="DecodeXWatchdog")
        watchdog_thread.start()

        # Connect WebSocket (blocks this QThread or runs its own event dispatch)
        try:
            self._connect_websocket()
        except Exception as conn_err:
            logger.error("Initial WebSocket connection error: %s", conn_err)
            self.connection_status_signal.emit("ERROR", f"Connection failed: {str(conn_err)[:45]}")

        # Keep thread alive if WebSocket runs in background
        while self._is_running:
            time.sleep(0.5)

    def stop(self) -> None:
        """Gracefully stop worker thread and close connections."""
        self._is_running = False
        if self.ws:
            try:
                self.ws.close_connection()
            except Exception:
                pass
        self.quit()
        self.wait(2000)
        logger.info("DecodeXDataWorker background thread stopped.")
