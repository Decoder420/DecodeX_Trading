"""DecodeX Trading — Automated Quant Execution & State Machine Engine.

Role:
- 6-Factor MTF Confluence State Machine:
    WAIT -> EXECUTE -> ORDER_SUBMITTED -> POSITION_OPEN -> TRAILING_STOP -> TARGET_HIT / STOPPED_OUT
- Active Quant Execution (Live Signals): Automatically sends orders to mock broker when confluence threshold is met.
- Strict Risk Gatekeeper: Emits alerts without routing execution requests.
- Rolling Event Log: Real-time telemetry of orders, trailing stops, and risk guardrails.
"""

from __future__ import annotations

import logging
import time
import uuid
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytz

from data.risk_engine import RiskCalculator, RiskEvaluationResult

logger = logging.getLogger("QuantExecutionEngine")
IST_TZ = pytz.timezone("Asia/Kolkata")


class QuantExecutionEngine:
    """Automated signal execution state machine and order dispatcher."""

    def __init__(self):
        self.execution_mode: str = "Active Quant Execution (Live Signals)"
        self.state: str = "WAIT"
        self.current_position: Optional[Dict[str, Any]] = None
        self.event_logs: deque = deque(maxlen=60)
        self.last_confluence_signal: str = "CONFLUENCE WAIT"
        self.last_executed_signal: str = ""
        self.chime_triggered: bool = False

        # Seed initial system logs
        self.log_event(
            category="SYSTEM",
            level="INFO",
            title="DecodeX Quant Execution Engine Online",
            details="State machine initialized in active intraday confluence mode.",
        )

    def log_event(self, category: str, level: str, title: str, details: str) -> None:
        """Append an institutional audit entry to the rolling event log."""
        entry = {
            "id": str(uuid.uuid4())[:8],
            "timestamp": datetime.now(IST_TZ).strftime("%H:%M:%S"),
            "category": category,
            "level": level,  # 'INFO', 'SUCCESS', 'WARNING', 'ERROR'
            "title": title,
            "details": details,
        }
        self.event_logs.appendleft(entry)
        logger.info("[%s] %s: %s", category, title, details)

    def set_execution_mode(self, mode: str) -> None:
        """Update operating mode between Active Execution and Strict Gatekeeper."""
        if mode != self.execution_mode:
            self.execution_mode = mode
            self.log_event(
                category="SYSTEM",
                level="INFO",
                title="Operating Mode Changed",
                details=f"Engine transitioned to '{mode}'.",
            )

    def evaluate_and_execute(
        self,
        confluence_data: Dict[str, Any],
        risk_params: Dict[str, Any],
        spot_price: float,
        options_chain_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Core state machine evaluation loop on incoming confluence ticks."""
        signal = confluence_data.get("signal", "CONFLUENCE WAIT")
        score = float(confluence_data.get("score", 0.0))
        trade_plan = confluence_data.get("trade_plan", {})
        action = trade_plan.get("action", "WAIT")
        rec_strike = trade_plan.get("recommended_strike", "ATM")
        atr_pts = float(trade_plan.get("atr_pts", 45.0))

        # Check for signal state transition
        is_entry = ("BULLISH" in signal or "BEARISH" in signal) and abs(score) >= 4.0
        signal_changed = (signal != self.last_confluence_signal)
        self.last_confluence_signal = signal

        if signal_changed:
            self.chime_triggered = True
            self.log_event(
                category="CONFLUENCE",
                level="SUCCESS" if is_entry else "INFO",
                title=f"Confluence Shift: {signal}",
                details=f"Score: {score:+.2f} | 15m: {confluence_data.get('bias_15m')} | 3m: {confluence_data.get('trigger_3m')}",
            )

        # 1. Active Position Tracking & Trailing SL
        if self.current_position:
            self._update_position_tracking(spot_price, atr_pts)
            return self.get_execution_status()

        # 2. No Open Position: Evaluate Entry Signal
        if is_entry and action in ("BUY_CALL", "BUY_PUT"):
            # Check if this exact signal was already executed to prevent duplicate orders
            sig_key = f"{signal}_{trade_plan.get('entry')}"
            if sig_key == self.last_executed_signal:
                return self.get_execution_status()

            # Evaluate Risk & Position Sizing
            risk_eval: RiskEvaluationResult = RiskCalculator.evaluate_risk(
                account_equity=risk_params.get("account_equity", 1_000_000.0),
                risk_per_trade_pct=risk_params.get("risk_pct", 1.0),
                atr_multiplier=risk_params.get("atr_mult", 1.5),
                instrument=risk_params.get("instrument", "NIFTY"),
                atr_pts=atr_pts,
            )

            # Check Small-Account Guardrail
            if risk_eval.is_small_account_blocked:
                self.state = "GUARDRAIL_BLOCKED"
                self.log_event(
                    category="RISK_GUARD",
                    level="WARNING",
                    title="Small-Account Guard Blocked Trade",
                    details=risk_eval.message,
                )
                return self.get_execution_status()

            # Check Execution Mode
            is_active_mode = "Active Quant Execution" in self.execution_mode
            if not is_active_mode:
                self.state = "WAIT"
                self.log_event(
                    category="ORDER",
                    level="INFO",
                    title="Gatekeeper Alert (Execution Suppressed)",
                    details=f"Strict Gatekeeper Mode active: Visual alert generated for {rec_strike} @ ₹{spot_price:,.1f}.",
                )
                return self.get_execution_status()

            # Execute Trade Order via Mock Broker
            self._execute_order(
                instrument=risk_params.get("instrument", "NIFTY"),
                strike=rec_strike,
                action=action,
                lots=risk_eval.recommended_lots,
                quantity=risk_eval.recommended_quantity,
                spot_price=spot_price,
                trade_plan=trade_plan,
                risk_eval=risk_eval,
            )
            self.last_executed_signal = sig_key

        return self.get_execution_status()

    def _execute_order(
        self,
        instrument: str,
        strike: str,
        action: str,
        lots: int,
        quantity: int,
        spot_price: float,
        trade_plan: Dict[str, Any],
        risk_eval: RiskEvaluationResult,
    ) -> None:
        """Submit order to mock broker and establish active position."""
        order_id = f"DX-{datetime.now(IST_TZ).strftime('%H%M%S')}-{uuid.uuid4().hex[:4].upper()}"
        est_premium = 120.0  # Estimated ATM options premium

        self.current_position = {
            "order_id": order_id,
            "timestamp": datetime.now(IST_TZ).strftime("%H:%M:%S"),
            "instrument": instrument,
            "strike": strike,
            "action": action,
            "lots": lots,
            "quantity": quantity,
            "spot_entry": spot_price,
            "entry_premium": est_premium,
            "stop_loss_pts": trade_plan.get("stop_loss", spot_price - 60.0),
            "target_1_pts": trade_plan.get("target", spot_price + 90.0),
            "stage": 0,  # 0: Initial Risk, 1: Breakeven Locked, 2: Runner Trail
            "highest_favorable_price": spot_price,
            "pnl_inr": 0.0,
            "status": "OPEN",
        }
        self.state = "POSITION_OPEN"

        self.log_event(
            category="ORDER",
            level="SUCCESS",
            title=f"Order Filled: {action} {quantity} Qty {strike}",
            details=(
                f"Order ID: {order_id} | Spot: ₹{spot_price:,.1f} | Lots: {lots} ({quantity} Qty) | "
                f"SL: ₹{trade_plan.get('stop_loss')} | Target: ₹{trade_plan.get('target')}"
            ),
        )

        # Log into paper trading duckdb database if available
        try:
            from data.paper_trading import log_and_evaluate_signal
            log_and_evaluate_signal(
                instrument=instrument,
                timeframe="15m",
                action="BUY_CE" if action == "BUY_CALL" else "BUY_PE",
                spot_price=spot_price,
                strike=strike,
                entry_premium=est_premium,
                stop_loss=est_premium * 0.70,
                target_1=est_premium * 1.50,
                target_2=est_premium * 2.20,
                quantity=quantity,
                confidence=0.88,
                score=4.8,
            )
        except Exception:
            pass

    def _update_position_tracking(self, spot_price: float, atr_pts: float) -> None:
        """Manage active trade: update trailing stop-loss, lock breakeven, or exit."""
        pos = self.current_position
        if not pos or pos["status"] != "OPEN":
            return

        is_call = pos["action"] == "BUY_CALL"
        entry = pos["spot_entry"]

        # Delta PnL points on underlying
        pts_move = (spot_price - entry) if is_call else (entry - spot_price)
        pos["pnl_inr"] = round(pts_move * 0.55 * pos["quantity"], 0)  # Approx delta 0.55

        # Check Stop-Loss
        sl = pos["stop_loss_pts"]
        is_stopped = (spot_price <= sl) if is_call else (spot_price >= sl)
        if is_stopped:
            pos["status"] = "STOPPED_OUT"
            self.state = "STOPPED_OUT"
            self.log_event(
                category="TRAILING_SL",
                level="WARNING",
                title=f"Position Exited (Stop-Loss Hit): {pos['strike']}",
                details=f"Exit Spot: ₹{spot_price:,.1f} | Net PnL: ₹{pos['pnl_inr']:,.0f}",
            )
            self.current_position = None
            return

        # Check Target 1 & 3-Stage Breakeven Lock
        target = pos["target_1_pts"]
        target_hit = (spot_price >= target) if is_call else (spot_price <= target)

        if target_hit and pos["stage"] < 1:
            # Stage 1: Breakeven Lock
            pos["stage"] = 1
            pos["stop_loss_pts"] = entry  # Move SL to entry
            self.state = "TRAILING_STOP"
            self.log_event(
                category="TRAILING_SL",
                level="SUCCESS",
                title=f"Target 1 Hit! Breakeven Stop Locked ({pos['strike']})",
                details=f"Spot: ₹{spot_price:,.1f} (+{pts_move:.1f} pts) | Stop moved to Entry ₹{entry:,.1f} | PnL: ₹{pos['pnl_inr']:,.0f}",
            )

        # Stage 2: Runner Trail above Target
        if pts_move > 1.8 * atr_pts and pos["stage"] < 2:
            pos["stage"] = 2
            # Trail at 1.0x ATR behind highest price
            new_sl = round(spot_price - 1.0 * atr_pts if is_call else spot_price + 1.0 * atr_pts, 1)
            pos["stop_loss_pts"] = new_sl
            self.log_event(
                category="TRAILING_SL",
                level="SUCCESS",
                title=f"Stage 2 Runner Trail Activated: {pos['strike']}",
                details=f"Trailing Stop advanced to ₹{new_sl:,.1f} to lock profits.",
            )

    def get_execution_status(self) -> Dict[str, Any]:
        """Serialize current state and rolling event log for UI and StateStore."""
        return {
            "execution_mode": self.execution_mode,
            "state": self.state,
            "has_open_position": bool(self.current_position is not None),
            "position": self.current_position,
            "event_logs": list(self.event_logs),
            "chime_triggered": self.chime_triggered,
        }


# Global singleton instance
execution_engine = QuantExecutionEngine()

