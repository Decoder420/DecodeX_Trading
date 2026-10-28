"""Quantitative metrics calculation and multi-dimensional performance breakdowns."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

from backtest.engine import TradeRecord


@dataclass
class PerformanceMetricsReport:
    total_trades: int
    win_rate_pct: float
    profit_factor: float
    expectancy_inr_per_trade: float
    avg_win_inr: float
    avg_loss_inr: float
    cagr_pct: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown_pct: float
    calmar_ratio: float
    exposure_pct: float
    exposure_scaled_bnh_return_pct: float
    excess_return_over_exposure_bnh: float
    total_turnover_inr: float
    is_sample_weak: bool               # Flagged True if total_trades < 100
    by_year: Dict[int, Dict[str, Any]]
    by_regime: Dict[str, Dict[str, Any]]
    by_expiry: Dict[str, Dict[str, Any]]
    by_direction: Dict[str, Dict[str, Any]]


def compute_comprehensive_metrics(
    trades: List[TradeRecord],
    daily_equity: pd.DataFrame,
    market_df: Optional[pd.DataFrame] = None,
    starting_capital: float = 1000000.0,
    bnh_cagr_pct: float = 9.10,
) -> PerformanceMetricsReport:
    """Calculate all standard and granular institutional metrics and breakdowns."""
    n_trades = len(trades)
    is_weak = n_trades < 100

    if n_trades == 0:
        return PerformanceMetricsReport(
            total_trades=0,
            win_rate_pct=0.0,
            profit_factor=0.0,
            expectancy_inr_per_trade=0.0,
            avg_win_inr=0.0,
            avg_loss_inr=0.0,
            cagr_pct=0.0,
            sharpe_ratio=0.0,
            sortino_ratio=0.0,
            max_drawdown_pct=0.0,
            calmar_ratio=0.0,
            exposure_pct=0.0,
            exposure_scaled_bnh_return_pct=0.0,
            excess_return_over_exposure_bnh=0.0,
            total_turnover_inr=0.0,
            is_sample_weak=True,
            by_year={},
            by_regime={},
            by_expiry={},
            by_direction={},
        )

    wins = [t.net_pnl_inr for t in trades if t.net_pnl_inr > 0]
    losses = [t.net_pnl_inr for t in trades if t.net_pnl_inr < 0]

    win_rate = (len(wins) / n_trades) * 100.0
    avg_win = float(np.mean(wins)) if wins else 0.0
    avg_loss = float(abs(np.mean(losses))) if losses else 0.0

    sum_wins = sum(wins)
    sum_losses = abs(sum(losses))
    profit_factor = (sum_wins / sum_losses) if sum_losses > 0 else (99.0 if sum_wins > 0 else 0.0)

    total_net_pnl = sum(t.net_pnl_inr for t in trades)
    expectancy = total_net_pnl / n_trades
    total_turnover = sum(t.notional_entry + t.notional_exit for t in trades)

    # Exposure: fraction of bars holding an open trade
    total_market_days = len(daily_equity)
    total_holding_days = sum(t.holding_bars for t in trades)
    exposure_pct = min(100.0, (total_holding_days / total_market_days * 100.0)) if total_market_days > 0 else 0.0

    # Equity curve stats
    eq_vals = daily_equity["equity"].values if not daily_equity.empty else np.array([starting_capital])
    final_eq = eq_vals[-1]
    days = (daily_equity["timestamp"].iloc[-1] - daily_equity["timestamp"].iloc[0]).days if len(daily_equity) > 1 else 365
    years = max(0.5, days / 365.25)
    cagr = ((final_eq / starting_capital) ** (1.0 / years) - 1.0) * 100.0

    running_max = np.maximum.accumulate(eq_vals)
    dd_series = (running_max - eq_vals) / running_max * 100.0
    max_dd = float(np.max(dd_series)) if len(dd_series) > 0 else 0.0

    daily_ret = np.diff(eq_vals) / eq_vals[:-1] if len(eq_vals) > 1 else np.array([0.0])
    std_ret = np.std(daily_ret) if len(daily_ret) > 0 else 1.0
    sharpe = (float(np.mean(daily_ret)) / std_ret * np.sqrt(252)) if std_ret > 0 else 0.0

    downside = daily_ret[daily_ret < 0]
    down_std = np.std(downside) if len(downside) > 0 else 1.0
    sortino = (float(np.mean(daily_ret)) / down_std * np.sqrt(252)) if down_std > 0 else 0.0
    calmar = (cagr / max_dd) if max_dd > 0 else 0.0

    # Exposure-adjusted benchmark comparison
    exposure_scaled_bnh_return_pct = float(exposure_pct / 100.0 * bnh_cagr_pct)
    excess_return_over_exposure_bnh = float(cagr - exposure_scaled_bnh_return_pct)

    # Breakdowns:
    by_year: Dict[int, Dict[str, Any]] = {}
    by_direction: Dict[str, Dict[str, Any]] = {"BUY": {}, "SELL": {}}
    by_expiry: Dict[str, Dict[str, Any]] = {"EXPIRY": {}, "NON_EXPIRY": {}}
    by_regime: Dict[str, Dict[str, Any]] = {}

    trade_df = pd.DataFrame(
        [
            {
                "year": t.entry_date.year,
                "direction": t.direction,
                "net_pnl": t.net_pnl_inr,
                "holding": t.holding_bars,
                "reason": t.entry_signal_reason,
            }
            for t in trades
        ]
    )

    # 1. By Year (combining trade records with daily equity series for returns & Sharpe)
    eq_copy = daily_equity.copy()
    eq_copy["dt"] = pd.to_datetime(eq_copy["timestamp"])
    eq_copy["year"] = eq_copy["dt"].dt.year

    all_years = sorted(list(set(eq_copy["year"].unique()).union(set(trade_df["year"].unique())))) if not trade_df.empty else list(eq_copy["year"].unique())
    for yr in all_years:
        grp = trade_df[trade_df["year"] == yr] if not trade_df.empty else pd.DataFrame()
        n_yr = len(grp)
        w_yr = (grp["net_pnl"] > 0).sum() if n_yr > 0 else 0
        pnl_yr = float(grp["net_pnl"].sum()) if n_yr > 0 else 0.0

        eq_yr = eq_copy[eq_copy["year"] == yr]["equity"].values
        yr_ret_pct = 0.0
        yr_sharpe = 0.0
        if len(eq_yr) > 1:
            yr_ret_pct = float((eq_yr[-1] / eq_yr[0] - 1.0) * 100.0)
            d_ret = np.diff(eq_yr) / eq_yr[:-1]
            s_d = np.std(d_ret)
            if s_d > 1e-8:
                yr_sharpe = float(np.mean(d_ret) / s_d * np.sqrt(252))

        by_year[int(yr)] = {
            "trades": n_yr,
            "win_rate_pct": float(w_yr / n_yr * 100.0) if n_yr > 0 else 0.0,
            "net_pnl_inr": pnl_yr,
            "return_pct": yr_ret_pct,
            "sharpe_ratio": yr_sharpe,
        }

    # 2. By Direction (Long vs Short)
    for d_val in ["BUY", "SELL"]:
        grp = trade_df[trade_df["direction"] == d_val] if not trade_df.empty else pd.DataFrame()
        n_d = len(grp)
        w_d = (grp["net_pnl"] > 0).sum() if n_d > 0 else 0
        pnl_d = float(grp["net_pnl"].sum()) if n_d > 0 else 0.0
        d_sharpe = 0.0
        if n_d > 1:
            d_pnl_arr = grp["net_pnl"].values
            std_pnl = np.std(d_pnl_arr)
            if std_pnl > 1e-8:
                d_sharpe = float((np.mean(d_pnl_arr) / std_pnl) * np.sqrt(min(252, n_d)))

        by_direction[d_val] = {
            "trades": n_d,
            "win_rate_pct": float(w_d / n_d * 100.0) if n_d > 0 else 0.0,
            "net_pnl_inr": pnl_d,
            "sharpe_ratio": d_sharpe,
        }

    # 3. Expiry vs Non-Expiry (lookup in market_df if available)
    if market_df is not None and "is_expiry_day" in market_df.columns:
        date_to_exp = dict(zip(pd.to_datetime(market_df["timestamp"]).dt.date, market_df["is_expiry_day"]))
        exp_trades = [t for t in trades if date_to_exp.get(t.entry_date, False)]
        non_exp_trades = [t for t in trades if not date_to_exp.get(t.entry_date, False)]

        for key, subset in [("EXPIRY", exp_trades), ("NON_EXPIRY", non_exp_trades)]:
            n_sub = len(subset)
            w_sub = len([t for t in subset if t.net_pnl_inr > 0])
            by_expiry[key] = {
                "trades": n_sub,
                "win_rate_pct": float(w_sub / n_sub * 100.0) if n_sub > 0 else 0.0,
                "net_pnl_inr": float(sum(t.net_pnl_inr for t in subset)),
            }

    # 4. By Regime
    if market_df is not None and "regime_label" in market_df.columns:
        date_to_reg = dict(zip(pd.to_datetime(market_df["timestamp"]).dt.date, market_df["regime_label"]))
        for reg_name in ["TRENDING", "RANGING", "HIGH_VOL", "UNKNOWN"]:
            reg_trades = [t for t in trades if date_to_reg.get(t.entry_date, "") == reg_name]
            n_r = len(reg_trades)
            w_r = len([t for t in reg_trades if t.net_pnl_inr > 0])
            pnl_r = float(sum(t.net_pnl_inr for t in reg_trades))
            r_sharpe = 0.0
            if n_r > 1:
                r_pnl_arr = np.array([t.net_pnl_inr for t in reg_trades])
                std_r = np.std(r_pnl_arr)
                if std_r > 1e-8:
                    r_sharpe = float((np.mean(r_pnl_arr) / std_r) * np.sqrt(min(252, n_r)))
            by_regime[reg_name] = {
                "trades": n_r,
                "win_rate_pct": float(w_r / n_r * 100.0) if n_r > 0 else 0.0,
                "net_pnl_inr": pnl_r,
                "sharpe_ratio": r_sharpe,
            }

    return PerformanceMetricsReport(
        total_trades=n_trades,
        win_rate_pct=win_rate,
        profit_factor=profit_factor,
        expectancy_inr_per_trade=expectancy,
        avg_win_inr=avg_win,
        avg_loss_inr=avg_loss,
        cagr_pct=cagr,
        sharpe_ratio=sharpe,
        sortino_ratio=sortino,
        max_drawdown_pct=max_dd,
        calmar_ratio=calmar,
        exposure_pct=exposure_pct,
        exposure_scaled_bnh_return_pct=exposure_scaled_bnh_return_pct,
        excess_return_over_exposure_bnh=excess_return_over_exposure_bnh,
        total_turnover_inr=total_turnover,
        is_sample_weak=is_weak,
        by_year=by_year,
        by_regime=by_regime,
        by_expiry=by_expiry,
        by_direction=by_direction,
    )


def split_sensex_pre_post_may_2023(
    trades: List[TradeRecord],
    daily_equity: pd.DataFrame,
    split_date: date = date(2023, 5, 12),
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Split SENSEX results into Pre-May 2023 (Hypothetical Derivatives) and Post-May 2023 (Live Tradable)."""
    pre_trades = [t for t in trades if t.entry_date < split_date]
    post_trades = [t for t in trades if t.entry_date >= split_date]

    eq_df = daily_equity.copy()
    eq_df["d"] = pd.to_datetime(eq_df["timestamp"]).dt.date
    pre_eq = eq_df[eq_df["d"] < split_date]
    post_eq = eq_df[eq_df["d"] >= split_date]

    def _calc_sub_metrics(sub_trades: List[TradeRecord], sub_eq: pd.DataFrame) -> Dict[str, Any]:
        n = len(sub_trades)
        wins = [t.net_pnl_inr for t in sub_trades if t.net_pnl_inr > 0]
        wr = (len(wins) / n * 100.0) if n > 0 else 0.0
        pnl = sum(t.net_pnl_inr for t in sub_trades)
        sr = 0.0
        if len(sub_eq) > 1:
            d_ret = np.diff(sub_eq["equity"].values) / sub_eq["equity"].values[:-1]
            s = np.std(d_ret)
            if s > 1e-8:
                sr = float(np.mean(d_ret) / s * np.sqrt(252))
        return {
            "trades": n,
            "win_rate_pct": wr,
            "net_pnl_inr": pnl,
            "sharpe_ratio": sr,
        }

    return _calc_sub_metrics(pre_trades, pre_eq), _calc_sub_metrics(post_trades, post_eq)
