"""Position sizing, risk management, and kill switch with restart protocol."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
import logging
from typing import Any, Dict, List, Optional
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class PositionSizeResult:
    units: float                      # Tradable continuous units
    risk_amount_inr: float            # Capital at risk in INR
    stop_distance_points: float       # Absolute stop distance from entry
    vol_scalar: float                 # Volatility target adjustment multiplier
    notional_exposure: float          # units * entry_price
    leverage: float                   # notional_exposure / current_capital


class RiskManager:
    """Manages risk-based position sizing, maximum daily loss, and drawdown kill switch."""

    def __init__(
        self,
        starting_capital: float = 1000000.0,
        risk_per_trade_pct: float = 1.0,
        vol_target_annual_pct: float = 15.0,
        max_daily_loss_pct: float = 2.5,
        max_drawdown_limit_pct: float = 15.0,
        kill_switch_pause_days: int = 20,
        max_leverage_cap: float = 2.5,
    ) -> None:
        self.starting_capital = starting_capital
        self.risk_per_trade_pct = risk_per_trade_pct
        self.vol_target_annual = vol_target_annual_pct / 100.0
        self.max_daily_loss_pct = max_daily_loss_pct
        self.max_drawdown_limit_pct = max_drawdown_limit_pct
        self.kill_switch_pause_days = kill_switch_pause_days
        self.max_leverage_cap = max_leverage_cap

        # State tracking
        self.current_capital = starting_capital
        self.peak_capital = starting_capital
        self.true_peak_capital = starting_capital
        self.true_max_drawdown_pct = 0.0
        self.current_drawdown_pct = 0.0
        self.is_paused = False
        self.pause_days_left = 0
        self.kill_switch_trigger_count = 0
        self.total_days_paused = 0
        self.kill_switch_history: List[Dict[str, Any]] = []

    def calculate_position_size(
        self,
        entry_price: float,
        stop_loss_price: float,
        realized_vol_annual: Optional[float] = None,
    ) -> PositionSizeResult:
        """Calculate position units using fixed fractional risk and volatility targeting.

        Formula:
            stop_distance = |entry - stop_loss|
            risk_budget = current_capital * (risk_pct / 100)
            base_units = risk_budget / stop_distance
            vol_scalar = target_vol / realized_vol
            units = base_units * clip(vol_scalar, 0.5, 1.5)
        """
        if self.is_paused or self.current_capital <= 0:
            return PositionSizeResult(0.0, 0.0, 0.0, 1.0, 0.0, 0.0)

        stop_distance = abs(entry_price - stop_loss_price)
        if stop_distance <= 0:
            stop_distance = entry_price * 0.01  # Fallback 1% distance

        risk_budget = self.current_capital * (self.risk_per_trade_pct / 100.0)
        base_units = risk_budget / stop_distance

        # Volatility target scaling
        vol_scalar = 1.0
        if realized_vol_annual is not None and not np.isnan(realized_vol_annual) and realized_vol_annual > 0:
            vol_scalar = self.vol_target_annual / realized_vol_annual
            vol_scalar = float(np.clip(vol_scalar, 0.5, 1.5))

        units = base_units * vol_scalar

        # Leverage cap guard
        notional = units * entry_price
        max_allowed_notional = self.current_capital * self.max_leverage_cap
        if notional > max_allowed_notional:
            units = max_allowed_notional / entry_price
            notional = max_allowed_notional

        leverage = notional / self.current_capital if self.current_capital > 0 else 0.0

        return PositionSizeResult(
            units=units,
            risk_amount_inr=risk_budget,
            stop_distance_points=stop_distance,
            vol_scalar=vol_scalar,
            notional_exposure=notional,
            leverage=leverage,
        )

    def check_kill_switch(self, current_equity: float, current_date: date) -> bool:
        """Update drawdown and trigger kill switch if threshold exceeded.

        Returns:
            True if kill switch was just triggered or is active.
        """
        self.current_capital = current_equity
        if current_equity > self.peak_capital:
            self.peak_capital = current_equity
        if current_equity > self.true_peak_capital:
            self.true_peak_capital = current_equity

        # Track true peak drawdown across entire lifetime
        true_dd = ((self.true_peak_capital - current_equity) / self.true_peak_capital * 100.0) if self.true_peak_capital > 0 else 0.0
        if true_dd > self.true_max_drawdown_pct:
            self.true_max_drawdown_pct = true_dd

        # Active cycle drawdown relative to latest restart watermark
        dd_pct = ((self.peak_capital - current_equity) / self.peak_capital * 100.0) if self.peak_capital > 0 else 0.0
        self.current_drawdown_pct = dd_pct

        if not self.is_paused and dd_pct >= self.max_drawdown_limit_pct:
            # Trigger kill switch
            self.is_paused = True
            self.pause_days_left = self.kill_switch_pause_days
            self.kill_switch_trigger_count += 1
            event = {
                "trigger_index": self.kill_switch_trigger_count,
                "date": str(current_date),
                "drawdown_pct": dd_pct,
                "true_drawdown_pct": true_dd,
                "equity_at_trigger": current_equity,
                "peak_equity": self.peak_capital,
                "true_peak_equity": self.true_peak_capital,
                "pause_days": self.kill_switch_pause_days,
            }
            self.kill_switch_history.append(event)
            logger.warning(
                "KILL SWITCH TRIGGERED on %s: Drawdown %.2f%% (True DD %.2f%%) exceeded limit %.2f%%. Pausing for %d days.",
                current_date,
                dd_pct,
                true_dd,
                self.max_drawdown_limit_pct,
                self.kill_switch_pause_days,
            )
            return True

        return self.is_paused

    def advance_day(self) -> None:
        """Call at end of each trading day to manage restart countdown."""
        if self.is_paused:
            self.total_days_paused += 1
            self.pause_days_left -= 1
            if self.pause_days_left <= 0:
                self.is_paused = False
                # Reset peak watermark to current capital to enable recovery
                self.peak_capital = self.current_capital
                logger.info(
                    "KILL SWITCH RESTART: Resume trading after pause. Watermark reset to %.2f INR",
                    self.current_capital,
                )
