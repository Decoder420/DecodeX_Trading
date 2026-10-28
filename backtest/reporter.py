"""Performance reporting and Decision Gate classification generator."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
import pandas as pd

from backtest.engine import TradeRecord
from backtest.metrics import PerformanceMetricsReport
from backtest.walk_forward import WalkForwardExperimentResult
from signals.gates import GateAuditReport

logger = logging.getLogger(__name__)


def classify_decision_gate(
    metrics: Dict[str, float],
    random_benchmark_rank: float,
    bnh_sharpe: float,
    stress_sharpe: float,
    is_sample_weak: bool,
    bootstrap_diff_ci: Optional[Dict[str, Any]] = None,
    dsr_pvalue: float = 1.0,
    positive_years_pct: float = 0.0,
) -> Tuple[str, str]:
    """Classify model performance into Decision Gate Class A, B, or C using strict institutional criteria.

    Class A Criteria (ALL must be met):
    1. Net Sharpe above Buy & Hold (sr > bnh_sharpe).
    2. Bootstrap 95% CI for the difference (Strategy Sharpe - B&H Sharpe) strictly excludes zero (ci_lower > 0).
    3. Random-signal rank >= 95% (top 5% against 1,000 reshuffled noise seeds).
    4. DSR p-value < 0.10 (statistically significant after multiple testing adjustment).
    5. Positive in at least 70% of walk-forward years.
    6. Positive under 5 bps stress slippage (stress_sharpe > 0).
    7. Sufficient sample size (total_trades >= 100, is_sample_weak is False).

    Anything failing goes to Class B (if net positive) or Class C (if net negative or flat).
    """
    sr = metrics.get("sharpe_ratio", 0.0)
    trades = metrics.get("total_trades", 0)
    diff_excludes_zero = bootstrap_diff_ci.get("excludes_zero", False) if bootstrap_diff_ci else False

    if sr <= 0.0 or metrics.get("cagr_pct", 0.0) <= 0.0:
        return (
            "Class C (No Edge After Costs)",
            "Model produces negative or flat net return after transaction costs and slippage. No statistical edge detected."
        )

    # Check Class A qualification
    failures = []
    if sr <= bnh_sharpe:
        failures.append(f"Sharpe {sr:.2f} <= B&H {bnh_sharpe:.2f}")
    if not diff_excludes_zero:
        ci_str = f"[{bootstrap_diff_ci.get('ci_lower', 0.0):.2f}, {bootstrap_diff_ci.get('ci_upper', 0.0):.2f}]" if bootstrap_diff_ci else "spans zero"
        failures.append(f"Bootstrap difference 95% CI {ci_str} does not exclude zero")
    if random_benchmark_rank < 95.0:
        failures.append(f"Random noise rank {random_benchmark_rank:.1f}% < 95.0%")
    if dsr_pvalue >= 0.10:
        failures.append(f"DSR p-value {dsr_pvalue:.2f} >= 0.10")
    if positive_years_pct < 70.0:
        failures.append(f"Positive years {positive_years_pct:.1f}% < 70.0%")
    if stress_sharpe <= 0.0:
        failures.append(f"Stress Sharpe {stress_sharpe:.2f} <= 0.0")
    if is_sample_weak:
        failures.append(f"Weak sample ({trades} < 100 trades)")

    if not failures:
        return (
            "Class A (Robust Out-of-Sample Edge)",
            f"Statistically validated edge: beats Buy & Hold (Sharpe {sr:.2f} > {bnh_sharpe:.2f}), "
            f"bootstrap difference CI excludes zero, random rank {random_benchmark_rank:.1f}% >= 95%, "
            f"DSR p-value {dsr_pvalue:.2f} < 0.10, positive in {positive_years_pct:.1f}% of years, and survives stress slippage."
        )

    # Class B
    return (
        "Class B (Marginal or Unstable Edge)",
        f"Marginal or unconfirmed candidate; fails Class A criteria: {'; '.join(failures)}."
    )


def generate_markdown_report(
    result: WalkForwardExperimentResult,
    detailed_metrics: PerformanceMetricsReport,
    bnh_metrics: Dict[str, float],
    random_benchmark: Dict[str, Any],
    stress_result: Optional[WalkForwardExperimentResult] = None,
    dsr_pvalue: float = 1.0,
    dsr_details: Optional[Dict[str, Any]] = None,
    bootstrap_diff_ci: Optional[Dict[str, Any]] = None,
    variant_count: int = 162,
    output_path: Optional[Path] = None,
) -> str:
    """Generate comprehensive quantitative markdown report for model evaluation."""
    stress_sr = stress_result.metrics.get("sharpe_ratio", 0.0) if stress_result else result.metrics.get("sharpe_ratio", 0.0)

    # Calculate positive years percentage
    pos_years = sum(1 for y_data in detailed_metrics.by_year.values() if y_data.get("return_pct", 0.0) > 0.0)
    total_years = max(1, len(detailed_metrics.by_year))
    positive_years_pct = (pos_years / total_years) * 100.0

    decision_class, decision_reason = classify_decision_gate(
        metrics=result.metrics,
        random_benchmark_rank=random_benchmark.get("strategy_percentile_rank", 50.0),
        bnh_sharpe=bnh_metrics.get("sharpe_ratio", 0.0),
        stress_sharpe=stress_sr,
        is_sample_weak=detailed_metrics.is_sample_weak,
        bootstrap_diff_ci=bootstrap_diff_ci,
        dsr_pvalue=dsr_pvalue,
        positive_years_pct=positive_years_pct,
    )

    lines: List[str] = [
        f"# Quantitative Walk-Forward Research Report: {result.model_name} on {result.symbol}",
        "",
        "> [!IMPORTANT]",
        "> **Proxy & Historical Continuity Disclaimer**:",
        "> 1. **Index Futures Proxy**: Cash index series are utilized as the tradable proxy for index futures. Basis fluctuations and roll gaps are omitted in this representation.",
        "> 2. **SENSEX Historical Derivative Extension**: SENSEX derivatives contracts prior to the May 2023 relaunch are hypothetical / back-extended.",
        "> 3. **Non-Execution Notice**: This system is built strictly for decision support and quantitative statistical research. Zero live execution. Never implies guaranteed profitability.",
        "> 4. **Validation Status**: **No model is validated. All candidates are marginal, unconfirmed hypotheses.**",
        "",
        f"## 1. Executive Summary & Decision Gate: **{decision_class}**",
        f"- **Verdict Rationale**: {decision_reason}",
        f"- **Model**: `{result.model_name}` | **Instrument**: `{result.symbol}`",
        f"- **Validation Period**: `2015-01-01` to `2024-10-31` (10 Expanding Walk-Forward Folds, Burn-In 252 Bars Dropped)",
        f"- **Slippage Setting**: Base `{result.slippage_mode}` (1.5 bps/side)" + (f" vs Stress (5.0 bps/side)" if stress_result else ""),
        f"- **Sample Size Qualification**: {'⚠️ STATISTICALLY WEAK (< 100 trades)' if detailed_metrics.is_sample_weak else '✅ ADEQUATE SAMPLE (>= 100 trades)'}",
        f"- **True Max Drawdown from All-Time Peak**: **{result.metrics.get('max_drawdown_pct', 0.0):.2f}%**",
        f"- **Kill Switch Triggers**: **{result.metrics.get('kill_switch_triggers', 0)}** times | **Total Days Paused**: **{result.metrics.get('total_days_paused', 0)}** trading days",
        "",
        "---",
        "",
        "## 2. Performance Metrics vs Benchmarks",
        "",
        "| Metric | Walk-Forward Strategy (Base Slippage) | Walk-Forward (Stress 5 bps) | Buy & Hold Benchmark | Exposure-Matched B&H | Random Noise Baseline (Mean) |",
        "| :--- | :---: | :---: | :---: | :---: | :---: |",
        f"| **Sharpe Ratio** | **{result.metrics['sharpe_ratio']:.2f}** | {stress_sr:.2f} | {bnh_metrics.get('sharpe_ratio', 0.0):.2f} | {bnh_metrics.get('sharpe_ratio', 0.0):.2f} | {random_benchmark.get('random_sharpe_mean', 0.0):.2f} |",
        f"| **CAGR** | **{result.metrics['cagr_pct']:.2f}%** | {stress_result.metrics.get('cagr_pct', 0.0) if stress_result else 0.0:.2f}% | {bnh_metrics.get('cagr_pct', 0.0):.2f}% | **{detailed_metrics.exposure_scaled_bnh_return_pct:.2f}%** | N/A |",
        f"| **Excess Return vs Exposure B&H** | **{detailed_metrics.excess_return_over_exposure_bnh:+.2f}%** | N/A | N/A | 0.00% | N/A |",
        f"| **Sortino Ratio** | **{result.metrics['sortino_ratio']:.2f}** | {stress_result.metrics.get('sortino_ratio', 0.0) if stress_result else 0.0:.2f} | N/A | N/A | N/A |",
        f"| **Max Drawdown (True Peak)** | **{result.metrics['max_drawdown_pct']:.2f}%** | {stress_result.metrics.get('max_drawdown_pct', 0.0) if stress_result else 0.0:.2f}% | {bnh_metrics.get('max_drawdown_pct', 0.0):.2f}% | N/A | N/A |",
        f"| **Calmar Ratio** | **{result.metrics['calmar_ratio']:.2f}** | {stress_result.metrics.get('calmar_ratio', 0.0) if stress_result else 0.0:.2f} | N/A | N/A | N/A |",
        f"| **Win Rate** | **{result.metrics['win_rate_pct']:.2f}%** | {stress_result.metrics.get('win_rate_pct', 0.0) if stress_result else 0.0:.2f}% | N/A | N/A | ~50.0% |",
        f"| **Profit Factor** | **{result.metrics['profit_factor']:.2f}** | {stress_result.metrics.get('profit_factor', 0.0) if stress_result else 0.0:.2f} | N/A | N/A | ~1.00 |",
        f"| **Total Net P&L** | **Rs {result.metrics['net_pnl_inr']:,.2f}** | Rs {stress_result.metrics.get('net_pnl_inr', 0.0) if stress_result else 0.0:,.2f} | N/A | N/A | N/A |",
        f"| **Total Trade Count** | **{result.total_trades}** | {stress_result.total_trades if stress_result else result.total_trades} | 1 | N/A | {result.total_trades} |",
        f"| **Market Exposure** | **{detailed_metrics.exposure_pct:.1f}%** | {detailed_metrics.exposure_pct:.1f}% | 100.0% | {detailed_metrics.exposure_pct:.1f}% | N/A |",
        f"| **Expectancy / Trade**| **Rs {detailed_metrics.expectancy_inr_per_trade:,.2f}** | N/A | N/A | N/A | N/A |",
        "",
        "### Multiple Testing & Statistical Significance",
        f"- **Random Baseline Percentile Rank**: **{random_benchmark.get('strategy_percentile_rank', 0.0):.1f}%** (Must be >= 95.0% for Class A)",
        f"- **Total Research Trials Evaluated ($K$)**: `{variant_count}` (All models x instruments x gate variants)",
        f"- **Expected Maximum Sharpe under Null ($E[\\max SR]$)**: **{dsr_details.get('expected_max_sr', 0.0):.2f}**",
        f"- **Deflated Sharpe Ratio (DSR) p-value**: **{dsr_pvalue:.4f}** ({'p < 0.10: Significant' if dsr_pvalue < 0.10 else 'p >= 0.10: Inconclusive under multiple testing'})",
        f"- **Bootstrap 95% CI on Sharpe Difference (Strategy - B&H)**: **[{bootstrap_diff_ci.get('ci_lower', 0.0):.2f}, {bootstrap_diff_ci.get('ci_upper', 0.0):.2f}]** "
        f"({'Excludes zero' if bootstrap_diff_ci and bootstrap_diff_ci.get('excludes_zero', False) else 'Includes zero - cannot reject B&H equivalence'})",
        f"- **Walk-Forward Positive Years**: **{pos_years}/{total_years} ({positive_years_pct:.1f}%)**",
        "",
        "---",
        "",
        "## 3. Trade Gating Filter Removal Breakdown",
        "",
        "| Gate / Filter | Trades Dropped | Description & Threshold |",
        "| :--- | :---: | :--- |",
        f"| **Raw Signals Emitted** | **{result.gate_audit.total_raw_signals}** | Total BUY ({result.gate_audit.raw_buy_signals}) and SELL ({result.gate_audit.raw_sell_signals}) raw signals |",
        f"| **Data Gap Gate** | **{result.gate_audit.dropped_by_gap}** | Signals falling on or within 3 bars of `DATA_MISSING_IN_FEED` |",
        f"| **Confidence Gate** | **{result.gate_audit.dropped_by_confidence}** | Signals below calibrated probability threshold |",
        f"| **Regime Filter Gate** | **{result.gate_audit.dropped_by_regime}** | Signals occurring in `UNKNOWN` or `HIGH_VOL` regime |",
        f"| **VIX Percentile Gate** | **{result.gate_audit.dropped_by_vix}** | Signals where VIX percentile > 85% or < 5% |",
        f"| **Expiry Proximity Gate**| **{result.gate_audit.dropped_by_expiry}** | Signals on contract expiry days |",
        f"| **Final Executed Signals** | **{result.gate_audit.final_executed_signals}** | Final approved trades ({result.gate_audit.final_executed_buys} BUY, {result.gate_audit.final_executed_sells} SELL) |",
        f"| **Total Filter Removal Rate** | **{result.gate_audit.removal_rate_pct:.1f}%** | Overall fraction of raw signals filtered out |",
        "",
        "---",
        "",
        "## 4. Multi-Dimensional Performance Breakdowns",
        "",
        "### A. Annual Breakdown (Walk-Forward Test Folds 2015–2024)",
        "| Year | Trades | Win Rate | Net P&L (INR) | Return % | Sharpe Ratio |",
        "| :---: | :---: | :---: | :---: | :---: | :---: |",
    ]

    for yr, data in sorted(detailed_metrics.by_year.items()):
        lines.append(f"| {yr} | {data['trades']} | {data['win_rate_pct']:.1f}% | Rs {data['net_pnl_inr']:,.2f} | {data.get('return_pct', 0.0):.2f}% | {data.get('sharpe_ratio', 0.0):.2f} |")

    lines.extend([
        "",
        "### B. Regime Breakdown",
        "| Market Regime | Trades | Win Rate | Net P&L (INR) | Sharpe Ratio |",
        "| :--- | :---: | :---: | :---: | :---: |",
    ])
    for reg, data in detailed_metrics.by_regime.items():
        lines.append(f"| {reg} | {data['trades']} | {data['win_rate_pct']:.1f}% | Rs {data['net_pnl_inr']:,.2f} | {data.get('sharpe_ratio', 0.0):.2f} |")

    lines.extend([
        "",
        "### C. Direction Breakdown (Long vs Short)",
        "| Direction | Trades | Win Rate | Net P&L (INR) | Sharpe Ratio |",
        "| :--- | :---: | :---: | :---: | :---: |",
        f"| **BUY (Long)** | {detailed_metrics.by_direction.get('BUY', {}).get('trades', 0)} | {detailed_metrics.by_direction.get('BUY', {}).get('win_rate_pct', 0.0):.1f}% | Rs {detailed_metrics.by_direction.get('BUY', {}).get('net_pnl_inr', 0.0):,.2f} | {detailed_metrics.by_direction.get('BUY', {}).get('sharpe_ratio', 0.0):.2f} |",
        f"| **SELL (Short)** | {detailed_metrics.by_direction.get('SELL', {}).get('trades', 0)} | {detailed_metrics.by_direction.get('SELL', {}).get('win_rate_pct', 0.0):.1f}% | Rs {detailed_metrics.by_direction.get('SELL', {}).get('net_pnl_inr', 0.0):,.2f} | {detailed_metrics.by_direction.get('SELL', {}).get('sharpe_ratio', 0.0):.2f} |",
        "",
        "---",
        "",
        "## 5. Walk-Forward Fold Progression",
        "| Fold | Test Year | Test Window | Trades | Win Rate | Net P&L | Final Equity | Sharpe |",
        "| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |",
    ])

    for fld in result.fold_summaries:
        lines.append(
            f"| {fld['fold_id']} | {fld['test_year']} | {fld['test_range']} | {fld['trades']} | {fld['win_rate_pct']:.1f}% | Rs {fld['net_pnl_inr']:,.2f} | Rs {fld['final_equity']:,.2f} | {fld['sharpe_ratio']:.2f} |"
        )

    lines.extend([
        "",
        "---",
        "*(Report generated by Antigravity Quantitative Research Platform - Part 2)*",
    ])

    report_content = "\n".join(lines)
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            f.write(report_content)

    return report_content

    for fld in result.fold_summaries:
        lines.append(
            f"| {fld['fold_id']} | {fld['test_year']} | {fld['test_range']} | {fld['trades']} | {fld['win_rate_pct']:.1f}% | Rs {fld['net_pnl_inr']:,.2f} | Rs {fld['final_equity']:,.2f} | {fld['sharpe_ratio']:.2f} |"
        )

    lines.extend([
        "",
        "---",
        "*(Report generated by Antigravity Quantitative Research Platform - Part 2)*",
    ])

    report_content = "\n".join(lines)
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            f.write(report_content)

    return report_content
