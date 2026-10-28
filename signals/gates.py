"""Configurable trade gatekeeper and filter auditing engine.

Enforces NO_TRADE as a first-class outcome based on:
1. Data gaps (flagged DATA_MISSING_IN_FEED)
2. Calibrated confidence threshold
3. Market regime (UNKNOWN and HIGH_VOL)
4. India VIX percentile extreme bounds
5. Expiry day proximity (with A/B comparison)
"""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

from models.base import SignalDirection

logger = logging.getLogger(__name__)


@dataclass
class GateAuditReport:
    """Statistics recording how many potential trades each gate filter removed."""
    total_candles: int = 0
    raw_buy_signals: int = 0
    raw_sell_signals: int = 0
    total_raw_signals: int = 0
    dropped_by_gap: int = 0
    dropped_by_confidence: int = 0
    dropped_by_regime: int = 0
    dropped_by_vix: int = 0
    dropped_by_expiry: int = 0
    final_executed_buys: int = 0
    final_executed_sells: int = 0
    final_executed_signals: int = 0
    removal_rate_pct: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_candles": self.total_candles,
            "total_raw_signals": self.total_raw_signals,
            "raw_buy_signals": self.raw_buy_signals,
            "raw_sell_signals": self.raw_sell_signals,
            "dropped_by_gap": self.dropped_by_gap,
            "dropped_by_confidence": self.dropped_by_confidence,
            "dropped_by_regime": self.dropped_by_regime,
            "dropped_by_vix": self.dropped_by_vix,
            "dropped_by_expiry": self.dropped_by_expiry,
            "final_executed_signals": self.final_executed_signals,
            "removal_rate_pct": self.removal_rate_pct,
        }


class TradeGatekeeper:
    """Applies hierarchical trade gates and logs filter statistics."""

    def __init__(
        self,
        min_confidence: float = 0.55,
        enable_regime_filter: bool = True,
        max_vix_percentile: float = 85.0,
        min_vix_percentile: float = 5.0,
        enable_expiry_filter: bool = True,
        gap_lookback_bars: int = 3,
    ) -> None:
        self.min_confidence = min_confidence
        self.enable_regime_filter = enable_regime_filter
        self.max_vix_percentile = max_vix_percentile
        self.min_vix_percentile = min_vix_percentile
        self.enable_expiry_filter = enable_expiry_filter
        self.gap_lookback_bars = gap_lookback_bars

    def apply_gates(
        self,
        market_df: pd.DataFrame,
        signals_df: pd.DataFrame,
    ) -> Tuple[pd.DataFrame, GateAuditReport]:
        """Apply filters sequentially to raw signal packets.

        Returns:
            (filtered_signals_df, GateAuditReport)
        """
        n = len(market_df)
        if len(signals_df) != n:
            raise ValueError(f"Length mismatch: market_df ({n}) vs signals_df ({len(signals_df)})")

        out = signals_df.copy()
        report = GateAuditReport(total_candles=n)

        # Pre-extract arrays for speed
        directions = out["direction"].values.copy()
        confidences = out["confidence"].values
        reasons = out["reasons"].values.copy()

        is_gap = market_df["is_gap"].values if "is_gap" in market_df.columns else np.zeros(n, dtype=bool)
        regimes = market_df["regime_label"].values if "regime_label" in market_df.columns else np.full(n, "UNKNOWN")
        vix_pctile = market_df["vix_pctile_252"].values if "vix_pctile_252" in market_df.columns else np.full(n, 50.0)
        is_expiry = market_df["is_expiry_day"].values if "is_expiry_day" in market_df.columns else np.zeros(n, dtype=bool)
        days_to_exp = market_df["days_to_expiry"].values if "days_to_expiry" in market_df.columns else np.full(n, 5)

        for i in range(n):
            d = directions[i]
            if d == SignalDirection.NO_TRADE.value:
                continue

            report.total_raw_signals += 1
            if d == SignalDirection.BUY.value:
                report.raw_buy_signals += 1
            else:
                report.raw_sell_signals += 1

            # 1. Data Gap Gate: Exclude bars spanning or immediately following flagged gap
            gap_span = False
            for lookback in range(max(0, i - self.gap_lookback_bars), i + 1):
                if is_gap[lookback]:
                    gap_span = True
                    break

            if gap_span:
                directions[i] = SignalDirection.NO_TRADE.value
                reasons[i] = f"[GATE_GAP_DROPPED] {reasons[i]}"
                report.dropped_by_gap += 1
                continue

            # 2. Confidence Threshold Gate
            if confidences[i] < self.min_confidence:
                directions[i] = SignalDirection.NO_TRADE.value
                reasons[i] = f"[GATE_LOW_CONFIDENCE({confidences[i]:.2f}<{self.min_confidence:.2f})] {reasons[i]}"
                report.dropped_by_confidence += 1
                continue

            # 3. Regime Filter Gate (UNKNOWN or HIGH_VOL)
            if self.enable_regime_filter:
                reg = str(regimes[i]).upper()
                if reg in ["UNKNOWN", "HIGH_VOL"]:
                    directions[i] = SignalDirection.NO_TRADE.value
                    reasons[i] = f"[GATE_REGIME_BLOCKED({reg})] {reasons[i]}"
                    report.dropped_by_regime += 1
                    continue

            # 4. India VIX Percentile Extreme Gate
            vix_val = vix_pctile[i]
            if not np.isnan(vix_val):
                if vix_val > self.max_vix_percentile or vix_val < self.min_vix_percentile:
                    directions[i] = SignalDirection.NO_TRADE.value
                    reasons[i] = f"[GATE_VIX_PERCENTILE({vix_val:.1f}%)] {reasons[i]}"
                    report.dropped_by_vix += 1
                    continue

            # 5. Expiry Day Proximity Gate
            if self.enable_expiry_filter:
                if is_expiry[i] or days_to_exp[i] <= 1:
                    directions[i] = SignalDirection.NO_TRADE.value
                    reasons[i] = f"[GATE_EXPIRY_PROXIMITY(days={days_to_exp[i]})] {reasons[i]}"
                    report.dropped_by_expiry += 1
                    continue

            # Passed all gates
            if directions[i] == SignalDirection.BUY.value:
                report.final_executed_buys += 1
            elif directions[i] == SignalDirection.SELL.value:
                report.final_executed_sells += 1

        report.final_executed_signals = report.final_executed_buys + report.final_executed_sells
        total_dropped = report.total_raw_signals - report.final_executed_signals
        report.removal_rate_pct = (total_dropped / report.total_raw_signals * 100.0) if report.total_raw_signals > 0 else 0.0

        out["direction"] = directions
        out["reasons"] = reasons

        return out, report
