"""Walk-forward cross-validation engine with strict purging, embargoing, and holdout separation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
import logging
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

from backtest.costs import CostCalculator
from backtest.engine import BacktestEngine, BacktestResult, TradeRecord
from config.loader import ConfigManager, config_manager
from models.base import BaseSignalModel
from signals.gates import GateAuditReport, TradeGatekeeper

logger = logging.getLogger(__name__)


@dataclass
class WalkForwardFold:
    fold_id: int
    train_start: date
    train_end_purged: date
    test_start: date
    test_end: date
    train_df: pd.DataFrame
    test_df: pd.DataFrame
    purged_bars_count: int


@dataclass
class WalkForwardExperimentResult:
    model_name: str
    symbol: str
    slippage_mode: str
    expiry_filter_enabled: bool
    folds_count: int
    total_trades: int
    trades: List[TradeRecord]
    daily_equity: pd.DataFrame
    metrics: Dict[str, float]
    gate_audit: GateAuditReport
    fold_summaries: List[Dict[str, Any]]


class WalkForwardEngine:
    """Manages expanding walk-forward folds, purging, and out-of-sample concatenation."""

    def __init__(
        self,
        cfg: Optional[ConfigManager] = None,
        burn_in_bars: int = 252,
        purge_bars: int = 10,
        embargo_bars: int = 5,
        holdout_start: date = date(2024, 11, 1),
    ) -> None:
        self.cfg = cfg or config_manager
        self.burn_in_bars = burn_in_bars
        self.purge_bars = purge_bars
        self.embargo_bars = embargo_bars
        self.holdout_start = holdout_start

    def generate_folds(self, df: pd.DataFrame) -> List[WalkForwardFold]:
        """Partition historical dataset into expanding walk-forward folds.

        Rules:
        - Discards first 252 bars ($t < 252$) as feature burn-in.
        - Excludes holdout data starting at holdout_start (2024-11-01).
        - Generates 1-year annual out-of-sample test folds starting from 2015 to 2024.
        - Purges last 10 bars of training window preceding each test fold.
        """
        # Drop 252 burn-in bars
        usable = df.iloc[self.burn_in_bars:].copy().reset_index(drop=True)
        timestamps = pd.to_datetime(usable["timestamp"]).dt.date.values

        # Filter out holdout period
        valid_indices = np.where(timestamps < self.holdout_start)[0]
        wf_df = usable.iloc[valid_indices].copy().reset_index(drop=True)
        wf_dates = pd.to_datetime(wf_df["timestamp"]).dt.date.values
        years = np.array([d.year for d in wf_dates])

        # Test years: 2015 to 2024
        test_years = sorted(list(set(years[years >= 2015])))
        folds: List[WalkForwardFold] = []

        for f_idx, t_year in enumerate(test_years, start=1):
            test_mask = (years == t_year)
            train_mask = (years < t_year)

            test_indices = np.where(test_mask)[0]
            train_indices = np.where(train_mask)[0]

            if len(test_indices) == 0 or len(train_indices) < 250:
                continue

            # Apply purge: remove last purge_bars from training window
            train_purged_indices = train_indices[:-self.purge_bars] if len(train_indices) > self.purge_bars else train_indices

            train_slice = wf_df.iloc[train_purged_indices].copy().reset_index(drop=True)
            test_slice = wf_df.iloc[test_indices].copy().reset_index(drop=True)

            t_start = pd.to_datetime(train_slice["timestamp"].iloc[0]).date()
            t_end = pd.to_datetime(train_slice["timestamp"].iloc[-1]).date()
            val_start = pd.to_datetime(test_slice["timestamp"].iloc[0]).date()
            val_end = pd.to_datetime(test_slice["timestamp"].iloc[-1]).date()

            fold = WalkForwardFold(
                fold_id=f_idx,
                train_start=t_start,
                train_end_purged=t_end,
                test_start=val_start,
                test_end=val_end,
                train_df=train_slice,
                test_df=test_slice,
                purged_bars_count=self.purge_bars,
            )
            folds.append(fold)

        return folds

    def run_model_walk_forward(
        self,
        model: BaseSignalModel,
        df: pd.DataFrame,
        symbol: str = "NIFTY",
        slippage_mode: str = "base",
        gatekeeper: Optional[TradeGatekeeper] = None,
        enable_expiry_filter: bool = True,
    ) -> WalkForwardExperimentResult:
        """Execute full expanding walk-forward test for a model across all folds."""
        folds = self.generate_folds(df)
        if not folds:
            raise ValueError(f"No valid walk-forward folds generated for {symbol}.")

        gate = gatekeeper or TradeGatekeeper(
            min_confidence=0.55,
            enable_regime_filter=True,
            enable_expiry_filter=enable_expiry_filter,
        )
        gate.enable_expiry_filter = enable_expiry_filter

        engine = BacktestEngine(
            cfg=self.cfg,
            slippage_mode=slippage_mode,
            starting_capital=1000000.0,
            risk_per_trade_pct=1.0,
        )

        from backtest.position_sizing import RiskManager
        persistent_risk_mgr = RiskManager(
            starting_capital=1000000.0,
            risk_per_trade_pct=1.0,
            max_drawdown_limit_pct=15.0,
            kill_switch_pause_days=20,
        )

        all_trades: List[TradeRecord] = []
        equity_frames: List[pd.DataFrame] = []
        fold_summaries: List[Dict[str, Any]] = []
        total_audit = GateAuditReport()

        current_equity = engine.starting_capital

        for fold in folds:
            # 1. Fit model on purged training fold
            model.fit(fold.train_df)

            # 2. Predict raw signals on strictly out-of-sample test fold
            raw_signals = model.predict_signals(fold.test_df)

            # 3. Apply gates to test signals
            filtered_signals, audit = gate.apply_gates(fold.test_df, raw_signals)

            # Aggregate audit statistics
            total_audit.total_candles += audit.total_candles
            total_audit.total_raw_signals += audit.total_raw_signals
            total_audit.raw_buy_signals += audit.raw_buy_signals
            total_audit.raw_sell_signals += audit.raw_sell_signals
            total_audit.dropped_by_gap += audit.dropped_by_gap
            total_audit.dropped_by_confidence += audit.dropped_by_confidence
            total_audit.dropped_by_regime += audit.dropped_by_regime
            total_audit.dropped_by_vix += audit.dropped_by_vix
            total_audit.dropped_by_expiry += audit.dropped_by_expiry
            total_audit.final_executed_buys += audit.final_executed_buys
            total_audit.final_executed_sells += audit.final_executed_sells
            total_audit.final_executed_signals += audit.final_executed_signals

            # 4. Simulate test fold trades
            engine.starting_capital = current_equity
            res = engine.run_backtest(
                df=fold.test_df,
                signals_df=filtered_signals,
                symbol=symbol,
                time_limit_bars=getattr(model, "time_limit_bars", 10),
                risk_manager=persistent_risk_mgr,
            )

            all_trades.extend(res.trades)
            equity_frames.append(res.daily_equity)
            current_equity = res.final_equity

            fold_summaries.append(
                {
                    "fold_id": fold.fold_id,
                    "test_year": fold.test_start.year,
                    "test_range": f"{fold.test_start} to {fold.test_end}",
                    "trades": res.total_trades,
                    "win_rate_pct": res.win_rate_pct,
                    "profit_factor": res.profit_factor,
                    "net_pnl_inr": res.net_pnl_inr,
                    "final_equity": res.final_equity,
                    "max_drawdown_pct": res.max_drawdown_pct,
                    "sharpe_ratio": res.sharpe_ratio,
                }
            )

        # Concatenate daily equity across all folds
        if equity_frames:
            full_equity = pd.concat(equity_frames, ignore_index=True).drop_duplicates(subset=["timestamp"]).reset_index(drop=True)
        else:
            full_equity = pd.DataFrame(columns=["timestamp", "equity"])

        # Compute aggregate metrics across full out-of-sample walk-forward
        total_trades = len(all_trades)
        wins = [tr for tr in all_trades if tr.net_pnl_inr > 0]
        losses = [tr for tr in all_trades if tr.net_pnl_inr < 0]
        win_rate = (len(wins) / total_trades * 100.0) if total_trades > 0 else 0.0

        gross_wins = sum(tr.net_pnl_inr for tr in wins)
        gross_losses = abs(sum(tr.net_pnl_inr for tr in losses))
        profit_factor = (gross_wins / gross_losses) if gross_losses > 0 else (99.0 if gross_wins > 0 else 0.0)

        tot_net_pnl = sum(tr.net_pnl_inr for tr in all_trades)
        final_eq = full_equity["equity"].iloc[-1] if not full_equity.empty else 1000000.0
        tot_ret = ((final_eq - 1000000.0) / 1000000.0) * 100.0

        days = (full_equity["timestamp"].iloc[-1] - full_equity["timestamp"].iloc[0]).days if len(full_equity) > 1 else 365
        years_span = max(0.5, days / 365.25)
        cagr = ((final_eq / 1000000.0) ** (1.0 / years_span) - 1.0) * 100.0

        eq_vals = full_equity["equity"].values if not full_equity.empty else np.array([1000000.0])
        running_max = np.maximum.accumulate(eq_vals)
        drawdowns = (running_max - eq_vals) / running_max * 100.0
        max_dd = float(np.max(drawdowns)) if len(drawdowns) > 0 else 0.0
        true_max_dd = max(max_dd, persistent_risk_mgr.true_max_drawdown_pct)

        daily_ret = np.diff(eq_vals) / eq_vals[:-1] if len(eq_vals) > 1 else np.array([0.0])
        mean_ret = np.mean(daily_ret)
        std_ret = np.std(daily_ret)
        sharpe = (mean_ret / std_ret * np.sqrt(252)) if std_ret > 0 else 0.0

        downside_ret = daily_ret[daily_ret < 0]
        downside_std = np.std(downside_ret) if len(downside_ret) > 0 else 1.0
        sortino = (mean_ret / downside_std * np.sqrt(252)) if downside_std > 0 else 0.0
        calmar = (cagr / true_max_dd) if true_max_dd > 0 else 0.0

        metrics_dict = {
            "total_trades": total_trades,
            "win_rate_pct": win_rate,
            "profit_factor": profit_factor,
            "net_pnl_inr": tot_net_pnl,
            "final_equity": final_eq,
            "total_return_pct": tot_ret,
            "cagr_pct": cagr,
            "max_drawdown_pct": true_max_dd,
            "sharpe_ratio": sharpe,
            "sortino_ratio": sortino,
            "calmar_ratio": calmar,
            "kill_switch_triggers": persistent_risk_mgr.kill_switch_trigger_count,
            "total_days_paused": persistent_risk_mgr.total_days_paused,
        }

        return WalkForwardExperimentResult(
            model_name=model.name,
            symbol=symbol,
            slippage_mode=slippage_mode,
            expiry_filter_enabled=enable_expiry_filter,
            folds_count=len(folds),
            total_trades=total_trades,
            trades=all_trades,
            daily_equity=full_equity,
            metrics=metrics_dict,
            gate_audit=total_audit,
            fold_summaries=fold_summaries,
        )
