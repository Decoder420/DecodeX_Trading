"""DecodeX Trading — Comprehensive Quant Execution & Risk Engine Unit Tests."""

import pytest
from pathlib import Path
from data.risk_engine import RiskCalculator, RiskEvaluationResult
from data.execution_engine import QuantExecutionEngine
from data.state_store import StateStore


def test_risk_calculator_normal_sizing():
    """Verify position sizing under institutional capital parameters."""
    res = RiskCalculator.evaluate_risk(
        account_equity=1_000_000.0,
        risk_per_trade_pct=1.0,
        atr_multiplier=1.5,
        instrument="NIFTY",
        atr_pts=45.0,
    )
    # Max risk = 10,000 INR
    assert res.max_risk_inr == 10_000.0
    # Stop distance = 45 * 1.5 = 67.5 pts
    assert res.stop_distance_pts == 67.5
    # Risk per lot = 67.5 * 65 = 4,387.5 INR
    assert res.risk_per_lot_inr == 4387.5
    # Recommended lots = 10,000 // 4,387.5 = 2 lots
    assert res.recommended_lots == 2
    assert res.recommended_quantity == 130
    assert res.is_small_account_blocked is False
    assert res.guardrail_status == "SAFE"


def test_risk_calculator_small_account_guard_blocks():
    """Verify that Small-Account Guard strictly blocks trade if 1 lot risk exceeds max allowed risk."""
    res = RiskCalculator.evaluate_risk(
        account_equity=50_000.0,
        risk_per_trade_pct=1.0,  # Max risk = 500 INR
        atr_multiplier=1.5,
        instrument="NIFTY",
        atr_pts=45.0,            # 1 lot risk = 4,387.5 INR
    )
    assert res.max_risk_inr == 500.0
    assert res.risk_per_lot_inr == 4387.5
    assert res.recommended_lots == 0
    assert res.recommended_quantity == 0
    assert res.is_small_account_blocked is True
    assert res.guardrail_status == "BLOCKED"
    assert "SMALL-ACCOUNT GUARD TRIGGERED" in res.message


def test_risk_calculator_instruments_lot_sizes():
    """Verify canonical lot sizes across indices."""
    assert RiskCalculator.get_lot_size("NIFTY") == 65
    assert RiskCalculator.get_lot_size("BANKNIFTY") == 30
    assert RiskCalculator.get_lot_size("SENSEX") == 20


def test_quant_execution_engine_active_trade_flow():
    """Verify confluence score >= 4.0 triggers mock order and establishes active position."""
    engine = QuantExecutionEngine()
    engine.set_execution_mode("Active Quant Execution (Live Signals)")

    confluence = {
        "signal": "BULLISH ENTRY (15m + 3m Converged)",
        "score": 4.8,
        "bias_15m": "BULLISH",
        "trigger_3m": "TRIGGER_LONG",
        "trade_plan": {
            "action": "BUY_CALL",
            "entry": 25050.0,
            "stop_loss": 24982.5,
            "target": 25153.5,
            "recommended_strike": "25050 CE",
            "atr_pts": 45.0,
        },
    }

    risk_params = {
        "account_equity": 1_000_000.0,
        "risk_pct": 1.0,
        "atr_mult": 1.5,
        "instrument": "NIFTY",
    }

    status = engine.evaluate_and_execute(
        confluence_data=confluence,
        risk_params=risk_params,
        spot_price=25050.0,
    )

    assert status["state"] == "POSITION_OPEN"
    assert status["has_open_position"] is True
    pos = status["position"]
    assert pos["action"] == "BUY_CALL"
    assert pos["strike"] == "25050 CE"
    assert pos["lots"] == 2
    assert pos["quantity"] == 130
    assert pos["spot_entry"] == 25050.0
    assert len(status["event_logs"]) > 0


