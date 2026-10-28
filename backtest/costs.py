"""Effective-dated transaction cost calculation for Indian index futures proxy.

DISCLAIMER:
- Models index futures contract transaction costs (tradable proxy).
- SENSEX derivatives prior to 2023 relaunch are hypothetical / back-extended.
- Unit convention: 1.0 = 1.0% (e.g., 0.02 = 0.02%, 18.0 = 18.0%).
- Multiplier: turnover * (rate_pct / 100.0).
- Slippage is modeled in basis points (bps) per side: price * (bps / 10000.0).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
import logging
from typing import Any, Dict, List, Optional
import pandas as pd

from config.loader import ConfigManager, config_manager

logger = logging.getLogger(__name__)


@dataclass
class CostBreakdown:
    """Detailed fee breakdown for a trade leg or round-trip trade."""
    turnover: float
    brokerage: float
    stt: float
    stamp_duty: float
    exchange_charges: float
    sebi_turnover_fee: float
    gst: float
    slippage_cost: float
    total_cost: float
    effective_rate_pct: float  # total_cost / turnover * 100
    slippage_bps: float
    schedule_date: str
    ipft: float = 0.0  # Investor Protection Fund Trust charge



class CostCalculator:
    """Computes statutory, exchange, brokerage, and slippage costs using effective-dated schedules."""

    def __init__(self, cfg: Optional[ConfigManager] = None) -> None:
        self.cfg = cfg or config_manager
        self.schedules = self._load_schedules()
        self.base_slippage_bps = float(self.cfg.get("cost_parameters.slippage.base_bps", 1.5))
        self.stress_slippage_bps = float(self.cfg.get("cost_parameters.slippage.stress_bps", 5.0))
        self.default_brokerage = float(self.cfg.get("cost_parameters.default_brokerage_per_order", 20.0))

    def _load_schedules(self) -> List[Dict[str, Any]]:
        raw_schedules = self.cfg.get("cost_schedules", [])
        if not raw_schedules:
            # Fallback schedule if not specified
            return [
                {
                    "effective_from": "2010-01-01",
                    "stt_sell_pct": 0.02,
                    "stamp_duty_buy_pct": 0.002,
                    "exchange_pct": 0.0019,
                    "sebi_turnover_pct": 0.0001,
                    "gst_pct": 18.0,
                    "brokerage_per_order": 20.0,
                }
            ]

        parsed: List[Dict[str, Any]] = []
        for s in raw_schedules:
            d = datetime.strptime(str(s["effective_from"]), "%Y-%m-%d").date()
            parsed.append({**s, "_date": d})

        parsed.sort(key=lambda x: x["_date"])
        return parsed

    def get_schedule(self, trade_date: date) -> Dict[str, Any]:
        """Find the most recent cost schedule applicable on trade_date."""
        applicable = self.schedules[0]
        for s in self.schedules:
            if s["_date"] <= trade_date:
                applicable = s
            else:
                break
        return applicable

    def calculate_trade_leg_cost(
        self,
        price: float,
        quantity: float,
        side: str,  # "BUY" or "SELL"
        trade_date: date,
        slippage_bps: Optional[float] = None,
    ) -> CostBreakdown:
        """Calculate transaction costs for a single execution leg (entry or exit).

        Args:
            price: Executed price of the index futures contract.
            quantity: Number of contracts / index units.
            side: "BUY" or "SELL".
            trade_date: Trade execution date for effective cost lookup.
            slippage_bps: Slippage in basis points (defaults to base_slippage_bps).

        Returns:
            CostBreakdown detailing each fee item.
        """
        turnover = price * quantity
        if turnover <= 0:
            return CostBreakdown(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, str(trade_date))

        side_upper = side.upper()
        if side_upper not in ["BUY", "SELL"]:
            raise ValueError(f"Side must be 'BUY' or 'SELL', got {side}")

        sched = self.get_schedule(trade_date)
        bps = self.base_slippage_bps if slippage_bps is None else slippage_bps

        # Brokerage (flat INR 20 per order)
        brokerage = float(sched.get("brokerage_per_order", self.default_brokerage))

        # STT: Levied exclusively on SELL turnover in equity index futures
        stt_pct = float(sched.get("stt_sell_pct", 0.02))
        stt = turnover * (stt_pct / 100.0) if side_upper == "SELL" else 0.0

        # Stamp Duty: Levied on BUY turnover in equity index futures
        stamp_pct = float(sched.get("stamp_duty_buy_pct", 0.002))
        stamp_duty = turnover * (stamp_pct / 100.0) if side_upper == "BUY" else 0.0

        # Exchange Transaction Charges: Levied on both Buy and Sell turnover
        exchange_pct = float(sched.get("exchange_pct", 0.0019))
        exchange_charges = turnover * (exchange_pct / 100.0)

        # Investor Protection Fund Trust (IPFT): Levied on both Buy and Sell turnover
        ipft_pct = float(sched.get("ipft_pct", 0.0))
        ipft = turnover * (ipft_pct / 100.0)

        # SEBI Turnover Fee: Levied on both Buy and Sell turnover
        sebi_pct = float(sched.get("sebi_turnover_pct", 0.0001))
        sebi_fee = turnover * (sebi_pct / 100.0)

        # GST: 18.0% on (Brokerage + Exchange Charges + IPFT + SEBI Fee)
        gst_pct = float(sched.get("gst_pct", 18.0))
        gst_taxable = brokerage + exchange_charges + ipft + sebi_fee
        gst = gst_taxable * (gst_pct / 100.0)

        # Slippage: modeled in basis points per side
        slippage_cost = turnover * (bps / 10000.0)

        total_cost = brokerage + stt + stamp_duty + exchange_charges + ipft + sebi_fee + gst + slippage_cost
        effective_rate = (total_cost / turnover) * 100.0

        return CostBreakdown(
            turnover=turnover,
            brokerage=brokerage,
            stt=stt,
            stamp_duty=stamp_duty,
            exchange_charges=exchange_charges,
            sebi_turnover_fee=sebi_fee,
            gst=gst,
            slippage_cost=slippage_cost,
            total_cost=total_cost,
            effective_rate_pct=effective_rate,
            slippage_bps=bps,
            schedule_date=str(sched["effective_from"]),
            ipft=ipft,
        )

    def calculate_round_trip_cost(
        self,
        entry_price: float,
        exit_price: float,
        quantity: float,
        entry_date: date,
        exit_date: date,
        is_long: bool = True,
        slippage_bps: Optional[float] = None,
    ) -> CostBreakdown:
        """Calculate complete round-trip costs across entry and exit legs."""
        entry_side = "BUY" if is_long else "SELL"
        exit_side = "SELL" if is_long else "BUY"

        c_entry = self.calculate_trade_leg_cost(entry_price, quantity, entry_side, entry_date, slippage_bps)
        c_exit = self.calculate_trade_leg_cost(exit_price, quantity, exit_side, exit_date, slippage_bps)

        total_turnover = c_entry.turnover + c_exit.turnover
        total_cost = c_entry.total_cost + c_exit.total_cost
        effective_rate = (total_cost / total_turnover * 100.0) if total_turnover > 0 else 0.0

        return CostBreakdown(
            turnover=total_turnover,
            brokerage=c_entry.brokerage + c_exit.brokerage,
            stt=c_entry.stt + c_exit.stt,
            stamp_duty=c_entry.stamp_duty + c_exit.stamp_duty,
            exchange_charges=c_entry.exchange_charges + c_exit.exchange_charges,
            sebi_turnover_fee=c_entry.sebi_turnover_fee + c_exit.sebi_turnover_fee,
            gst=c_entry.gst + c_exit.gst,
            slippage_cost=c_entry.slippage_cost + c_exit.slippage_cost,
            total_cost=total_cost,
            effective_rate_pct=effective_rate,
            slippage_bps=c_entry.slippage_bps,
            schedule_date=f"{c_entry.schedule_date} -> {c_exit.schedule_date}",
            ipft=c_entry.ipft + c_exit.ipft,
        )
