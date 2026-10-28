"""Gradient Boosted Tree models using LightGBM with Tree SHAP explainability and chronological calibration."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
import lightgbm as lgb
import numpy as np
import pandas as pd

from models.base import BaseSignalModel, SignalDirection
from models.calibration import MultiClassCalibrator, split_calibration_slice

logger = logging.getLogger(__name__)

EXCLUDED_COLS = {
    "timestamp",
    "updated_at",
    "ts_str",
    "is_outlier",
    "is_gap",
    "vwap",
    "regime_label",
    "market_structure_trend",
    "tb_barrier_hit",
    "tb_label",
    "tb_holding_period",
    "tb_return",
}


class LightGBMDirectionModel(BaseSignalModel):
    """Model 3A: LightGBM classifier predicting next N-bar direction (target_dir_3) with Tree SHAP."""

    def __init__(
        self,
        name: str = "LightGBM_Direction_3B",
        target_col: str = "target_dir_3",
        params: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(name=name, params=params)
        self.target_col = target_col
        self.calibrator = MultiClassCalibrator(method="isotonic")
        self.feature_names: List[str] = []
        self.model: Optional[lgb.LGBMClassifier] = None
        self.atr_col = self.params.get("atr_col", "atr_14")
        self.pt_mult = float(self.params.get("pt_mult", 2.0))
        self.sl_mult = float(self.params.get("sl_mult", 1.5))

    def _select_features(self, df: pd.DataFrame) -> List[str]:
        target_prefixes = ("target_fwd_", "target_dir_")
        numeric_cols = [
            c for c in df.columns
            if c not in EXCLUDED_COLS
            and not c.startswith(target_prefixes)
            and pd.api.types.is_numeric_dtype(df[c])
            and df[c].isna().mean() < 0.30
        ]
        return numeric_cols

    def fit(self, train_df: pd.DataFrame, **kwargs: Any) -> LightGBMDirectionModel:
        train_sub, calib_sub = split_calibration_slice(train_df, calib_pct=0.20, purge_bars=10)
        self.feature_names = self._select_features(train_sub)
        if not self.feature_names:
            raise ValueError("No valid numeric features found for LightGBM fitting.")

        if self.target_col not in train_sub.columns:
            from models.labels import compute_forward_returns
            horizons = [1, 3, 5]
            fwd_df = compute_forward_returns(train_df["close"], horizons=horizons)
            train_sub[self.target_col] = fwd_df[self.target_col].iloc[: len(train_sub)]
            calib_sub[self.target_col] = fwd_df[self.target_col].iloc[-len(calib_sub):].values

        valid_train = train_sub.dropna(subset=self.feature_names + [self.target_col])
        X_train = valid_train[self.feature_names].values
        # Shift classes from {-1, 0, 1} to {0, 1, 2} for LightGBM objective
        y_train_raw = valid_train[self.target_col].values.astype(int)
        y_train = y_train_raw + 1

        self.model = lgb.LGBMClassifier(
            objective="multiclass",
            num_class=3,
            n_estimators=60,
            max_depth=4,
            num_leaves=15,
            learning_rate=0.03,
            min_child_samples=25,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42,
            verbosity=-1,
        )
        self.model.fit(X_train, y_train)

        # Chronological calibration on separate calib slice
        valid_calib = calib_sub.dropna(subset=self.feature_names + [self.target_col])
        if len(valid_calib) >= 20:
            X_calib = valid_calib[self.feature_names].values
            raw_calib_probs = self.model.predict_proba(X_calib)
            y_calib_raw = valid_calib[self.target_col].values.astype(int)
            y_calib = y_calib_raw + 1
            self.calibrator.fit(raw_calib_probs, y_calib)

        self.is_fitted = True
        return self

    def predict_signals(self, df: pd.DataFrame, **kwargs: Any) -> pd.DataFrame:
        n = len(df)
        directions = [SignalDirection.NO_TRADE.value] * n
        confidences = [0.0] * n
        stops = [0.0] * n
        targets = [0.0] * n
        reasons = ["MODEL_NOT_FITTED"] * n
        margins = [0.0] * n

        if not self.is_fitted or self.model is None or not self.feature_names:
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

        close = df["close"].values
        atr = df[self.atr_col].values if self.atr_col in df.columns else np.full(n, 100.0)

        feat_df = df[self.feature_names].copy().fillna(0.0)
        X = feat_df.values
        raw_probs = self.model.predict_proba(X)
        calib_probs = self.calibrator.predict_calibrated(raw_probs)

        # Native Tree SHAP contributions: shape (N, num_classes * (F + 1))
        try:
            tree_contribs = self.model.booster_.predict(X, pred_contrib=True)
            n_features = len(self.feature_names)
            has_shap = True
        except Exception as e:
            logger.debug("Tree SHAP computation skipped: %s", e)
            has_shap = False

        # Class indexing: 0 -> -1 (SELL), 1 -> 0 (NO_TRADE), 2 -> +1 (BUY)
        for i in range(n):
            c_val = close[i]
            atr_val = atr[i] if not np.isnan(atr[i]) and atr[i] > 0 else 50.0

            p_sell = calib_probs[i, 0]
            p_flat = calib_probs[i, 1]
            p_buy = calib_probs[i, 2]

            # Extract top 3 SHAP drivers for the candle if available
            shap_desc = ""
            if has_shap:
                try:
                    # Reshape tree_contribs: class 0 (sell), class 1 (flat), class 2 (buy)
                    contribs_c2 = tree_contribs[i, 2 * (n_features + 1) : 2 * (n_features + 1) + n_features]
                    top_f_idx = np.argsort(np.abs(contribs_c2))[-3:][::-1]
                    shap_desc = "; ".join([f"{self.feature_names[idx]}(SHAP={contribs_c2[idx]:+.2f})" for idx in top_f_idx])
                except Exception:
                    shap_desc = "SHAP_UNAVAILABLE"

            if p_buy > p_sell and p_buy > p_flat:
                directions[i] = SignalDirection.BUY.value
                confidences[i] = float(p_buy)
                stops[i] = c_val - (self.sl_mult * atr_val)
                targets[i] = c_val + (self.pt_mult * atr_val)
                margins[i] = float(p_buy - max(p_sell, p_flat))
                reasons[i] = f"LGBM_BUY(p={p_buy:.2f},margin={margins[i]:.2f}) | {shap_desc}"
            elif p_sell > p_buy and p_sell > p_flat:
                directions[i] = SignalDirection.SELL.value
                confidences[i] = float(p_sell)
                stops[i] = c_val + (self.sl_mult * atr_val)
                targets[i] = c_val - (self.pt_mult * atr_val)
                margins[i] = float(p_sell - max(p_buy, p_flat))
                reasons[i] = f"LGBM_SELL(p={p_sell:.2f},margin={margins[i]:.2f}) | {shap_desc}"
            else:
                directions[i] = SignalDirection.NO_TRADE.value
                confidences[i] = float(p_flat)
                stops[i] = 0.0
                targets[i] = 0.0
                margins[i] = 0.0
                reasons[i] = f"LGBM_NO_TRADE(p_flat={p_flat:.2f})"

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


class LightGBMTripleBarrierModel(BaseSignalModel):
    """Model 3B: LightGBM predicting Triple Barrier outcomes (tb_label).

    CRITICAL RULE (MASTER PROMPT REQUIREMENT 5):
    Trade Model 3B using exactly the label exits:
    - 2.0 ATR profit target
    - 1.5 ATR stop loss
    - 10 bar time limit
    """

    def __init__(
        self,
        name: str = "LightGBM_Triple_Barrier",
        params: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(name=name, params=params)
        self.calibrator = MultiClassCalibrator(method="isotonic")
        self.feature_names: List[str] = []
        self.model: Optional[lgb.LGBMClassifier] = None
        self.atr_col = self.params.get("atr_col", "atr_14")
        # Exactly matching Triple Barrier label definition parameters
        self.pt_mult = 2.0
        self.sl_mult = 1.5
        self.time_limit_bars = 10

    def _select_features(self, df: pd.DataFrame) -> List[str]:
        target_prefixes = ("target_fwd_", "target_dir_")
        numeric_cols = [
            c for c in df.columns
            if c not in EXCLUDED_COLS
            and not c.startswith(target_prefixes)
            and pd.api.types.is_numeric_dtype(df[c])
            and df[c].isna().mean() < 0.30
        ]
        return numeric_cols

    def fit(self, train_df: pd.DataFrame, **kwargs: Any) -> LightGBMTripleBarrierModel:
        train_sub, calib_sub = split_calibration_slice(train_df, calib_pct=0.20, purge_bars=10)
        self.feature_names = self._select_features(train_sub)

        # Compute triple barrier labels if not present
        if "tb_label" not in train_sub.columns:
            from models.labels import compute_triple_barrier_labels
            tb_all = compute_triple_barrier_labels(
                train_df,
                pt_atr_mult=self.pt_mult,
                sl_atr_mult=self.sl_mult,
                time_limit_bars=self.time_limit_bars,
            )
            train_sub["tb_label"] = tb_all["tb_label"].iloc[: len(train_sub)]
            calib_sub["tb_label"] = tb_all["tb_label"].iloc[-len(calib_sub):].values

        valid_train = train_sub.dropna(subset=self.feature_names + ["tb_label"])
        X_train = valid_train[self.feature_names].values
        # Shift classes from {-1, 0, 1} to {0, 1, 2}
        y_train_raw = valid_train["tb_label"].values.astype(int)
        y_train = y_train_raw + 1

        self.model = lgb.LGBMClassifier(
            objective="multiclass",
            num_class=3,
            n_estimators=70,
            max_depth=4,
            num_leaves=15,
            learning_rate=0.03,
            min_child_samples=25,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42,
            verbosity=-1,
        )
        self.model.fit(X_train, y_train)

        # Chronological calibration slice
        valid_calib = calib_sub.dropna(subset=self.feature_names + ["tb_label"])
        if len(valid_calib) >= 20:
            X_calib = valid_calib[self.feature_names].values
            raw_calib_probs = self.model.predict_proba(X_calib)
            y_calib_raw = valid_calib["tb_label"].values.astype(int)
            y_calib = y_calib_raw + 1
            self.calibrator.fit(raw_calib_probs, y_calib)

        self.is_fitted = True
        return self

    def predict_signals(self, df: pd.DataFrame, **kwargs: Any) -> pd.DataFrame:
        n = len(df)
        directions = [SignalDirection.NO_TRADE.value] * n
        confidences = [0.0] * n
        stops = [0.0] * n
        targets = [0.0] * n
        reasons = ["MODEL_NOT_FITTED"] * n
        margins = [0.0] * n

        if not self.is_fitted or self.model is None or not self.feature_names:
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

        close = df["close"].values
        atr = df[self.atr_col].values if self.atr_col in df.columns else np.full(n, 100.0)

        feat_df = df[self.feature_names].copy().fillna(0.0)
        X = feat_df.values
        raw_probs = self.model.predict_proba(X)
        calib_probs = self.calibrator.predict_calibrated(raw_probs)

        try:
            tree_contribs = self.model.booster_.predict(X, pred_contrib=True)
            n_features = len(self.feature_names)
            has_shap = True
        except Exception:
            has_shap = False

        for i in range(n):
            c_val = close[i]
            atr_val = atr[i] if not np.isnan(atr[i]) and atr[i] > 0 else 50.0

            p_sl = calib_probs[i, 0]    # Class 0: -1 (Stop Loss hit first)
            p_vert = calib_probs[i, 1]  # Class 1: 0 (Vertical time limit exit)
            p_pt = calib_probs[i, 2]    # Class 2: +1 (Profit Take hit first)

            shap_desc = ""
            if has_shap:
                try:
                    contribs_c2 = tree_contribs[i, 2 * (n_features + 1) : 2 * (n_features + 1) + n_features]
                    top_f_idx = np.argsort(np.abs(contribs_c2))[-3:][::-1]
                    shap_desc = "; ".join([f"{self.feature_names[idx]}(SHAP={contribs_c2[idx]:+.2f})" for idx in top_f_idx])
                except Exception:
                    shap_desc = ""

            # Trade ONLY when Profit Take barrier probability dominates both SL and Vertical barrier
            if p_pt > p_sl and p_pt > p_vert:
                directions[i] = SignalDirection.BUY.value
                confidences[i] = float(p_pt)
                # Exact label exits: 2.0 ATR profit target, 1.5 ATR stop loss
                stops[i] = c_val - (self.sl_mult * atr_val)
                targets[i] = c_val + (self.pt_mult * atr_val)
                margins[i] = float(p_pt - max(p_sl, p_vert))
                reasons[i] = f"TB_PROFIT_TAKE_PREDICTED(p_pt={p_pt:.2f},margin={margins[i]:.2f}) | {shap_desc}"
            elif p_sl > p_pt and p_sl > p_vert:
                # If stop loss barrier is predicted, signal SELL / SHORT trade
                directions[i] = SignalDirection.SELL.value
                confidences[i] = float(p_sl)
                stops[i] = c_val + (self.sl_mult * atr_val)
                targets[i] = c_val - (self.pt_mult * atr_val)
                margins[i] = float(p_sl - max(p_pt, p_vert))
                reasons[i] = f"TB_STOP_LOSS_PREDICTED(p_sl={p_sl:.2f},margin={margins[i]:.2f}) | {shap_desc}"
            else:
                directions[i] = SignalDirection.NO_TRADE.value
                confidences[i] = float(p_vert)
                stops[i] = 0.0
                targets[i] = 0.0
                margins[i] = 0.0
                reasons[i] = f"TB_VERTICAL_BARRIER_PREDICTED(p_vert={p_vert:.2f})"

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