def test_quant_execution_engine_gatekeeper_mode_suppression():
    """Verify Strict Risk Gatekeeper mode suppresses order dispatch and only emits alerts."""
    engine = QuantExecutionEngine()
    engine.set_execution_mode("Strict Risk Gatekeeper (Read-Only)")

    confluence = {
        "signal": "BULLISH ENTRY (15m + 3m Converged)",
        "score": 5.0,
        "bias_15m": "BULLISH",
        "trigger_3m": "TRIGGER_LONG",
        "trade_plan": {
            "action": "BUY_CALL",
            "entry": 25050.0,
            "stop_loss": 24982.5,
            "target": 25153.5,
            "recommended_strike": "25050 CE",
            "atr_pts": 45.0,
        },
    }

    risk_params = {
        "account_equity": 1_000_000.0,
        "risk_pct": 1.0,
        "atr_mult": 1.5,
        "instrument": "NIFTY",
    }

    status = engine.evaluate_and_execute(
        confluence_data=confluence,
        risk_params=risk_params,
        spot_price=25050.0,
    )

    # Position must NOT be opened in Gatekeeper mode
    assert status["has_open_position"] is False
    assert status["position"] is None
    # Event log must record Gatekeeper alert
    gate_events = [ev for ev in status["event_logs"] if "Gatekeeper" in ev["title"]]
    assert len(gate_events) > 0


def test_quant_execution_trailing_sl_and_breakeven_lock():
    """Verify 3-stage breakeven lock and runner trailing stop management."""
    engine = QuantExecutionEngine()
    engine.set_execution_mode("Active Quant Execution (Live Signals)")

    # Open trade at 25000 with target at 25050 and initial SL at 24940
    confluence = {
        "signal": "BULLISH ENTRY",
        "score": 4.5,
        "trade_plan": {
            "action": "BUY_CALL",
            "entry": 25000.0,
            "stop_loss": 24940.0,
            "target": 25050.0,
            "recommended_strike": "25000 CE",
            "atr_pts": 40.0,
        },
    }
    risk_params = {"account_equity": 1_000_000.0, "risk_pct": 1.0, "atr_mult": 1.5, "instrument": "NIFTY"}
    engine.evaluate_and_execute(confluence, risk_params, spot_price=25000.0)

    assert engine.current_position["stage"] == 0
    assert engine.current_position["stop_loss_pts"] == 24940.0

    # 1. Price advances to Target 1 (25055) -> Triggers Stage 1 Breakeven Lock
    engine.evaluate_and_execute(confluence, risk_params, spot_price=25055.0)
    assert engine.current_position["stage"] == 1
    assert engine.current_position["stop_loss_pts"] == 25000.0  # SL moved to entry
    assert engine.state == "TRAILING_STOP"

    # 2. Price advances further to 25110 (> 1.8 * 40 = 72 pts move) -> Runner Trail Stage 2
    engine.evaluate_and_execute(confluence, risk_params, spot_price=25110.0)
    assert engine.current_position["stage"] == 2
    assert engine.current_position["stop_loss_pts"] == 25070.0  # 25110 - 40.0 = 25070.0

    # 3. Price falls back to 25065 (below 25070 SL) -> Position exits
    engine.evaluate_and_execute(confluence, risk_params, spot_price=25065.0)
    assert engine.current_position is None
    assert engine.state == "STOPPED_OUT"


def test_state_store_controls_sync(tmp_path):
    """Verify two-way decoupled controls exchange between UI and Engine."""
    ctrl_file = tmp_path / "test_controls.json"
    store = StateStore(controls_path=ctrl_file)

    controls = {
        "op_mode": "Strict Risk Gatekeeper (Read-Only)",
        "instrument": "BANKNIFTY",
        "account_equity": 500_000.0,
        "risk_pct": 2.0,
        "atr_mult": 2.0,
    }
    assert store.set_controls(controls) is True

    loaded = store.get_controls()
    assert loaded["op_mode"] == "Strict Risk Gatekeeper (Read-Only)"
    assert loaded["instrument"] == "BANKNIFTY"
    assert loaded["account_equity"] == 500_000.0
    assert loaded["risk_pct"] == 2.0
    assert loaded["atr_mult"] == 2.0
