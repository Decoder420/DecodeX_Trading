"""Statistical robustness, Monte Carlo simulations, Deflated Sharpe Ratio, and benchmarks."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
from scipy import stats

from backtest.engine import TradeRecord

logger = logging.getLogger(__name__)


def compute_deflated_sharpe_ratio(
    estimated_sharpe: float,
    num_trials: int,
    var_sharpe: Optional[float] = None,
    trial_sharpes: Optional[List[float]] = None,
    sample_length_years: float = 10.0,
    skew: float = 0.0,
    kurtosis: float = 3.0,
) -> Dict[str, float]:
    """Calculate the Deflated Sharpe Ratio (Bailey & López de Prado, 2014) accounting for multiple testing.

    Adjusts for selection bias under multiple trials:
    - Expected Maximum Sharpe under null: E[max_K] ~ sqrt(V) * ((1-gamma)*Phi^-1(1 - 1/K) + gamma*Phi^-1(1 - 1/(K*e)))
    - Annualized standard error of Sharpe ratio over Y years:
      sigma(SR_ann) = sqrt((1 - skew*(SR_ann/sqrt(252)) + (kurtosis - 1)/4 * (SR_ann^2/252)) / sample_length_years)
    - Test statistic z = (SR_est - expected_max_sr) / se_sr
    - DSR probability = Phi(z)
    - DSR p-value = 1.0 - Phi(z) (probability of observing this Sharpe by chance under multiple testing)

    Returns:
        Dict with keys: 'dsr_pvalue', 'dsr_prob', 'expected_max_sr', 'se_sr', 'stat', 'var_sharpe', 'num_trials'.
    """
    if num_trials <= 1:
        p_val = 0.0 if estimated_sharpe > 0 else 1.0
        return {
            "dsr_pvalue": p_val,
            "dsr_prob": 1.0 - p_val,
            "expected_max_sr": 0.0,
            "se_sr": 0.316,
            "stat": 0.0,
            "var_sharpe": 0.0,
            "num_trials": 1,
        }

    # Calculate empirical cross-sectional variance of trials if provided
    if trial_sharpes is not None and len(trial_sharpes) > 1:
        v_trials = float(np.var(trial_sharpes, ddof=1))
        # Ensure positive lower bound to prevent numerical collapse
        v_trials = max(1e-4, v_trials)
    elif var_sharpe is not None:
        v_trials = max(1e-4, var_sharpe)
    else:
        # Default empirical variance across benchmark model trials
        v_trials = 0.133

    # Euler-Mascheroni constant
    em_const = 0.5772156649
    # Expected maximum Sharpe of N independent trials under null hypothesis
    z_n = (1.0 - em_const) * stats.norm.ppf(1.0 - 1.0 / num_trials) + em_const * stats.norm.ppf(1.0 - 1.0 / (num_trials * np.e))
    expected_max_sr = np.sqrt(v_trials) * z_n

    # Annualized standard error of estimated Sharpe over sample_length_years (Opdyke / Merton / Lo)
    y_years = max(1.0, float(sample_length_years))
    # Daily Sharpe equivalent for non-normality terms
    sr_daily = estimated_sharpe / np.sqrt(252.0)
    term = 1.0 - skew * sr_daily + ((kurtosis - 1.0) / 4.0) * (sr_daily ** 2)
    term = max(1e-4, term)
    se_sr = np.sqrt(term / y_years)

    if se_sr <= 0:
        se_sr = 0.316

    stat = (estimated_sharpe - expected_max_sr) / se_sr
    dsr_prob = float(stats.norm.cdf(stat))
    dsr_pvalue = float(1.0 - dsr_prob)

    return {
        "dsr_pvalue": dsr_pvalue,
        "dsr_prob": dsr_prob,
        "expected_max_sr": float(expected_max_sr),
        "se_sr": float(se_sr),
        "stat": float(stat),
        "var_sharpe": float(v_trials),
        "num_trials": int(num_trials),
    }


def bootstrap_sharpe_difference_ci(
    strategy_returns: np.ndarray,
    benchmark_returns: np.ndarray,
    n_bootstraps: int = 1000,
    alpha: float = 0.05,
    random_seed: int = 42,
) -> Dict[str, Any]:
    """Calculate bootstrap 95% confidence interval for the difference:
    Delta = Sharpe(strategy) - Sharpe(benchmark).

    Excludes zero strictly when ci_lower > 0.
    """
    n = min(len(strategy_returns), len(benchmark_returns))
    if n < 10:
        return {
            "mean_diff": 0.0,
            "ci_lower": 0.0,
            "ci_upper": 0.0,
            "excludes_zero": False,
        }

    s_ret = strategy_returns[:n]
    b_ret = benchmark_returns[:n]

    rng = np.random.RandomState(random_seed)
    diffs = np.empty(n_bootstraps)

    for i in range(n_bootstraps):
        idx = rng.choice(n, size=n, replace=True)
        s_samp = s_ret[idx]
        b_samp = b_ret[idx]

        s_std = np.std(s_samp)
        b_std = np.std(b_samp)

        s_sr = (np.mean(s_samp) / s_std * np.sqrt(252)) if s_std > 1e-8 else 0.0
        b_sr = (np.mean(b_samp) / b_std * np.sqrt(252)) if b_std > 1e-8 else 0.0

        diffs[i] = s_sr - b_sr

    mean_diff = float(np.mean(diffs))
    ci_lower = float(np.percentile(diffs, 100.0 * (alpha / 2.0)))
    ci_upper = float(np.percentile(diffs, 100.0 * (1.0 - alpha / 2.0)))
    excludes_zero = bool(ci_lower > 0.0)

    return {
        "mean_diff": mean_diff,
        "ci_lower": ci_lower,
        "ci_upper": ci_upper,
        "excludes_zero": excludes_zero,
    }


def bootstrap_sharpe_ci(
    returns: np.ndarray,
    n_bootstraps: int = 1000,
    alpha: float = 0.05,
    random_seed: int = 42,
) -> Tuple[float, float, float]:
    """Calculate bootstrap 95% confidence interval for annualized Sharpe ratio."""
    if len(returns) < 10:
        return 0.0, 0.0, 0.0

    rng = np.random.RandomState(random_seed)
    n = len(returns)
    boot_sharpes = np.empty(n_bootstraps)

    for i in range(n_bootstraps):
        sample = rng.choice(returns, size=n, replace=True)
        std_val = np.std(sample)
        if std_val > 1e-8:
            boot_sharpes[i] = (np.mean(sample) / std_val) * np.sqrt(252)
        else:
            boot_sharpes[i] = 0.0

    point_est = float(np.mean(boot_sharpes))
    ci_lower = float(np.percentile(boot_sharpes, 100.0 * (alpha / 2.0)))
    ci_upper = float(np.percentile(boot_sharpes, 100.0 * (1.0 - alpha / 2.0)))

    return point_est, ci_lower, ci_upper


def monte_carlo_trade_reshuffle(
    trades: List[TradeRecord],
    starting_capital: float = 1000000.0,
    n_simulations: int = 1000,
    random_seed: int = 42,
) -> Dict[str, Any]:
    """Simulate Monte Carlo permutations of trade sequence to test order-dependence of max drawdown."""
    if not trades:
        return {"simulated_max_dd_median": 0.0, "simulated_max_dd_95th": 0.0}

    pnl_array = np.array([t.net_pnl_inr for t in trades])
    n_trades = len(pnl_array)
    rng = np.random.RandomState(random_seed)

    max_dds = np.empty(n_simulations)
    terminal_equities = np.empty(n_simulations)

    for i in range(n_simulations):
        shuffled_pnl = rng.permutation(pnl_array)
        equity_curve = starting_capital + np.cumsum(shuffled_pnl)
        running_peak = np.maximum.accumulate(equity_curve)
        dds = (running_peak - equity_curve) / running_peak * 100.0
        max_dds[i] = np.max(dds)
        terminal_equities[i] = equity_curve[-1]

    return {
        "simulated_max_dd_median": float(np.median(max_dds)),
        "simulated_max_dd_95th": float(np.percentile(max_dds, 95.0)),
        "simulated_terminal_equity_median": float(np.median(terminal_equities)),
    }


def compute_random_signal_benchmark(
    market_df: pd.DataFrame,
    target_trade_count: int,
    avg_holding_bars: int = 5,
    n_seeds: int = 1000,
    starting_capital: float = 1000000.0,
    strategy_sharpe: float = 0.0,
) -> Dict[str, Any]:
    """Run 1,000 random signal simulations with identical trade frequency and test strategy percentile rank."""
    closes = market_df["close"].values
    n = len(closes)
    if n < 50 or target_trade_count <= 0:
        return {"random_sharpe_mean": 0.0, "strategy_percentile_rank": 50.0}

    # Simulate random entries
    random_sharpes = np.empty(n_seeds)

    for s_idx in range(n_seeds):
        rng = np.random.RandomState(1000 + s_idx)
        # Random entry points
        entry_indices = rng.choice(range(n - avg_holding_bars), size=min(target_trade_count, n // 2), replace=False)
        entry_directions = rng.choice([-1, 1], size=len(entry_indices))

        trade_returns = []
        for e_idx, d_val in zip(entry_indices, entry_directions):
            ret = (closes[e_idx + avg_holding_bars] - closes[e_idx]) / closes[e_idx] * d_val
            trade_returns.append(ret)

        if trade_returns:
            arr = np.array(trade_returns)
            std = np.std(arr)
            random_sharpes[s_idx] = (np.mean(arr) / std * np.sqrt(252 / avg_holding_bars)) if std > 1e-6 else 0.0
        else:
            random_sharpes[s_idx] = 0.0

    percentile_rank = float(np.mean(strategy_sharpe > random_sharpes) * 100.0)
    return {
        "random_sharpe_mean": float(np.mean(random_sharpes)),
        "random_sharpe_std": float(np.std(random_sharpes)),
        "strategy_percentile_rank": percentile_rank,
    }


def compute_buy_and_hold_benchmark(
    market_df: pd.DataFrame,
    starting_capital: float = 1000000.0,
) -> Dict[str, float]:
    """Calculate standard Buy and Hold benchmark performance."""
    closes = market_df["close"].values
    if len(closes) < 2:
        return {"cagr_pct": 0.0, "sharpe_ratio": 0.0, "max_drawdown_pct": 0.0}

    initial_price = closes[0]
    final_price = closes[-1]
    units = starting_capital / initial_price

    eq_curve = closes * units
    running_max = np.maximum.accumulate(eq_curve)
    dds = (running_max - eq_curve) / running_max * 100.0
    max_dd = float(np.max(dds))

    days = (pd.to_datetime(market_df["timestamp"].iloc[-1]) - pd.to_datetime(market_df["timestamp"].iloc[0])).days
    years = max(0.5, days / 365.25)
    cagr = float(((final_price / initial_price) ** (1.0 / years) - 1.0) * 100.0)

    daily_ret = np.diff(closes) / closes[:-1]
    std = np.std(daily_ret)
    sharpe = float((np.mean(daily_ret) / std * np.sqrt(252))) if std > 0 else 0.0

    return {
        "cagr_pct": cagr,
        "sharpe_ratio": sharpe,
        "max_drawdown_pct": max_dd,
        "total_return_pct": float((final_price - initial_price) / initial_price * 100.0),
    }
