"""Causal event-driven backtesting execution engine for index futures proxy."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
import logging
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd

from backtest.costs import CostBreakdown, CostCalculator
from backtest.position_sizing import PositionSizeResult, RiskManager
from config.loader import ConfigManager, config_manager
from models.base import SignalDirection

logger = logging.getLogger(__name__)


@dataclass
class TradeRecord:
    trade_id: int
    symbol: str
    direction: str                     # "BUY" (Long) or "SELL" (Short)
    entry_date: date
    exit_date: date
    entry_price: float
    exit_price: float
    units: float
    notional_entry: float
    notional_exit: float
    gross_pnl_inr: float
    gross_return_pct: float
    total_cost_inr: float
    net_pnl_inr: float
    net_return_pct: float
    exit_reason: str                   # GAP_STOP_LOSS, GAP_PROFIT_TAKE, STOP_LOSS, PROFIT_TAKE, TIME_LIMIT
    holding_bars: int
    entry_signal_reason: str
    cost_breakdown: Optional[CostBreakdown] = None
    lots_current_contract: float = 0.0 # Informational lot conversion using current lot size


@dataclass
class BacktestResult:
    trades: List[TradeRecord]
    daily_equity: pd.DataFrame
    total_trades: int
    win_rate_pct: float
    profit_factor: float
    gross_pnl_inr: float
    total_costs_inr: float
    net_pnl_inr: float
    final_equity: float
    total_return_pct: float
    cagr_pct: float
    max_drawdown_pct: float
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    kill_switch_triggers: int
    total_days_paused: int
    true_max_drawdown_pct: float
    slippage_mode: str                 # "base" (1.5 bps) or "stress" (5.0 bps)


class BacktestEngine:
    """Executes trade signals causally with open-fill gap logic, conservative intraday breach, and fees."""

    def __init__(
        self,
        cfg: Optional[ConfigManager] = None,
        cost_calculator: Optional[CostCalculator] = None,
        slippage_mode: str = "base",  # "base" (1.5 bps) or "stress" (5.0 bps)
        starting_capital: float = 1000000.0,
        risk_per_trade_pct: float = 1.0,
        kill_switch_drawdown_pct: float = 15.0,
        kill_switch_pause_days: int = 20,
    ) -> None:
        self.cfg = cfg or config_manager
        self.cost_calc = cost_calculator or CostCalculator(self.cfg)
        self.slippage_mode = slippage_mode.lower()
        self.slippage_bps = (
            self.cost_calc.stress_slippage_bps if self.slippage_mode == "stress" else self.cost_calc.base_slippage_bps
        )
        self.starting_capital = starting_capital
        self.risk_per_trade_pct = risk_per_trade_pct
        self.kill_switch_dd = kill_switch_drawdown_pct
        self.kill_switch_pause = kill_switch_pause_days

    def run_backtest(
        self,
        df: pd.DataFrame,
        signals_df: pd.DataFrame,
        symbol: str = "NIFTY",
        time_limit_bars: int = 10,
        risk_manager: Optional[RiskManager] = None,
    ) -> BacktestResult:
        """Run simulation across market bars and signals.

        Rules:
        - Signal generated at Close of bar t; executed at Open of bar t+1.
        - Zero same-bar fills.
        - Gap beyond stop or target filled at Open price, NOT stop/target price.
        - Conservative intraday: if both high >= target and low <= stop hit, stop loss assumed hit first.
        - Time limit vertical barrier: exit at Close of bar t + time_limit_bars.
        """
        n = len(df)
        if len(signals_df) != n:
            raise ValueError(f"Market data ({n}) and signals ({len(signals_df)}) must be identical length.")

        if risk_manager is not None:
            risk_mgr = risk_manager
            risk_mgr.current_capital = self.starting_capital
        else:
            risk_mgr = RiskManager(
                starting_capital=self.starting_capital,
                risk_per_trade_pct=self.risk_per_trade_pct,
                max_drawdown_limit_pct=self.kill_switch_dd,
                kill_switch_pause_days=self.kill_switch_pause,
            )

        try:
            current_lot_size = self.cfg.get_lot_size(symbol, date.today())
        except KeyError:
            current_lot_size = 50  # Default nominal lot size for pooled multi-index proxy
        timestamps = pd.to_datetime(df["timestamp"]).dt.date.values
        opens = df["open"].values
        highs = df["high"].values
        lows = df["low"].values
        closes = df["close"].values
        vol_col = "realized_vol_20"
        vols = df[vol_col].values if vol_col in df.columns else np.full(n, 0.15)

        sig_directions = signals_df["direction"].values
        sig_stops = signals_df["stop_loss"].values
        sig_targets = signals_df["take_profit"].values
        sig_reasons = signals_df["reasons"].values

        trades: List[TradeRecord] = []
        equity_series: List[float] = [self.starting_capital]
        equity_dates: List[date] = [timestamps[0]]

        in_position = False
        pos_dir = 0
        entry_idx = 0
        entry_price = 0.0
        pos_units = 0.0
        stop_price = 0.0
        target_price = 0.0
        entry_reason = ""
        current_equity = self.starting_capital
        trade_counter = 0

        for t in range(n - 1):
            curr_date = timestamps[t]
            next_date = timestamps[t + 1]

            # 1. Manage active position if open
            if in_position:
                k = t + 1  # Bar being evaluated for exit
                h_k, l_k, o_k, c_k = highs[k], lows[k], opens[k], closes[k]
                holding_bars = k - entry_idx

                exit_triggered = False
                exit_price = 0.0
                exit_reason = ""

                if pos_dir == 1:  # LONG
                    # A. Check Open Gap beyond stop or target
                    if o_k <= stop_price:
                        # Open is below stop -> Fill at Open (adverse gap)
                        exit_price = o_k
                        exit_reason = "GAP_STOP_LOSS"
                        exit_triggered = True
                    elif o_k >= target_price:
                        # Open is above target -> Fill at Open (favorable gap)
                        exit_price = o_k
                        exit_reason = "GAP_PROFIT_TAKE"
                        exit_triggered = True
                    else:
                        # B. Check Intraday High/Low
                        both_hit = (l_k <= stop_price) and (h_k >= target_price)
                        if both_hit:
                            # Conservative assumption: stop hit first
                            exit_price = stop_price
                            exit_reason = "STOP_LOSS_CONSERVATIVE_DUAL"
                            exit_triggered = True
                        elif l_k <= stop_price:
                            exit_price = stop_price
                            exit_reason = "STOP_LOSS"
                            exit_triggered = True
                        elif h_k >= target_price:
                            exit_price = target_price
                            exit_reason = "PROFIT_TAKE"
                            exit_triggered = True
                        elif holding_bars >= time_limit_bars:
                            # C. Time limit vertical barrier
                            exit_price = c_k
                            exit_reason = "TIME_LIMIT_EXIT"
                            exit_triggered = True

                elif pos_dir == -1:  # SHORT
                    # A. Check Open Gap beyond stop or target
                    if o_k >= stop_price:
                        # Open is above stop -> Fill at Open (adverse gap)
                        exit_price = o_k
                        exit_reason = "GAP_STOP_LOSS"
                        exit_triggered = True
                    elif o_k <= target_price:
                        # Open is below target -> Fill at Open (favorable gap)
                        exit_price = o_k
                        exit_reason = "GAP_PROFIT_TAKE"
                        exit_triggered = True
                    else:
                        # B. Check Intraday High/Low
                        both_hit = (h_k >= stop_price) and (l_k <= target_price)
                        if both_hit:
                            exit_price = stop_price
                            exit_reason = "STOP_LOSS_CONSERVATIVE_DUAL"
                            exit_triggered = True
                        elif h_k >= stop_price:
                            exit_price = stop_price
                            exit_reason = "STOP_LOSS"
                            exit_triggered = True
                        elif l_k <= target_price:
                            exit_price = target_price
                            exit_reason = "PROFIT_TAKE"
                            exit_triggered = True
                        elif holding_bars >= time_limit_bars:
                            exit_price = c_k
                            exit_reason = "TIME_LIMIT_EXIT"
                            exit_triggered = True

                if exit_triggered:
                    # Calculate fee and PnL
                    cost_bd = self.cost_calc.calculate_round_trip_cost(
                        entry_price=entry_price,
                        exit_price=exit_price,
                        quantity=pos_units,
                        entry_date=timestamps[entry_idx],
                        exit_date=next_date,
                        is_long=(pos_dir == 1),
                        slippage_bps=self.slippage_bps,
                    )

                    notional_entry = entry_price * pos_units
                    notional_exit = exit_price * pos_units
                    if pos_dir == 1:
                        gross_pnl = (exit_price - entry_price) * pos_units
                        gross_ret = (exit_price - entry_price) / entry_price * 100.0
                    else:
                        gross_pnl = (entry_price - exit_price) * pos_units
                        gross_ret = (entry_price - exit_price) / entry_price * 100.0

                    net_pnl = gross_pnl - cost_bd.total_cost
                    net_ret = (net_pnl / notional_entry * 100.0) if notional_entry > 0 else 0.0

                    current_equity += net_pnl
                    trade_counter += 1

                    trade_rec = TradeRecord(
                        trade_id=trade_counter,
                        symbol=symbol,
                        direction="BUY" if pos_dir == 1 else "SELL",
                        entry_date=timestamps[entry_idx],
                        exit_date=next_date,
                        entry_price=entry_price,
                        exit_price=exit_price,
                        units=pos_units,
                        notional_entry=notional_entry,
                        notional_exit=notional_exit,
                        gross_pnl_inr=gross_pnl,
                        gross_return_pct=gross_ret,
                        total_cost_inr=cost_bd.total_cost,
                        net_pnl_inr=net_pnl,
                        net_return_pct=net_ret,
                        exit_reason=exit_reason,
                        holding_bars=holding_bars,
                        entry_signal_reason=entry_reason,
                        cost_breakdown=cost_bd,
                        lots_current_contract=(pos_units / current_lot_size) if current_lot_size > 0 else 0.0,
                    )
                    trades.append(trade_rec)

                    # Reset position state
                    in_position = False
                    pos_dir = 0

            # 2. Check risk manager kill switch and advance day
            risk_mgr.check_kill_switch(current_equity, curr_date)
            risk_mgr.advance_day()

            # 3. Enter new position if flat and signal triggered at close of bar t
            sig = sig_directions[t]
            if not in_position and sig in [SignalDirection.BUY.value, SignalDirection.SELL.value] and not risk_mgr.is_paused:
                next_open = opens[t + 1]
                st_p = sig_stops[t]
                tp_p = sig_targets[t]

                if st_p > 0 and tp_p > 0:
                    pos_size = risk_mgr.calculate_position_size(
                        entry_price=next_open,
                        stop_loss_price=st_p,
                        realized_vol_annual=vols[t],
                    )

                    if pos_size.units > 0:
                        in_position = True
                        pos_dir = 1 if sig == SignalDirection.BUY.value else -1
                        entry_idx = t + 1
                        entry_price = next_open
                        pos_units = pos_size.units
                        stop_price = st_p
                        target_price = tp_p
                        entry_reason = sig_reasons[t]

            equity_series.append(current_equity)
            equity_dates.append(next_date)

        # Build equity DataFrame
        daily_equity = pd.DataFrame(
            {"timestamp": equity_dates, "equity": equity_series}
        ).drop_duplicates(subset=["timestamp"]).reset_index(drop=True)

        return self._compute_summary(trades, daily_equity, risk_mgr)

    def _compute_summary(
        self,
        trades: List[TradeRecord],
        daily_equity: pd.DataFrame,
        risk_mgr: RiskManager,
    ) -> BacktestResult:
        total_trades = len(trades)
        final_equity = daily_equity["equity"].iloc[-1]
        total_return_pct = ((final_equity - self.starting_capital) / self.starting_capital) * 100.0

        if total_trades == 0:
            return BacktestResult(
                trades=[],
                daily_equity=daily_equity,
                total_trades=0,
                win_rate_pct=0.0,
                profit_factor=0.0,
                gross_pnl_inr=0.0,
                total_costs_inr=0.0,
                net_pnl_inr=0.0,
                final_equity=final_equity,
                total_return_pct=0.0,
                cagr_pct=0.0,
                max_drawdown_pct=0.0,
                sharpe_ratio=0.0,
                sortino_ratio=0.0,
                calmar_ratio=0.0,
                kill_switch_triggers=risk_mgr.kill_switch_trigger_count,
                total_days_paused=risk_mgr.total_days_paused,
                true_max_drawdown_pct=risk_mgr.true_max_drawdown_pct,
                slippage_mode=self.slippage_mode,
            )

        wins = [tr for tr in trades if tr.net_pnl_inr > 0]
        losses = [tr for tr in trades if tr.net_pnl_inr < 0]
        win_rate = (len(wins) / total_trades) * 100.0

        gross_wins = sum(tr.net_pnl_inr for tr in wins)
        gross_losses = abs(sum(tr.net_pnl_inr for tr in losses))
        profit_factor = (gross_wins / gross_losses) if gross_losses > 0 else (99.0 if gross_wins > 0 else 0.0)

        tot_gross_pnl = sum(tr.gross_pnl_inr for tr in trades)
        tot_costs = sum(tr.total_cost_inr for tr in trades)
        tot_net_pnl = sum(tr.net_pnl_inr for tr in trades)

        # CAGR and Drawdown calculation from daily equity
        eq_vals = daily_equity["equity"].values
        days = (daily_equity["timestamp"].iloc[-1] - daily_equity["timestamp"].iloc[0]).days
        years = max(0.1, days / 365.25)
        cagr = ((final_equity / self.starting_capital) ** (1.0 / years) - 1.0) * 100.0

        running_max = np.maximum.accumulate(eq_vals)
        drawdowns = (running_max - eq_vals) / running_max * 100.0
        max_dd = float(np.max(drawdowns)) if len(drawdowns) > 0 else 0.0

        # Daily returns for Sharpe and Sortino
        daily_ret = np.diff(eq_vals) / eq_vals[:-1]
        mean_ret = np.mean(daily_ret) if len(daily_ret) > 0 else 0.0
        std_ret = np.std(daily_ret) if len(daily_ret) > 0 else 1.0

        sharpe = (mean_ret / std_ret * np.sqrt(252)) if std_ret > 0 else 0.0

        downside_ret = daily_ret[daily_ret < 0]
        downside_std = np.std(downside_ret) if len(downside_ret) > 0 else 1.0
        sortino = (mean_ret / downside_std * np.sqrt(252)) if downside_std > 0 else 0.0

        calmar = (cagr / max_dd) if max_dd > 0 else 0.0

        return BacktestResult(
            trades=trades,
            daily_equity=daily_equity,
            total_trades=total_trades,
            win_rate_pct=win_rate,
            profit_factor=profit_factor,
            gross_pnl_inr=tot_gross_pnl,
            total_costs_inr=tot_costs,
            net_pnl_inr=tot_net_pnl,
            final_equity=final_equity,
            total_return_pct=total_return_pct,
            cagr_pct=cagr,
            max_drawdown_pct=max_dd,
            sharpe_ratio=sharpe,
            sortino_ratio=sortino,
            calmar_ratio=calmar,
            kill_switch_triggers=risk_mgr.kill_switch_trigger_count,
            total_days_paused=risk_mgr.total_days_paused,
            true_max_drawdown_pct=max(max_dd, risk_mgr.true_max_drawdown_pct),
            slippage_mode=self.slippage_mode,
        )
