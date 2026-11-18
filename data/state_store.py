"""DecodeX Trading — Ultra-Low-Latency Local State Store.

Supports:
1. Local Redis in-memory key-value store (if redis-server is running on localhost:6379).
2. Atomic filesystem store (JSON + POSIX atomic os.replace) as an ultra-fast (<0.3ms),
   zero-config, non-blocking fallback that requires zero external daemons.

Used by:
- engine.py (Writer): Broadcasts live ticks, L2 depth, MTF indicators, and news updates.
- app.py (Reader): Fast sub-millisecond polling inside Streamlit @st.fragment(run_every="1s").
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger("DecodeXStateStore")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_STATE_FILE = PROJECT_ROOT / "data" / "decodex_state.json"
DEFAULT_TMP_FILE = PROJECT_ROOT / "data" / "decodex_state.json.tmp"
DEFAULT_CONTROLS_FILE = PROJECT_ROOT / "data" / "decodex_controls.json"
REDIS_KEY = "decodex:live_state"
REDIS_CONTROLS_KEY = "decodex:controls"


class StateStore:
    """Ultra-low-latency state storage with automatic Redis detection and atomic file fallback."""

    def __init__(
        self,
        redis_host: str = "localhost",
        redis_port: int = 6379,
        redis_db: int = 0,
        file_path: Optional[Path] = None,
        controls_path: Optional[Path] = None,
    ):
        self.file_path = file_path or DEFAULT_STATE_FILE
        self.tmp_path = self.file_path.with_suffix(".json.tmp")
        self.controls_file = controls_path or DEFAULT_CONTROLS_FILE
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

        self._redis_client = None
        self._redis_available = False
        self._last_state_cache: Optional[Dict[str, Any]] = None
        self._last_controls_cache: Optional[Dict[str, Any]] = None
        self._last_write_time: float = 0.0

        # Attempt Redis connection
        try:
            import redis
            client = redis.Redis(
                host=redis_host,
                port=redis_port,
                db=redis_db,
                socket_connect_timeout=0.3,
                socket_timeout=0.3,
                decode_responses=True,
            )
            client.ping()
            self._redis_client = client
            self._redis_available = True
            logger.info("DecodeX StateStore: Connected to Redis on %s:%d.", redis_host, redis_port)
        except Exception as e:
            self._redis_available = False
            logger.info(
                "DecodeX StateStore: Redis unavailable (%s). Using high-speed atomic file store: %s",
                e,
                self.file_path,
            )

    @property
    def is_redis_active(self) -> bool:
        """Return True if Redis is active and reachable."""
        return self._redis_available

    def set_state(self, state: Dict[str, Any]) -> bool:
        """Write state payload atomically without blocking."""
        state["updated_at"] = time.time()
        self._last_state_cache = state
        self._last_write_time = state["updated_at"]

        # 1. Attempt Redis Write
        if self._redis_available and self._redis_client:
            try:
                payload_str = json.dumps(state, default=str)
                self._redis_client.set(REDIS_KEY, payload_str)
                # Keep file updated as well for offline persistence
            except Exception as e:
                logger.warning("Redis write failed, falling back to atomic file: %s", e)
                self._redis_available = False

        # 2. Ultra-fast Atomic File Write (<0.3ms)
        try:
            payload_str = json.dumps(state, default=str)
            with open(self.tmp_path, "w", encoding="utf-8") as f:
                f.write(payload_str)
            os.replace(self.tmp_path, self.file_path)
            return True
        except Exception as e:
            logger.error("StateStore atomic file write error: %s", e)
            return False

    def get_state(self) -> Optional[Dict[str, Any]]:
        """Read latest state in microseconds."""
        # 1. Try Redis first
        if self._redis_available and self._redis_client:
            try:
                raw = self._redis_client.get(REDIS_KEY)
                if raw:
                    data = json.loads(raw)
                    self._last_state_cache = data
                    return data
            except Exception as e:
                logger.debug("Redis read failed: %s", e)
                self._redis_available = False

        # 2. Read Atomic File
        if self.file_path.exists():
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._last_state_cache = data
                return data
            except Exception:
                # In rare case of microsecond race, return cached copy
                if self._last_state_cache is not None:
                    return self._last_state_cache

        return self._last_state_cache

    def set_controls(self, controls: Dict[str, Any]) -> bool:
        """Save UI controls parameters for engine consumption."""
        self._last_controls_cache = controls
        # Try redis
        if self._redis_available and self._redis_client:
            try:
                self._redis_client.set(REDIS_CONTROLS_KEY, json.dumps(controls))
            except Exception:
                pass
        # Atomic file write
        try:
            tmp_ctrl = self.controls_file.with_suffix(".json.tmp")
            with open(tmp_ctrl, "w", encoding="utf-8") as f:
                json.dump(controls, f)
            os.replace(tmp_ctrl, self.controls_file)
            return True
        except Exception as e:
            logger.debug("Failed to write controls file: %s", e)
            return False

    def get_controls(self) -> Dict[str, Any]:
        """Read UI controls parameters."""
        default_ctrl = {
            "op_mode": "Active Quant Execution (Live Signals)",
            "instrument": "NIFTY",
            "expiry": "17NOV2026",
            "account_equity": 1_000_000.0,
            "risk_pct": 1.0,
            "atr_mult": 1.5,
            "enable_chime": True,
            "hard_sl": True,
        }
        if self._redis_available and self._redis_client:
            try:
                raw = self._redis_client.get(REDIS_CONTROLS_KEY)
                if raw:
                    return {**default_ctrl, **json.loads(raw)}
            except Exception:
                pass
        if self.controls_file.exists():
            try:
                with open(self.controls_file, "r", encoding="utf-8") as f:
                    return {**default_ctrl, **json.load(f)}
            except Exception:
                pass
        return self._last_controls_cache or default_ctrl

    def get_age_seconds(self) -> float:
        """Return age in seconds of the current state."""
        state = self.get_state()
        if not state:
            return 999.0
        updated = state.get("updated_at", 0.0)
        return max(0.0, time.time() - updated)


# Global singleton store instance
state_store = StateStore()

