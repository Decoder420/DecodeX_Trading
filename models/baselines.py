"""Rule-based baseline signal models: Trend Following, Mean Reversion, Breakout, and Regime-Switching."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional
import numpy as np
import pandas as pd

from models.base import BaseSignalModel, SignalDirection

logger = logging.getLogger(__name__)


class TrendFollowingModel(BaseSignalModel):
    """Trend-following baseline: EMA 21/50 crossover confirmed by ADX > 25."""

    def __init__(self, params: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(name="Baseline_Trend_EMA_ADX", params=params)
        self.fast_ema_col = self.params.get("fast_ema", "ema_21")
        self.slow_ema_col = self.params.get("slow_ema", "ema_50")
        self.adx_col = self.params.get("adx_col", "adx_14")
        self.adx_threshold = float(self.params.get("adx_threshold", 25.0))
        self.atr_col = self.params.get("atr_col", "atr_14")
        self.pt_mult = float(self.params.get("pt_mult", 2.5))
        self.sl_mult = float(self.params.get("sl_mult", 1.5))

    def fit(self, train_df: pd.DataFrame, **kwargs: Any) -> TrendFollowingModel:
        self.is_fitted = True
        return self

    def predict_signals(self, df: pd.DataFrame, **kwargs: Any) -> pd.DataFrame:
        n = len(df)
        directions = [SignalDirection.NO_TRADE.value] * n
        confidences = [0.0] * n
        stops = [0.0] * n
        targets = [0.0] * n
        reasons = ["NO_CONDITION_MET"] * n
        margins = [0.0] * n

        close = df["close"].values
        atr = df[self.atr_col].values if self.atr_col in df.columns else np.full(n, 100.0)
        fast_ema = df[self.fast_ema_col].values if self.fast_ema_col in df.columns else close
        slow_ema = df[self.slow_ema_col].values if self.slow_ema_col in df.columns else close
        adx = df[self.adx_col].values if self.adx_col in df.columns else np.full(n, 30.0)

        for i in range(1, n):
            c_val = close[i]
            atr_val = atr[i] if not np.isnan(atr[i]) and atr[i] > 0 else 50.0

            # Crossover condition
            prev_bullish = fast_ema[i - 1] > slow_ema[i - 1]
            curr_bullish = fast_ema[i] > slow_ema[i]
            prev_bearish = fast_ema[i - 1] < slow_ema[i - 1]
            curr_bearish = fast_ema[i] < slow_ema[i]

            trend_strong = adx[i] >= self.adx_threshold if not np.isnan(adx[i]) else False

            if curr_bullish and not prev_bullish and trend_strong:
                directions[i] = SignalDirection.BUY.value
                confidences[i] = min(0.95, 0.55 + (adx[i] - self.adx_threshold) / 100.0)
                stops[i] = c_val - (self.sl_mult * atr_val)
                targets[i] = c_val + (self.pt_mult * atr_val)
                reasons[i] = f"EMA_CROSS_BULLISH(fast={fast_ema[i]:.1f}>slow={slow_ema[i]:.1f})+ADX({adx[i]:.1f}>={self.adx_threshold})"
                margins[i] = confidences[i] - 0.33
            elif curr_bearish and not prev_bearish and trend_strong:
                directions[i] = SignalDirection.SELL.value
                confidences[i] = min(0.95, 0.55 + (adx[i] - self.adx_threshold) / 100.0)
                stops[i] = c_val + (self.sl_mult * atr_val)
                targets[i] = c_val - (self.pt_mult * atr_val)
                reasons[i] = f"EMA_CROSS_BEARISH(fast={fast_ema[i]:.1f}<slow={slow_ema[i]:.1f})+ADX({adx[i]:.1f}>={self.adx_threshold})"
                margins[i] = confidences[i] - 0.33

        return pd.DataFrame(
            {
                "direction": directions,
                "confidence": confidences,
                "suggested_entry": close,
                "stop_loss": stops,
                "take_profit": targets,
                "reasons": reasons,
                "margin": margins,
            },
            index=df.index,
        )


class MeanReversionModel(BaseSignalModel):
    """Mean reversion baseline: 20-bar Returns Z-score and Bollinger %B exhaustion."""

    def __init__(self, params: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(name="Baseline_Mean_Reversion", params=params)
        self.zscore_col = self.params.get("zscore_col", "returns_zscore_20")
        self.pct_b_col = self.params.get("pct_b_col", "bb_pct_b_20")
        self.bb_mid_col = self.params.get("bb_mid_col", "bb_mid_20")
        self.atr_col = self.params.get("atr_col", "atr_14")
        self.z_threshold = float(self.params.get("z_threshold", 1.25))
        self.oversold_pct_b = float(self.params.get("oversold_pct_b", 0.20))
        self.overbought_pct_b = float(self.params.get("overbought_pct_b", 0.80))
        self.sl_mult = float(self.params.get("sl_mult", 1.2))

    def fit(self, train_df: pd.DataFrame, **kwargs: Any) -> MeanReversionModel:
        # Calibrate entry threshold adaptively on the training fold if available
        if self.zscore_col in train_df.columns:
            valid_z = train_df[self.zscore_col].dropna().values
            if len(valid_z) > 100:
                self.z_threshold = float(np.percentile(np.abs(valid_z), 75.0))
                self.z_threshold = float(np.clip(self.z_threshold, 1.0, 1.75))
        self.is_fitted = True
        return self

    def predict_signals(self, df: pd.DataFrame, **kwargs: Any) -> pd.DataFrame:
        n = len(df)
        directions = [SignalDirection.NO_TRADE.value] * n
        confidences = [0.0] * n
        stops = [0.0] * n
        targets = [0.0] * n
        reasons = ["NO_CONDITION_MET"] * n
        margins = [0.0] * n

        close = df["close"].values
        atr = df[self.atr_col].values if self.atr_col in df.columns else np.full(n, 100.0)
        zscore = df[self.zscore_col].values if self.zscore_col in df.columns else np.zeros(n)
        pct_b = df[self.pct_b_col].values if self.pct_b_col in df.columns else np.full(n, 0.5)
        bb_mid = df[self.bb_mid_col].values if self.bb_mid_col in df.columns else close

        for i in range(n):
            c_val = close[i]
            atr_val = atr[i] if not np.isnan(atr[i]) and atr[i] > 0 else 50.0
            mid_val = bb_mid[i] if not np.isnan(bb_mid[i]) else c_val

            z_val = zscore[i] if not np.isnan(zscore[i]) else 0.0
            b_val = pct_b[i] if not np.isnan(pct_b[i]) else 0.5

            if z_val <= -self.z_threshold and b_val <= self.oversold_pct_b:
                # Oversold -> BUY toward mean
                directions[i] = SignalDirection.BUY.value
                conf = min(0.90, 0.55 + (abs(z_val) / 5.0) * 0.20)
                confidences[i] = conf
                stops[i] = c_val - (self.sl_mult * atr_val)
                targets[i] = max(mid_val, c_val + (1.5 * atr_val))
                reasons[i] = f"OVERSOLD(z={z_val:.2f}<-{self.z_threshold:.2f},pct_b={b_val:.2f}<={self.oversold_pct_b})"
                margins[i] = conf - 0.33
            elif z_val >= self.z_threshold and b_val >= self.overbought_pct_b:
                # Overbought -> SELL toward mean
                directions[i] = SignalDirection.SELL.value
                conf = min(0.90, 0.55 + (abs(z_val) / 5.0) * 0.20)
                confidences[i] = conf
                stops[i] = c_val + (self.sl_mult * atr_val)
                targets[i] = min(mid_val, c_val - (1.5 * atr_val))
                reasons[i] = f"OVERBOUGHT(z={z_val:.2f}>{self.z_threshold:.2f},pct_b={b_val:.2f}>={self.overbought_pct_b})"
                margins[i] = conf - 0.33

        return pd.DataFrame(
            {
                "direction": directions,
                "confidence": confidences,
                "suggested_entry": close,
                "stop_loss": stops,
                "take_profit": targets,
                "reasons": reasons,
                "margin": margins,
            },
            index=df.index,
        )


class BreakoutModel(BaseSignalModel):
    """Breakout baseline: 20-bar Donchian channel breakout with trailing ATR stop."""

    def __init__(self, params: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(name="Baseline_Breakout_Donchian", params=params)
        self.window = int(self.params.get("window", 20))
        self.atr_col = self.params.get("atr_col", "atr_14")
        self.pt_mult = float(self.params.get("pt_mult", 3.0))
        self.sl_mult = float(self.params.get("sl_mult", 2.0))

    def fit(self, train_df: pd.DataFrame, **kwargs: Any) -> BreakoutModel:
        self.is_fitted = True
        return self

    def predict_signals(self, df: pd.DataFrame, **kwargs: Any) -> pd.DataFrame:
        n = len(df)
        directions = [SignalDirection.NO_TRADE.value] * n
        confidences = [0.0] * n
        stops = [0.0] * n
        targets = [0.0] * n
        reasons = ["NO_CONDITION_MET"] * n
        margins = [0.0] * n

        close = df["close"].values
        high = df["high"].values
        low = df["low"].values
        atr = df[self.atr_col].values if self.atr_col in df.columns else np.full(n, 100.0)

        # Causal rolling 20-bar max and min (shifted by 1 so current bar is not in reference)
        series_high = pd.Series(high)
        series_low = pd.Series(low)
        donchian_high = series_high.rolling(self.window).max().shift(1).values
        donchian_low = series_low.rolling(self.window).min().shift(1).values

        for i in range(self.window + 1, n):
            c_val = close[i]
            atr_val = atr[i] if not np.isnan(atr[i]) and atr[i] > 0 else 50.0

            if c_val > donchian_high[i] and not np.isnan(donchian_high[i]):
                directions[i] = SignalDirection.BUY.value
                confidences[i] = 0.60
                stops[i] = c_val - (self.sl_mult * atr_val)
                targets[i] = c_val + (self.pt_mult * atr_val)
                reasons[i] = f"DONCHIAN_BREAKOUT_UP(close={c_val:.1f}>high_{self.window}={donchian_high[i]:.1f})"
                margins[i] = 0.27
            elif c_val < donchian_low[i] and not np.isnan(donchian_low[i]):
                directions[i] = SignalDirection.SELL.value
                confidences[i] = 0.60
                stops[i] = c_val + (self.sl_mult * atr_val)
                targets[i] = c_val - (self.pt_mult * atr_val)
                reasons[i] = f"DONCHIAN_BREAKOUT_DOWN(close={c_val:.1f}<low_{self.window}={donchian_low[i]:.1f})"
                margins[i] = 0.27

        return pd.DataFrame(
            {
                "direction": directions,
                "confidence": confidences,
                "suggested_entry": close,
                "stop_loss": stops,
                "take_profit": targets,
                "reasons": reasons,
                "margin": margins,
            },
            index=df.index,
        )


class RegimeSwitchingBaselineModel(BaseSignalModel):
    """Regime-switching combination: selects Trend in TRENDING, Mean-Reversion in RANGING, NO_TRADE otherwise."""

    def __init__(self, params: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(name="Baseline_Regime_Switching", params=params)
        self.trend_model = TrendFollowingModel(params)
        self.mr_model = MeanReversionModel(params)
        self.regime_col = self.params.get("regime_col", "regime_label")

    def fit(self, train_df: pd.DataFrame, **kwargs: Any) -> RegimeSwitchingBaselineModel:
        self.trend_model.fit(train_df)
        self.mr_model.fit(train_df)
        self.is_fitted = True
        return self

    def predict_signals(self, df: pd.DataFrame, **kwargs: Any) -> pd.DataFrame:
        trend_signals = self.trend_model.predict_signals(df)
        mr_signals = self.mr_model.predict_signals(df)

        n = len(df)
        regimes = df[self.regime_col].values if self.regime_col in df.columns else np.full(n, "UNKNOWN")

        directions = [SignalDirection.NO_TRADE.value] * n
        confidences = [0.0] * n
        stops = [0.0] * n
        targets = [0.0] * n
        reasons = ["REGIME_INACTIVE_OR_HIGH_VOL"] * n
        margins = [0.0] * n

        for i in range(n):
            reg = str(regimes[i]).upper()
            if reg == "TRENDING":
                directions[i] = trend_signals["direction"].iloc[i]
                confidences[i] = trend_signals["confidence"].iloc[i]
                stops[i] = trend_signals["stop_loss"].iloc[i]
                targets[i] = trend_signals["take_profit"].iloc[i]
                reasons[i] = f"[REGIME_TRENDING] -> {trend_signals['reasons'].iloc[i]}"
                margins[i] = trend_signals["margin"].iloc[i]
            elif reg == "RANGING":
                directions[i] = mr_signals["direction"].iloc[i]
                confidences[i] = mr_signals["confidence"].iloc[i]
                stops[i] = mr_signals["stop_loss"].iloc[i]
                targets[i] = mr_signals["take_profit"].iloc[i]
                reasons[i] = f"[REGIME_RANGING] -> {mr_signals['reasons'].iloc[i]}"
                margins[i] = mr_signals["margin"].iloc[i]
            else:
                directions[i] = SignalDirection.NO_TRADE.value
                confidences[i] = 0.0
                stops[i] = 0.0
                targets[i] = 0.0
                reasons[i] = f"REGIME_FILTER_GATE({reg})"
                margins[i] = 0.0

        return pd.DataFrame(
            {
                "direction": directions,
                "confidence": confidences,
                "suggested_entry": df["close"].values,
                "stop_loss": stops,
                "take_profit": targets,
                "reasons": reasons,
                "margin": margins,
            },
            index=df.index,
        )
