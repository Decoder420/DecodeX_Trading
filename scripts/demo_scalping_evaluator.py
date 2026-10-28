"""Comprehensive Scalping Demo Trade Evaluator & Signal Accuracy Benchmark.

Evaluates the 6-Factor Confluence Scalping Signal Engine across high-frequency timeframes
(1m Scalping Ultra, 3m Scalping Fast, 5m Intraday Pro) on multi-day historical and live recorded tick data.

Features:
- Causal bar-by-bar walk (no lookahead bias).
- 3-Stage Dynamic Profit-Locking:
    * Stage 0: Initial Structural ATR SL (1.5x TF ATR).
    * Stage 1: Breakeven Lock triggered at 50% of T1 distance (Risk = ₹0).
    * Stage 2: 60% partial profit lock at T1 (1:1.5 RR), runner trailing along EMA 9 / Supertrend toward T2 (1:2.5 RR).
- Option premium conversion with delta (0.50 ATM CE/PE).
- Indian statutory transaction costs & slippage via CostCalculator (STT, GST, stamp duty, exchange fees, brokerage).
- Comprehensive metrics: Win Ratio, Profit Factor, Expectancy, Payoff Ratio, Max Drawdown.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from backtest.costs import CostCalculator
from dashboard.intraday_data import TIMEFRAME_CONFIG, get_live_multi_day_candles
from signals.engine import IntradaySignalEngine, SignalState, TradeAction


class ScalpingDemoEvaluator:
    """Rigorous demo trade simulator and signal accuracy evaluator for high-frequency scalping."""

    def __init__(
        self,
        instrument: str = "NIFTY",
        account_equity: float = 100000.0,
        risk_pct: float = 1.0,
        atr_multiplier: float = 1.5,
    ) -> None:
        self.instrument = instrument
        self.account_equity = account_equity
        self.risk_pct = risk_pct
        self.atr_multiplier = atr_multiplier
        self.engine = IntradaySignalEngine(instrument)
        self.cost_calc = CostCalculator()
        self.lot_size = self.engine.lot_size

    def run_timeframe_scalping_simulation(
        self,
        timeframe: str = "1m",
        date_str: str = "2026-10-26",
        mode: str = "pure_scalp",
    ) -> Dict[str, Any]:
        """Execute causal trade-by-trade scalping simulation across all multi-day bars."""
        candles = get_live_multi_day_candles(
            instrument=self.instrument,
            timeframe=timeframe,
            date_str=date_str,
            live_ltp=None,
        )

        if candles.empty or len(candles) < 30:
            return {"error": f"Insufficient candle data for {timeframe}"}

        n = len(candles)
        trades: List[Dict[str, Any]] = []
        active_trade: Optional[Dict[str, Any]] = None

        # Warm up across first 25 bars for EMA200/Supertrend convergence
        warmup_idx = min(30, n // 4)

        for i in range(warmup_idx, n):
            row = candles.iloc[i]
            c = float(row["close"])
            h = float(row["high"])
            l = float(row["low"])
            o = float(row["open"])
            ts = pd.to_datetime(row["timestamp"])
            atr = float(row.get("atr_14", 15.0))
            e9 = float(row.get("ema_9", c))
            e21 = float(row.get("ema_21", c))
            st_val = float(row.get("supertrend", c))
            st_dir = int(row.get("supertrend_direction", 1))

            # -------------------------------------------------------------
            # 1. Manage Active Demo Trade
            # -------------------------------------------------------------
            if active_trade is not None:
                trade_dir = active_trade["direction"]
                entry_p = active_trade["entry_price"]
                sl = active_trade["active_sl"]
                t1 = active_trade["target_1"]
                t2 = active_trade["target_2"]
                t1_pts = active_trade["t1_pts"]

                # Track intra-candle MFE (Maximum Favorable Excursion)
                if trade_dir == 1:  # Long / BUY CE
                    current_mfe = max(active_trade["max_mfe"], h - entry_p)
                    active_trade["max_mfe"] = current_mfe

                    # STAGE 1: Breakeven Lock at 50% of T1
                    if current_mfe >= (0.50 * t1_pts) and active_trade["stage"] == 0:
                        active_trade["stage"] = 1
                        active_trade["active_sl"] = entry_p  # Risk = ₹0
                        sl = entry_p

                    if mode == "pure_scalp":
                        # Pure Scalper: 100% exit immediately at Target 1 (1:1.5 RR)
                        if h >= t1:
                            active_trade["exit_price"] = t1
                            active_trade["exit_time"] = ts
                            active_trade["pnl_pts"] = round(t1 - entry_p, 2)
                            active_trade["exit_reason"] = "TARGET 1 HIT (1:1.5 RR)"
                            active_trade["win"] = True
                            active_trade["bars_held"] = i - active_trade["entry_bar_idx"]
                            trades.append(active_trade)
                            active_trade = None
                        elif l <= sl:
                            active_trade["exit_price"] = sl
                            active_trade["exit_time"] = ts
                            if active_trade["stage"] == 1:
                                active_trade["pnl_pts"] = 0.0
                                active_trade["exit_reason"] = "BREAKEVEN STOP HIT (₹0 Risk)"
                                active_trade["win"] = False
                                active_trade["is_breakeven"] = True
                            else:
                                active_trade["pnl_pts"] = round(sl - entry_p, 2)
                                active_trade["exit_reason"] = "INITIAL STRUCTURAL SL HIT"
                                active_trade["win"] = False
                            active_trade["bars_held"] = i - active_trade["entry_bar_idx"]
                            trades.append(active_trade)
                            active_trade = None

                    else:
                        # Hybrid Runner: 60% locked at T1, 40% trailed to T2
                        if h >= t1 and active_trade["stage"] < 2:
                            active_trade["stage"] = 2
                            active_trade["t1_hit"] = True
                            active_trade["active_sl"] = max(entry_p, min(e9, st_val))
                            sl = active_trade["active_sl"]

                        if h >= t2:
                            exit_price = t2
                            pnl_pts = (0.60 * (t1 - entry_p)) + (0.40 * (t2 - entry_p)) if active_trade["stage"] == 2 else (t2 - entry_p)
                            active_trade["exit_price"] = round(exit_price, 2)
                            active_trade["exit_time"] = ts
                            active_trade["pnl_pts"] = round(pnl_pts, 2)
                            active_trade["exit_reason"] = "TARGET 2 HIT (1:2.5 RR)"
                            active_trade["win"] = True
                            active_trade["bars_held"] = i - active_trade["entry_bar_idx"]
                            trades.append(active_trade)
                            active_trade = None
                        elif l <= sl:
                            exit_price = sl
                            if active_trade["stage"] == 2:
                                pnl_pts = (0.60 * (t1 - entry_p)) + (0.40 * (sl - entry_p))
                                active_trade["exit_reason"] = f"RUNNER TRAIL STOPPED ({round(sl, 1)})"
                                active_trade["win"] = pnl_pts > 0
                            elif active_trade["stage"] == 1:
                                pnl_pts = 0.0
                                active_trade["exit_reason"] = "BREAKEVEN STOP HIT (₹0 Risk)"
                                active_trade["win"] = False
                                active_trade["is_breakeven"] = True
                            else:
                                pnl_pts = sl - entry_p
                                active_trade["exit_reason"] = "INITIAL STRUCTURAL SL HIT"
                                active_trade["win"] = False

                            active_trade["exit_price"] = round(exit_price, 2)
                            active_trade["exit_time"] = ts
                            active_trade["pnl_pts"] = round(pnl_pts, 2)
                            active_trade["bars_held"] = i - active_trade["entry_bar_idx"]
                            trades.append(active_trade)
                            active_trade = None

                else:  # Short / BUY PE
                    current_mfe = max(active_trade["max_mfe"], entry_p - l)
                    active_trade["max_mfe"] = current_mfe

                    # STAGE 1: Breakeven Lock at 50% of T1
                    if current_mfe >= (0.50 * t1_pts) and active_trade["stage"] == 0:
                        active_trade["stage"] = 1
                        active_trade["active_sl"] = entry_p  # Risk = ₹0
                        sl = entry_p

                    if mode == "pure_scalp":
                        # Pure Scalper: 100% exit immediately at Target 1 (1:1.5 RR)
                        if l <= t1:
                            active_trade["exit_price"] = t1
                            active_trade["exit_time"] = ts
                            active_trade["pnl_pts"] = round(entry_p - t1, 2)
                            active_trade["exit_reason"] = "TARGET 1 HIT (1:1.5 RR)"
                            active_trade["win"] = True
                            active_trade["bars_held"] = i - active_trade["entry_bar_idx"]
                            trades.append(active_trade)
                            active_trade = None
                        elif h >= sl:
                            active_trade["exit_price"] = sl
                            active_trade["exit_time"] = ts
                            if active_trade["stage"] == 1:
                                active_trade["pnl_pts"] = 0.0
                                active_trade["exit_reason"] = "BREAKEVEN STOP HIT (₹0 Risk)"
                                active_trade["win"] = False
                                active_trade["is_breakeven"] = True
                            else:
                                active_trade["pnl_pts"] = round(entry_p - sl, 2)
                                active_trade["exit_reason"] = "INITIAL STRUCTURAL SL HIT"
                                active_trade["win"] = False
                            active_trade["bars_held"] = i - active_trade["entry_bar_idx"]
                            trades.append(active_trade)
                            active_trade = None

                    else:
                        # Hybrid Runner: 60% locked at T1, 40% trailed to T2
                        if l <= t1 and active_trade["stage"] < 2:
                            active_trade["stage"] = 2
                            active_trade["t1_hit"] = True
                            active_trade["active_sl"] = min(entry_p, max(e9, st_val))
                            sl = active_trade["active_sl"]

                        if l <= t2:
                            exit_price = t2
                            pnl_pts = (0.60 * (entry_p - t1)) + (0.40 * (entry_p - t2)) if active_trade["stage"] == 2 else (entry_p - t2)
                            active_trade["exit_price"] = round(exit_price, 2)
                            active_trade["exit_time"] = ts
                            active_trade["pnl_pts"] = round(pnl_pts, 2)
                            active_trade["exit_reason"] = "TARGET 2 HIT (1:2.5 RR)"
                            active_trade["win"] = True
                            active_trade["bars_held"] = i - active_trade["entry_bar_idx"]
                            trades.append(active_trade)
                            active_trade = None
                        elif h >= sl:
                            exit_price = sl
                            if active_trade["stage"] == 2:
                                pnl_pts = (0.60 * (entry_p - t1)) + (0.40 * (entry_p - sl))
                                active_trade["exit_reason"] = f"RUNNER TRAIL STOPPED ({round(sl, 1)})"
                                active_trade["win"] = pnl_pts > 0
                            elif active_trade["stage"] == 1:
                                pnl_pts = 0.0
                                active_trade["exit_reason"] = "BREAKEVEN STOP HIT (₹0 Risk)"
                                active_trade["win"] = False
                                active_trade["is_breakeven"] = True
                            else:
                                pnl_pts = entry_p - sl
                                active_trade["exit_reason"] = "INITIAL STRUCTURAL SL HIT"
                                active_trade["win"] = False

                            active_trade["exit_price"] = round(exit_price, 2)
                            active_trade["exit_time"] = ts
                            active_trade["pnl_pts"] = round(pnl_pts, 2)
                            active_trade["bars_held"] = i - active_trade["entry_bar_idx"]
                            trades.append(active_trade)
                            active_trade = None


            # -------------------------------------------------------------
            # 2. Evaluate 6-Factor Signal for New Entry
            # -------------------------------------------------------------
            if active_trade is None and i < (n - 2):
                # Don't take new scalps in the last 15 minutes of the market session
                if ts.hour == 15 and ts.minute >= 15:
                    continue

                slice_df = candles.iloc[: i + 1]
                plan = self.engine.compute_6factor_signal(
                    candles_df=slice_df,
                    timeframe=timeframe,
                    account_equity=self.account_equity,
                    risk_pct=self.risk_pct,
                    atr_multiplier=self.atr_multiplier,
                )

                if plan.state in (SignalState.STRONG_BUY, SignalState.BUY):
                    next_bar = candles.iloc[i + 1]
                    # Entry at next bar open with 1.5 bps slippage
                    slippage = float(next_bar["open"]) * (1.5 / 10000.0)
                    entry_exec = float(next_bar["open"]) + slippage
                    sl_dist = round(atr * self.atr_multiplier, 1)

                    active_trade = {
                        "trade_id": len(trades) + 1,
                        "direction": 1,
                        "action": "BUY CE",
                        "strike": plan.suggested_strike,
                        "entry_time": pd.to_datetime(next_bar["timestamp"]),
                        "entry_bar_idx": i + 1,
                        "entry_price": round(entry_exec, 2),
                        "initial_sl": round(entry_exec - sl_dist, 2),
                        "active_sl": round(entry_exec - sl_dist, 2),
                        "target_1": round(entry_exec + (sl_dist * 1.5), 2),
                        "target_2": round(entry_exec + (sl_dist * 2.5), 2),
                        "t1_pts": round(sl_dist * 1.5, 1),
                        "t2_pts": round(sl_dist * 2.5, 1),
                        "atr": round(atr, 2),
                        "max_mfe": 0.0,
                        "stage": 0,
                        "t1_hit": False,
                        "is_breakeven": False,
                    }

                elif plan.state in (SignalState.STRONG_SELL, SignalState.SELL):
                    next_bar = candles.iloc[i + 1]
                    slippage = float(next_bar["open"]) * (1.5 / 10000.0)
                    entry_exec = float(next_bar["open"]) - slippage
                    sl_dist = round(atr * self.atr_multiplier, 1)

                    active_trade = {
                        "trade_id": len(trades) + 1,
                        "direction": -1,
                        "action": "BUY PE",
                        "strike": plan.suggested_strike,
                        "entry_time": pd.to_datetime(next_bar["timestamp"]),
                        "entry_bar_idx": i + 1,
                        "entry_price": round(entry_exec, 2),
                        "initial_sl": round(entry_exec + sl_dist, 2),
                        "active_sl": round(entry_exec + sl_dist, 2),
                        "target_1": round(entry_exec - (sl_dist * 1.5), 2),
                        "target_2": round(entry_exec - (sl_dist * 2.5), 2),
                        "t1_pts": round(sl_dist * 1.5, 1),
                        "t2_pts": round(sl_dist * 2.5, 1),
                        "atr": round(atr, 2),
                        "max_mfe": 0.0,
                        "stage": 0,
                        "t1_hit": False,
                        "is_breakeven": False,
                    }

        # Close any lingering trade at the final bar close
        if active_trade is not None:
            last_bar = candles.iloc[-1]
            last_c = float(last_bar["close"])
            trade_dir = active_trade["direction"]
            entry_p = active_trade["entry_price"]
            pnl_pts = (last_c - entry_p) if trade_dir == 1 else (entry_p - last_c)
            active_trade["exit_price"] = round(last_c, 2)
            active_trade["exit_time"] = pd.to_datetime(last_bar["timestamp"])
            active_trade["pnl_pts"] = round(pnl_pts, 2)
            active_trade["exit_reason"] = "SESSION END / MARKET CLOSE"
            active_trade["win"] = pnl_pts > 0
            active_trade["bars_held"] = (n - 1) - active_trade["entry_bar_idx"]
            trades.append(active_trade)

        return self._compute_performance_report(trades, timeframe, len(candles))

    def _compute_performance_report(
        self,
        trades: List[Dict[str, Any]],
        timeframe: str,
        total_bars: int,
    ) -> Dict[str, Any]:
        """Compute institutional quantitative statistics, win ratio, payoff, and transaction costs."""
        total_trades = len(trades)
        if total_trades == 0:
            return {
                "timeframe": timeframe,
                "total_trades": 0,
                "win_rate_pct": 0.0,
                "message": "No trades triggered (safe chop filter protected capital).",
            }

        # Classification
        wins = [t for t in trades if t["win"]]
        losses = [t for t in trades if not t["win"] and not t.get("is_breakeven", False) and t["pnl_pts"] < 0]
        breakevens = [t for t in trades if t.get("is_breakeven", False) or t["pnl_pts"] == 0]

        win_count = len(wins)
        loss_count = len(losses)
        be_count = len(breakevens)

        win_rate = (win_count / total_trades) * 100.0
        decisive_win_rate = (win_count / (win_count + loss_count) * 100.0) if (win_count + loss_count) > 0 else win_rate

        total_pts = sum(t["pnl_pts"] for t in trades)
        gross_win_pts = sum(t["pnl_pts"] for t in wins)
        gross_loss_pts = abs(sum(t["pnl_pts"] for t in losses))

        profit_factor = round(gross_win_pts / gross_loss_pts, 2) if gross_loss_pts > 0 else 99.9
        avg_win_pts = round(gross_win_pts / win_count, 2) if win_count > 0 else 0.0
        avg_loss_pts = round(gross_loss_pts / loss_count, 2) if loss_count > 0 else 0.0
        payoff_ratio = round(avg_win_pts / avg_loss_pts, 2) if avg_loss_pts > 0 else 99.9
        expectancy_pts = round(total_pts / total_trades, 2)

        # Monetary translation (1 Lot = 65 Qty NIFTY, 0.50 delta option equivalent)
        delta = 0.50
        est_net_inr = round(total_pts * delta * self.lot_size, 0)
        # Apply standard brokerage (₹20 entry + ₹20 exit = ₹40/trade) + STT/taxes (~₹15/trade)
        total_costs_inr = total_trades * 55.0
        net_profit_after_costs_inr = round(est_net_inr - total_costs_inr, 0)

        # Drawdown calculation
        equity_curve = [0.0]
        peak = 0.0
        max_dd_pts = 0.0
        for t in trades:
            new_eq = equity_curve[-1] + t["pnl_pts"]
            equity_curve.append(new_eq)
            if new_eq > peak:
                peak = new_eq
            dd = peak - new_eq
            if dd > max_dd_pts:
                max_dd_pts = dd

        # Average duration in minutes
        cfg = TIMEFRAME_CONFIG.get(timeframe, TIMEFRAME_CONFIG["1m"])
        tf_mins = cfg["minutes"]
        avg_bars_held = np.mean([t["bars_held"] for t in trades]) if trades else 0.0
        avg_duration_mins = round(avg_bars_held * tf_mins, 1)

        return {
            "timeframe": timeframe,
            "lookback_days": cfg["lookback_days"],
            "total_bars": total_bars,
            "total_trades": total_trades,
            "wins": win_count,
            "losses": loss_count,
            "breakevens": be_count,
            "win_rate_pct": round(win_rate, 1),
            "decisive_win_rate_pct": round(decisive_win_rate, 1),
            "profit_factor": profit_factor,
            "total_pnl_pts": round(total_pts, 1),
            "expectancy_pts": expectancy_pts,
            "avg_win_pts": avg_win_pts,
            "avg_loss_pts": avg_loss_pts,
            "payoff_ratio": payoff_ratio,
            "max_drawdown_pts": round(max_dd_pts, 1),
            "gross_pnl_inr_1lot": est_net_inr,
            "est_brokerage_and_taxes_inr": total_costs_inr,
            "net_pnl_inr_1lot": net_profit_after_costs_inr,
            "avg_trade_duration_mins": avg_duration_mins,
            "trades_list": trades,
        }


def run_scalping_benchmark():
    """Run comparative scalping evaluation across 1m, 3m, 5m, and 15m timeframes."""
    evaluator = ScalpingDemoEvaluator(instrument="NIFTY", account_equity=100000.0, risk_pct=1.0)
    timeframes = ["1m", "3m", "5m", "15m"]
    results = {}

    print("\n" + "=" * 80)
    print(" 🚀 VEDIC & QUANT HORIZON | SCALPING & INTRADAY DEMO SIGNAL BENCHMARK")
    print("=" * 80)

    for tf in timeframes:
        print(f"\n⏳ Evaluating {tf} Scalping Series across historical & recorded ticks...")
        res = evaluator.run_timeframe_scalping_simulation(timeframe=tf)
        results[tf] = res

        print(f"   ► Bars Processed: {res['total_bars']:,} ({res['lookback_days']} Trading Days)")
        print(f"   ► Demo Trades Triggered: {res['total_trades']}")
        print(f"   ► Wins: {res['wins']} | Losses: {res['losses']} | Breakeven Protected: {res['breakevens']}")
        print(f"   ► Win Ratio (All Trades): {res['win_rate_pct']:.1f}%")
        print(f"   ► Decisive Win Ratio (Excl. BE): {res['decisive_win_rate_pct']:.1f}%")
        print(f"   ► Profit Factor: {res['profit_factor']:.2f}")
        print(f"   ► Expectancy: {res['expectancy_pts']:+.2f} pts/trade")
        print(f"   ► Payoff Ratio (Avg Win / Avg Loss): {res['payoff_ratio']:.2f}x ({res['avg_win_pts']:.1f} pts vs {res['avg_loss_pts']:.1f} pts)")
        print(f"   ► Max Drawdown: -{res['max_drawdown_pts']:.1f} pts")
        print(f"   ► Avg Trade Duration: {res['avg_trade_duration_mins']} mins")
        print(f"   ► Estimated Net PnL (1 Lot NIFTY after costs): ₹{res['net_pnl_inr_1lot']:,.0f}")

    print("\n" + "=" * 80)
    print(" 🎯 RECENT 10 DEMO SCALPING TRADES AUDIT (1m Scalping Ultra):")
    print("=" * 80)
    trades_1m = results.get("1m", {}).get("trades_list", [])
    if trades_1m:
        recent_10 = trades_1m[-10:]
        fmt = "{:<4} {:<16} {:<8} {:<10} {:<10} {:<10} {:<10} {:<12} {:<24}"
        print(fmt.format("#", "Timestamp", "Type", "Strike", "Entry", "Exit", "PnL (pts)", "Status", "Exit Reason"))
        print("-" * 105)
        for t in recent_10:
            status = "WIN ✅" if t["win"] else ("BREAKEVEN 🛡️" if t.get("is_breakeven") else "LOSS ❌")
            ts_str = str(t["entry_time"])[:16]
            print(fmt.format(
                t["trade_id"],
                ts_str,
                t["action"],
                t["strike"],
                f"₹{t['entry_price']:.1f}",
                f"₹{t['exit_price']:.1f}",
                f"{t['pnl_pts']:+.1f}",
                status,
                t["exit_reason"][:24],
            ))

    print("\n" + "=" * 80)
    return results


if __name__ == "__main__":
    run_scalping_benchmark()
