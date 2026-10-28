"""Market regime classification using strictly causal Hidden Markov Models (HMM) and rolling statistics."""

from __future__ import annotations

import logging
from typing import Dict, Optional, Tuple
from hmmlearn import hmm
import numpy as np
import pandas as pd

from features.trend import compute_adx

logger = logging.getLogger(__name__)


def compute_hmm_forward_filtered_probabilities(
    model: hmm.GaussianHMM,
    X: np.ndarray,
) -> np.ndarray:
    """Calculate filtered forward state probabilities P(S_t | y_1 ... y_t) without lookahead backward pass."""
    framelogprob = model._compute_log_likelihood(X)
    log_startprob = np.log(np.maximum(model.startprob_, 1e-12))
    log_transmat = np.log(np.maximum(model.transmat_, 1e-12))

    n_samples, n_components = framelogprob.shape
    fwd_lattice = np.zeros((n_samples, n_components))

    # Initial step t=0
    fwd_lattice[0] = log_startprob + framelogprob[0]
    fwd_lattice[0] -= np.max(fwd_lattice[0])

    # Forward recurrence: alpha_t(j) = sum_i alpha_{t-1}(i) * A_{i,j} * B_j(y_t)
    for t in range(1, n_samples):
        for j in range(n_components):
            fwd_lattice[t, j] = np.logaddexp.reduce(fwd_lattice[t - 1] + log_transmat[:, j]) + framelogprob[t, j]
        fwd_lattice[t] -= np.max(fwd_lattice[t])  # Numerical stability

    probs = np.exp(fwd_lattice)
    probs /= probs.sum(axis=1, keepdims=True)
    return probs


def map_hmm_states(model: hmm.GaussianHMM) -> Dict[str, int]:
    """Map HMM states to economic regimes based on fitted volatility and returns.

    Rule:
    - State with highest fitted variance is mapped to 'HIGH_VOL'.
    - Between remaining two states, state with higher absolute return/trend is 'TRENDING'.
    - Remaining state is 'RANGING'.
    Never assumes arbitrary state indices (0, 1, 2).
    """
    means = model.means_.flatten()
    if model.covariance_type == "diag":
        variances = model.covars_.flatten()
    elif model.covariance_type == "full":
        variances = np.array([model.covars_[i, 0, 0] for i in range(model.n_components)])
    else:
        variances = model.covars_.flatten()

    high_vol_state = int(np.argmax(variances))
    other_states = [s for s in range(model.n_components) if s != high_vol_state]

    # Compare return magnitudes or directional trend in remaining states
    s1, s2 = other_states[0], other_states[1]
    score_s1 = abs(means[s1])
    score_s2 = abs(means[s2])

    if score_s1 >= score_s2:
        trending_state = s1
        ranging_state = s2
    else:
        trending_state = s2
        ranging_state = s1

    return {
        "HIGH_VOL": high_vol_state,
        "TRENDING": trending_state,
        "RANGING": ranging_state,
    }


def compute_hmm_regime(
    close: pd.Series,
    n_states: int = 3,
    fit_window: int = 252,
    refit_step: int = 20,
    random_state: int = 42,
) -> pd.DataFrame:
    """Classify regime using rolling window Gaussian HMM and filtered forward probabilities.

    Guarantees no lookahead bias by fitting strictly on past window data and using forward variables.
    """
    returns = np.log(close / close.shift(1)).fillna(0.0).values
    n = len(returns)

    # Initialize to UNKNOWN prior to HMM activation at fit_window
    regime_labels = pd.Series("UNKNOWN", index=close.index, dtype=str)
    prob_trending = pd.Series(np.nan, index=close.index, dtype=float)
    prob_ranging = pd.Series(np.nan, index=close.index, dtype=float)
    prob_high_vol = pd.Series(np.nan, index=close.index, dtype=float)

    if n < fit_window:
        logger.warning("Dataset length (%d) < HMM fit_window (%d). Returning UNKNOWN regimes.", n, fit_window)
        return pd.DataFrame(
            {
                "regime_label": regime_labels,
                "prob_trending": prob_trending,
                "prob_ranging": prob_ranging,
                "prob_high_vol": prob_high_vol,
            },
            index=close.index,
        )

    cached_model = None
    state_map: Dict[str, int] = {}
    last_fit_idx = -1

    for i in range(fit_window, n):
        # Rolling window slice: strictly causal [i - fit_window + 1 : i + 1]
        if cached_model is None or (i - last_fit_idx) >= refit_step:
            sub_ret = returns[i - fit_window + 1 : i + 1].reshape(-1, 1)
            try:
                model = hmm.GaussianHMM(
                    n_components=n_states,
                    covariance_type="diag",
                    n_iter=50,
                    random_state=random_state,
                    tol=1e-3,
                )
                model.fit(sub_ret)
                cached_model = model
                state_map = map_hmm_states(model)
                last_fit_idx = i
            except Exception as e:
                logger.debug("HMM fit failed at index %d: %s", i, e)
                continue

        if cached_model is not None:
            # Forward pass on window up to i
            sub_ret = returns[i - fit_window + 1 : i + 1].reshape(-1, 1)
            probs = compute_hmm_forward_filtered_probabilities(cached_model, sub_ret)
            curr_probs = probs[-1]  # At time t = i

            p_trend = float(curr_probs[state_map["TRENDING"]])
            p_range = float(curr_probs[state_map["RANGING"]])
            p_hvol = float(curr_probs[state_map["HIGH_VOL"]])

            prob_trending.iloc[i] = p_trend
            prob_ranging.iloc[i] = p_range
            prob_high_vol.iloc[i] = p_hvol

            max_p = max(p_trend, p_range, p_hvol)
            if max_p == p_hvol:
                regime_labels.iloc[i] = "HIGH_VOL"
            elif max_p == p_trend:
                regime_labels.iloc[i] = "TRENDING"
            else:
                regime_labels.iloc[i] = "RANGING"

    return pd.DataFrame(
        {
            "regime_label": regime_labels,
            "prob_trending": prob_trending,
            "prob_ranging": prob_ranging,
            "prob_high_vol": prob_high_vol,
        },
        index=close.index,
    )


def compute_rolling_stats_regime(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    vol_window: int = 20,
    adx_threshold: float = 25.0,
) -> pd.DataFrame:
    """Classify regime using rolling realized volatility and ADX statistics."""
    adx_df = compute_adx(high, low, close, period=14)
    adx = adx_df["adx_14"]

    log_ret = np.log(close / close.shift(1))
    rolling_vol = log_ret.rolling(window=vol_window, min_periods=vol_window).std()
    vol_threshold = rolling_vol.rolling(window=100, min_periods=40).quantile(0.80)

    regimes = pd.Series("UNKNOWN", index=close.index)
    valid_mask = (~adx.isna()) & (~rolling_vol.isna()) & (~vol_threshold.isna())

    # High Vol regime
    hvol_mask = valid_mask & (rolling_vol > vol_threshold)
    # Trending regime
    trend_mask = valid_mask & (~hvol_mask) & (adx > adx_threshold)
    # Ranging regime
    range_mask = valid_mask & (~hvol_mask) & (~trend_mask)

    regimes.loc[hvol_mask] = "HIGH_VOL"
    regimes.loc[trend_mask] = "TRENDING"
    regimes.loc[range_mask] = "RANGING"

    return pd.DataFrame(
        {
            "regime_label": regimes,
            "is_trending": (regimes == "TRENDING").astype(int),
            "is_ranging": (regimes == "RANGING").astype(int),
            "is_high_vol": (regimes == "HIGH_VOL").astype(int),
        },
        index=close.index,
    )
