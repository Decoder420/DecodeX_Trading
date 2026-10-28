"""Futures contract rollover manager and decision rule engine."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Dict, Optional, Tuple


@dataclass
class RollSignal:
    should_roll: bool
    reason: str
    near_symbol: str
    next_symbol: str
    roll_spread: Optional[float] = None
    dte: Optional[int] = None
    active_contract: str = "near"


class FuturesRollManager:
    """Manages institutional rollover logic between near-month and next-month index futures."""

    def __init__(self, underlying: str):
        self.underlying = underlying
        self.active_contract: str = "near"  # 'near' or 'next'
        self.rolled_date: Optional[date] = None

    def evaluate_roll(
        self,
        current_time: datetime,
        near_expiry: date,
        near_symbol: str,
        near_price: float,
        near_oi: int,
        near_vol: int,
        next_expiry: date,
        next_symbol: str,
        next_price: float,
        next_oi: int,
        next_vol: int,
    ) -> RollSignal:
        """Evaluate whether to roll from near-month to next-month contract.
        
        Rules:
        1. If already rolled for this cycle, remain on next contract.
        2. DTE (Days to Expiry): (near_expiry - current_date).days
        3. DTE <= 1 (Expiry Eve or Expiry Day):
           - Rule A (OI Crossover): next_oi > near_oi
           - Rule B (Volume Crossover): next_vol > near_vol
        4. DTE == 0 (Expiry Day) at or after 12:00 IST:
           - Rule C (Mandatory Time Cutoff): Force roll before final 3 hours to avoid cash settlement distortions.
        """
        cur_date = current_time.date()
        dte = (near_expiry - cur_date).days
        spread = round(next_price - near_price, 2) if (next_price and near_price) else None

        if self.active_contract == "next":
            return RollSignal(
                should_roll=False,
                reason="Already rolled to next contract",
                near_symbol=near_symbol,
                next_symbol=next_symbol,
                roll_spread=spread,
                dte=dte,
                active_contract=self.active_contract,
            )

        if dte > 1:
            return RollSignal(
                should_roll=False,
                reason=f"Near contract not within roll window (DTE={dte} > 1)",
                near_symbol=near_symbol,
                next_symbol=next_symbol,
                roll_spread=spread,
                dte=dte,
                active_contract=self.active_contract,
            )

        # On Expiry Eve or Expiry Day (DTE <= 1)
        if next_oi > near_oi and next_oi > 0:
            self.active_contract = "next"
            self.rolled_date = cur_date
            return RollSignal(
                should_roll=True,
                reason=f"OI Crossover detected: next_oi ({next_oi}) > near_oi ({near_oi}) at DTE={dte}",
                near_symbol=near_symbol,
                next_symbol=next_symbol,
                roll_spread=spread,
                dte=dte,
                active_contract=self.active_contract,
            )

        if next_vol > near_vol and next_vol > 0:
            self.active_contract = "next"
            self.rolled_date = cur_date
            return RollSignal(
                should_roll=True,
                reason=f"Volume Crossover detected: next_vol ({next_vol}) > near_vol ({near_vol}) at DTE={dte}",
                near_symbol=near_symbol,
                next_symbol=next_symbol,
                roll_spread=spread,
                dte=dte,
                active_contract=self.active_contract,
            )

        # Mandatory Expiry Day cutoff at 12:00 IST
        if dte == 0 and (current_time.hour > 12 or (current_time.hour == 12 and current_time.minute >= 0)):
            self.active_contract = "next"
            self.rolled_date = cur_date
            return RollSignal(
                should_roll=True,
                reason="Mandatory expiry day cutoff reached (12:00 IST on expiry day)",
                near_symbol=near_symbol,
                next_symbol=next_symbol,
                roll_spread=spread,
                dte=dte,
                active_contract=self.active_contract,
            )

        return RollSignal(
            should_roll=False,
            reason=f"Roll criteria not yet met at DTE={dte} (near_oi={near_oi}, next_oi={next_oi})",
            near_symbol=near_symbol,
            next_symbol=next_symbol,
            roll_spread=spread,
            dte=dte,
            active_contract=self.active_contract,
        )
