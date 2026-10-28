"""Thread-safe Token Bucket Rate Limiter and backoff handler for Angel One SmartAPI.

Routes all REST endpoints through documented limits, with safety margins (70% target).
Catches rate-limit errors and performs exponential backoff (2s -> 4s -> 8s -> ... -> 60s max).
"""

from __future__ import annotations

import logging
import threading
import time
from collections import deque
from typing import Any, Callable, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class EndpointTokenBucket:
    """Sliding-window token bucket enforcing per-second, per-minute, and per-hour limits."""

    def __init__(self, per_sec: int, per_min: Optional[int] = None, per_hour: Optional[int] = None):
        self.per_sec = per_sec
        self.per_min = per_min
        self.per_hour = per_hour
        self.sec_window: deque[float] = deque()
        self.min_window: deque[float] = deque()
        self.hour_window: deque[float] = deque()
        self.lock = threading.Lock()

    def acquire(self) -> None:
        while True:
            with self.lock:
                now = time.time()
                while self.sec_window and now - self.sec_window[0] >= 1.0:
                    self.sec_window.popleft()
                while self.min_window and now - self.min_window[0] >= 60.0:
                    self.min_window.popleft()
                while self.hour_window and now - self.hour_window[0] >= 3600.0:
                    self.hour_window.popleft()

                wait_sec = 0.0
                if len(self.sec_window) >= self.per_sec:
                    wait_sec = max(wait_sec, 1.0 - (now - self.sec_window[0]))
                if self.per_min and len(self.min_window) >= self.per_min:
                    wait_sec = max(wait_sec, 60.0 - (now - self.min_window[0]))
                if self.per_hour and len(self.hour_window) >= self.per_hour:
                    wait_sec = max(wait_sec, 3600.0 - (now - self.hour_window[0]))

                if wait_sec <= 0:
                    now = time.time()
                    self.sec_window.append(now)
                    if self.per_min:
                        self.min_window.append(now)
                    if self.per_hour:
                        self.hour_window.append(now)
                    return
            time.sleep(wait_sec + 0.05)


class SharedRateLimiter:
    """Shared rate limiter across all SmartAPI REST endpoints with 70% safety margins."""

    def __init__(self):
        # 70% safety margin:
        # getCandleData: 3/sec -> 2/sec, 120/min -> 84/min, 5000/hr -> 3500/hr
        # quote: 10/sec -> 7/sec, 500/min -> 350/min
        # optionGreek: 1/sec -> 1/sec (safety interval handled by bucket), 42/min
        self.buckets: Dict[str, EndpointTokenBucket] = {
            "getCandleData": EndpointTokenBucket(per_sec=2, per_min=80, per_hour=3500),
            "quote": EndpointTokenBucket(per_sec=7, per_min=350, per_hour=3500),
            "getLtpData": EndpointTokenBucket(per_sec=7, per_min=350, per_hour=3500),
            "optionGreek": EndpointTokenBucket(per_sec=1, per_min=42, per_hour=700),
            "generateTokens": EndpointTokenBucket(per_sec=1, per_min=40, per_hour=700),
            "loginByPassword": EndpointTokenBucket(per_sec=1, per_min=40, per_hour=700),
            "searchScrip": EndpointTokenBucket(per_sec=1, per_min=40, per_hour=700),
            "estimateCharges": EndpointTokenBucket(per_sec=1, per_min=40, per_hour=700),
            "getOIData": EndpointTokenBucket(per_sec=2, per_min=80, per_hour=3500),
            "getProfile": EndpointTokenBucket(per_sec=1, per_min=40, per_hour=700),
        }
        self.call_stats: Dict[str, int] = {}
        self.rate_limits_hit: Dict[str, int] = {}
        self.lock = threading.Lock()

    def acquire(self, endpoint: str) -> None:
        bucket = self.buckets.get(endpoint)
        if bucket:
            bucket.acquire()
        with self.lock:
            self.call_stats[endpoint] = self.call_stats.get(endpoint, 0) + 1

    def record_rate_limit_hit(self, endpoint: str) -> None:
        with self.lock:
            self.rate_limits_hit[endpoint] = self.rate_limits_hit.get(endpoint, 0) + 1

    def execute_with_backoff(
        self,
        endpoint: str,
        func: Callable[..., Any],
        *args: Any,
        max_attempts: int = 6,
        **kwargs: Any,
    ) -> Any:
        """Execute SmartAPI call with rate limiter acquire and exponential backoff retry."""
        backoff_sec = 2.0
        max_backoff = 60.0

        for attempt in range(1, max_attempts + 1):
            self.acquire(endpoint)
            try:
                res = func(*args, **kwargs)
                return res
            except Exception as e:
                err_msg = str(e)
                # Rate limit signature
                is_rate_limit = (
                    "Access denied because of exceeding access rate" in err_msg
                    or "exceeding rate limit" in err_msg
                    or "exceeding access rate" in err_msg
                    or "Too many requests" in err_msg
                    or "429" in err_msg
                )

                if is_rate_limit:
                    self.record_rate_limit_hit(endpoint)
                    if attempt == max_attempts:
                        logger.error("Rate limit retry exhausted after %d attempts for [%s]", attempt, endpoint)
                        raise
                    logger.warning(
                        "Rate limit on [%s] (attempt %d/%d). Backing off %.1fs (max 60s)...",
                        endpoint,
                        attempt,
                        max_attempts,
                        backoff_sec,
                    )
                    time.sleep(backoff_sec)
                    backoff_sec = min(backoff_sec * 2.0, max_backoff)
                else:
                    # Non-rate-limit exception
                    logger.error("SmartAPI call failed on [%s]: %s", endpoint, e)
                    raise


# Global shared rate limiter singleton
shared_rate_limiter = SharedRateLimiter()
