"""DecodeX Trading — Dynamic Risk & Position Sizing Engine.

Implements reactive institutional risk sizing:
1. Max Risk (INR) = Account Equity * (Risk % / 100).
2. Structural Stop Distance = ATR * Multiplier (1.0x to 3.0x).
3. Risk per Lot = Stop Distance * Instrument Lot Size.
4. Recommended Lots = Floor(Max Risk / Risk per Lot).
5. Small-Account Guard: Blocks trade execution if a single minimum lot exceeds the max allowed risk.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class RiskEvaluationResult:
    max_risk_inr: float
    stop_distance_pts: float
    risk_per_lot_inr: float
    recommended_lots: int
    recommended_quantity: int
    is_small_account_blocked: bool
    guardrail_status: str       # 'SAFE', 'WARNING', 'BLOCKED'
    message: str


class RiskCalculator:
    """Reactive Risk & Capital Allocation Calculator for Indian Index Options."""

    LOT_SIZES = {
        "NIFTY": 65,
        "BANKNIFTY": 30,
        "SENSEX": 20,
    }

    @classmethod
    def get_lot_size(cls, instrument: str) -> int:
        """Fetch canonical lot size for index."""
        return cls.LOT_SIZES.get(instrument.upper().strip(), 65)

    @classmethod
    def evaluate_risk(
        cls,
        account_equity: float,
        risk_per_trade_pct: float,
        atr_multiplier: float,
        instrument: str = "NIFTY",
        atr_pts: float = 45.0,
    ) -> RiskEvaluationResult:
        """Compute position sizing and validate small-account guardrails."""
        equity = max(1000.0, float(account_equity))
        risk_pct = max(0.1, min(5.0, float(risk_per_trade_pct)))
        mult = max(1.0, min(3.5, float(atr_multiplier)))
        atr = max(5.0, float(atr_pts))

        lot_size = cls.get_lot_size(instrument)

        # 1. Max Risk in INR
        max_risk_inr = round(equity * (risk_pct / 100.0), 2)

        # 2. Stop Distance (pts)
        stop_dist = round(atr * mult, 1)

        # 3. Minimum 1-Lot Risk
        risk_per_lot = round(stop_dist * lot_size, 2)

        # 4. Recommended Sizing
        if risk_per_lot > 0:
            rec_lots = int(max_risk_inr // risk_per_lot)
        else:
            rec_lots = 1

        # 5. Small-Account Guardrail Validation
        if max_risk_inr < risk_per_lot:
            # Account cannot absorb even a single lot within the risk budget
            is_blocked = True
            rec_lots = 0
            rec_qty = 0
            guard_status = "BLOCKED"
            pct_exceeded = round(((risk_per_lot - max_risk_inr) / max_risk_inr) * 100, 1)
            msg = (
                f"⚠️ SMALL-ACCOUNT GUARD TRIGGERED: Minimum 1 lot risk is ₹{risk_per_lot:,.0f}, "
                f"which exceeds your ₹{max_risk_inr:,.0f} limit by {pct_exceeded}%. Automated execution BLOCKED."
            )
        elif rec_lots == 1 and (risk_per_lot > 0.85 * max_risk_inr):
            is_blocked = False
            rec_lots = 1
            rec_qty = lot_size
            guard_status = "WARNING"
            msg = f"⚠️ Near Risk Limit: 1 lot consumes {round((risk_per_lot/max_risk_inr)*100)}% of your allocated budget."
        else:
            is_blocked = False
            rec_lots = max(1, rec_lots)
            rec_qty = rec_lots * lot_size
            guard_status = "SAFE"
            msg = f"✅ Position Sizing Safe: {rec_lots} Lot{'s' if rec_lots > 1 else ''} ({rec_qty} Qty) approved."

        return RiskEvaluationResult(
            max_risk_inr=max_risk_inr,
            stop_distance_pts=stop_dist,
            risk_per_lot_inr=risk_per_lot,
            recommended_lots=rec_lots,
            recommended_quantity=rec_lots * lot_size,
            is_small_account_blocked=is_blocked,
            guardrail_status=guard_status,
            message=msg,
        )

