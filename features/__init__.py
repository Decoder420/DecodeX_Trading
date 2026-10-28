"""Features package."""

from features.pipeline import FeaturePipeline
from features.trend import (
    compute_ema,
    compute_all_emas,
    compute_adx,
    compute_supertrend,
    compute_vwap,
    compute_hh_hl_structure,
)
from features.momentum import (
    compute_rsi,
    compute_macd,
    compute_roc,
    compute_stochastic,
    compute_returns_zscore,
)
from features.volatility import (
    compute_atr,
    compute_bollinger_bands,
    compute_realized_volatility,
    compute_garch_forecast,
    compute_vix_features,
)
from features.mean_reversion import (
    compute_distance_from_ma_atr,
    calculate_hurst_exponent,
    compute_rolling_hurst,
    compute_rolling_adf,
)
from features.calendar import compute_calendar_features
from features.regime import (
    compute_hmm_regime,
    compute_rolling_stats_regime,
    compute_hmm_forward_filtered_probabilities,
    map_hmm_states,
)

__all__ = [
    "FeaturePipeline",
    "compute_ema",
    "compute_all_emas",
    "compute_adx",
    "compute_supertrend",
    "compute_vwap",
    "compute_hh_hl_structure",
    "compute_rsi",
    "compute_macd",
    "compute_roc",
    "compute_stochastic",
    "compute_returns_zscore",
    "compute_atr",
    "compute_bollinger_bands",
    "compute_realized_volatility",
    "compute_garch_forecast",
    "compute_vix_features",
    "compute_distance_from_ma_atr",
    "calculate_hurst_exponent",
    "compute_rolling_hurst",
    "compute_rolling_adf",
    "compute_calendar_features",
    "compute_hmm_regime",
    "compute_rolling_stats_regime",
    "compute_hmm_forward_filtered_probabilities",
    "map_hmm_states",
]
