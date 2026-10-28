"""Master feature engineering pipeline combining trend, momentum, volatility, mean reversion, calendar, and regime."""

from __future__ import annotations

import logging
from typing import Optional
import pandas as pd

from config.loader import ConfigManager, config_manager
from features.calendar import compute_calendar_features
from features.mean_reversion import (
    compute_distance_from_ma_atr,
    compute_rolling_adf,
    compute_rolling_hurst,
)
from features.momentum import (
    compute_macd,
    compute_returns_zscore,
    compute_roc,
    compute_rsi,
    compute_stochastic,
)
from features.regime import compute_hmm_regime, compute_rolling_stats_regime
from features.trend import (
    compute_adx,
    compute_all_emas,
    compute_hh_hl_structure,
    compute_supertrend,
    compute_vwap,
)
from features.volatility import (
    compute_atr,
    compute_bollinger_bands,
    compute_garch_forecast,
    compute_realized_volatility,
    compute_vix_features,
)

logger = logging.getLogger(__name__)


class FeaturePipeline:
    """Configurable pipeline that computes all feature sets without lookahead bias."""

    def __init__(self, cfg: Optional[ConfigManager] = None) -> None:
        self.cfg = cfg or config_manager

    def compute_all_features(
        self,
        df: pd.DataFrame,
        instrument: str,
        vix_df: Optional[pd.DataFrame] = None,
        include_garch: bool = True,
        include_regime: bool = True,
        include_mean_reversion: bool = True,
    ) -> pd.DataFrame:
        """Compute full feature matrix for an instrument dataset.

        Args:
            df: Cleaned OHLCV DataFrame with standard columns.
            instrument: Instrument symbol key ('NIFTY', 'BANKNIFTY', 'SENSEX').
            vix_df: Optional India VIX DataFrame for volatility rank features.
            include_garch: Flag to compute GARCH(1,1) one-step forecast.
            include_regime: Flag to compute HMM or rolling stats regime.
            include_mean_reversion: Flag to compute Hurst exponent and ADF p-value.

        Returns:
            DataFrame containing raw OHLCV and all generated technical features.
        """
        if df.empty:
            return df

        out = df.copy()
        high = out["high"]
        low = out["low"]
        close = out["close"]

        # --- 1. Trend Features ---
        ema_periods = self.cfg.get("features.trend.ema_periods", [9, 21, 50, 200])
        emas = compute_all_emas(close, periods=ema_periods)
        out = pd.concat([out, emas], axis=1)

        adx_period = self.cfg.get("features.trend.adx_period", 14)
        adx_df = compute_adx(high, low, close, period=adx_period)
        out = pd.concat([out, adx_df], axis=1)

        st_period = self.cfg.get("features.trend.supertrend.period", 10)
        st_mult = self.cfg.get("features.trend.supertrend.multiplier", 3.0)
        st_df = compute_supertrend(high, low, close, period=st_period, multiplier=st_mult)
        out = pd.concat([out, st_df], axis=1)

        vwap_df = compute_vwap(out)
        out = pd.concat([out, vwap_df], axis=1)

        hh_hl_window = self.cfg.get("features.trend.hh_hl_window", 5)
        hh_hl_df = compute_hh_hl_structure(high, low, window=hh_hl_window)
        out = pd.concat([out, hh_hl_df], axis=1)

        # --- 2. Momentum Features ---
        rsi_period = self.cfg.get("features.momentum.rsi_period", 14)
        out[f"rsi_{rsi_period}"] = compute_rsi(close, period=rsi_period)

        macd_params = self.cfg.get("features.momentum.macd", {"fast": 12, "slow": 26, "signal": 9})
        macd_df = compute_macd(
            close,
            fast=macd_params.get("fast", 12),
            slow=macd_params.get("slow", 26),
            signal=macd_params.get("signal", 9),
        )
        out = pd.concat([out, macd_df], axis=1)

        roc_period = self.cfg.get("features.momentum.roc_period", 10)
        out[f"roc_{roc_period}"] = compute_roc(close, period=roc_period)

        stoch_params = self.cfg.get("features.momentum.stochastic", {"k_period": 14, "d_period": 3})
        stoch_df = compute_stochastic(
            high,
            low,
            close,
            k_period=stoch_params.get("k_period", 14),
            d_period=stoch_params.get("d_period", 3),
        )
        out = pd.concat([out, stoch_df], axis=1)

        zscore_window = self.cfg.get("features.momentum.returns_zscore_window", 20)
        out[f"returns_zscore_{zscore_window}"] = compute_returns_zscore(close, window=zscore_window)

        # --- 3. Volatility Features ---
        atr_period = self.cfg.get("features.volatility.atr_period", 14)
        out[f"atr_{atr_period}"] = compute_atr(high, low, close, period=atr_period)

        bb_params = self.cfg.get("features.volatility.bollinger", {"period": 20, "num_std": 2.0})
        bb_df = compute_bollinger_bands(
            close,
            period=bb_params.get("period", 20),
            num_std=bb_params.get("num_std", 2.0),
        )
        out = pd.concat([out, bb_df], axis=1)

        realized_vol_window = self.cfg.get("features.volatility.realized_vol_window", 20)
        out[f"realized_vol_{realized_vol_window}"] = compute_realized_volatility(
            close, window=realized_vol_window
        )

        if include_garch:
            garch_cfg = self.cfg.get("features.volatility.garch", {})
            garch_series = compute_garch_forecast(
                close,
                fit_window=garch_cfg.get("fit_window", 252),
                p=garch_cfg.get("p", 1),
                q=garch_cfg.get("q", 1),
                refit_step=garch_cfg.get("refit_step", 10),
            )
            out = pd.concat([out, garch_series], axis=1)

        vix_pctile_win = self.cfg.get("features.volatility.vix_percentile_window", 252)
        vix_feat = compute_vix_features(vix_df, out["timestamp"], percentile_window=vix_pctile_win)
        out = pd.concat([out, vix_feat], axis=1)

        # --- 4. Mean Reversion Features ---
        dist_ma_period = self.cfg.get("features.mean_reversion.distance_ma_period", 20)
        out[f"dist_ma_{dist_ma_period}_atr"] = compute_distance_from_ma_atr(
            high, low, close, ma_period=dist_ma_period, atr_period=atr_period
        )

        if include_mean_reversion:
            hurst_win = self.cfg.get("features.mean_reversion.hurst_window", 100)
            out[f"hurst_{hurst_win}"] = compute_rolling_hurst(close, window=hurst_win)

            adf_win = self.cfg.get("features.mean_reversion.adf_window", 60)
            out[f"adf_pvalue_{adf_win}"] = compute_rolling_adf(close, window=adf_win)

        # --- 5. Calendar Features ---
        calendar_df = compute_calendar_features(out, instrument=instrument, cfg=self.cfg)
        out = pd.concat([out, calendar_df], axis=1)

        # --- 6. Regime Features ---
        if include_regime:
            regime_method = self.cfg.get("features.regime.method", "hmm").lower()
            if regime_method == "hmm":
                regime_df = compute_hmm_regime(
                    close,
                    n_states=self.cfg.get("features.regime.hmm_states", 3),
                    fit_window=self.cfg.get("features.regime.fit_window", 252),
                    refit_step=self.cfg.get("features.regime.refit_step", 20),
                    random_state=self.cfg.get("project.random_seed", 42),
                )
            else:
                regime_df = compute_rolling_stats_regime(
                    high,
                    low,
                    close,
                    vol_window=self.cfg.get("features.regime.rolling_vol_window", 20),
                    adx_threshold=self.cfg.get("features.regime.rolling_adx_threshold", 25.0),
                )
            out = pd.concat([out, regime_df], axis=1)

        return out

    @staticmethod
    def get_feature_warmup_report(df_features: pd.DataFrame) -> pd.DataFrame:
        """Inspect a feature matrix and report leading NaN warm-up length for each column.

        Returns:
            pd.DataFrame with ['feature', 'leading_nans', 'total_nans', 'pct_nans', 'status']
            sorted by leading_nans descending.
        """
        records = []
        n_total = len(df_features)

        for col in df_features.columns:
            series = df_features[col]
            # Calculate leading consecutive NaNs
            is_nan = series.isna().values
            leading_nans = 0
            for val in is_nan:
                if val:
                    leading_nans += 1
                else:
                    break

            total_nans = int(series.isna().sum())
            pct_nans = (total_nans / n_total * 100.0) if n_total > 0 else 0.0

            records.append(
                {
                    "feature": col,
                    "leading_nans": leading_nans,
                    "total_nans": total_nans,
                    "pct_nans": round(pct_nans, 2),
                    "status": "READY" if leading_nans == 0 else f"WARMUP_{leading_nans}",
                }
            )

        report_df = pd.DataFrame(records).sort_values(
            ["leading_nans", "total_nans"], ascending=[False, False]
        ).reset_index(drop=True)
        return report_df
