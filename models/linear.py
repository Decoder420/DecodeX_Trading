"""Regularized Linear Models (L1/L2 Logistic Regression) with chronological calibration."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

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


class RegularizedLogisticModel(BaseSignalModel):
    """Logistic Regression with L1 or L2 regularization and chronological calibration slice."""

    def __init__(
        self,
        name: str = "Linear_Logistic_L2",
        penalty: str = "l2",
        c_param: float = 0.5,
        target_col: str = "target_dir_3",
        params: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(name=name, params=params)
        self.penalty = penalty.lower()
        self.c_param = c_param
        self.target_col = target_col
        self.scaler = StandardScaler()
        self.calibrator = MultiClassCalibrator(method="sigmoid")
        self.feature_names: List[str] = []
        self.model: Optional[LogisticRegression] = None
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

    def fit(self, train_df: pd.DataFrame, **kwargs: Any) -> RegularizedLogisticModel:
        # Separate chronological calibration slice (last 20%, 10-bar purge)
        train_sub, calib_sub = split_calibration_slice(train_df, calib_pct=0.20, purge_bars=10)

        self.feature_names = self._select_features(train_sub)
        if not self.feature_names:
            raise ValueError("No valid numeric features found for linear model fitting.")

        if self.target_col not in train_sub.columns:
            from models.labels import compute_forward_returns
            horizons = [1, 3, 5]
            fwd_df = compute_forward_returns(train_df["close"], horizons=horizons)
            train_sub[self.target_col] = fwd_df[self.target_col].iloc[: len(train_sub)]
            calib_sub[self.target_col] = fwd_df[self.target_col].iloc[-len(calib_sub):].values

        # Prepare X, y for model training
        valid_train = train_sub.dropna(subset=self.feature_names + [self.target_col])
        if len(valid_train) < 50:
            logger.warning("Very few valid training rows (%d) for %s", len(valid_train), self.name)

        # Drop zero-variance features to prevent divide-by-zero during scaling
        stds = valid_train[self.feature_names].std()
        self.feature_names = [f for f in self.feature_names if stds[f] > 1e-6]

        X_train_raw = valid_train[self.feature_names].values
        y_train = valid_train[self.target_col].values.astype(int)

        self.scaler.fit(X_train_raw)
        X_train = np.clip(np.nan_to_num(self.scaler.transform(X_train_raw), nan=0.0, posinf=0.0, neginf=0.0), -5.0, 5.0)

        # Fit regularized Logistic Regression
        if self.penalty == "l1":
            self.model = LogisticRegression(
                penalty="l1",
                l1_ratio=1.0,
                C=self.c_param,
                solver="saga",
                max_iter=1000,
                random_state=42,
            )
        else:
            self.model = LogisticRegression(
                C=self.c_param,
                solver="lbfgs",
                max_iter=1000,
                random_state=42,
            )
        self.model.fit(X_train, y_train)

        # Chronological calibration slice
        valid_calib = calib_sub.dropna(subset=self.feature_names + [self.target_col])
        if len(valid_calib) >= 20:
            X_calib = np.clip(
                np.nan_to_num(self.scaler.transform(valid_calib[self.feature_names].values), nan=0.0, posinf=0.0, neginf=0.0),
                -5.0,
                5.0,
            )
            raw_calib_probs = self.model.predict_proba(X_calib)
            y_calib = valid_calib[self.target_col].values.astype(int)
            self.calibrator.fit(raw_calib_probs, y_calib)

        self.is_fitted = True
        return self

    def predict_signals(self, df: pd.DataFrame, **kwargs: Any) -> pd.DataFrame:
        n = len(df)
        directions = [SignalDirection.NO_TRADE.value] * n
        confidences = [0.0] * n
        stops = [0.0] * n
        targets = [0.0] * n
        reasons = ["NOT_ENOUGH_DATA"] * n
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

        # Impute missing feature values with 0.0 (z-score mean) for prediction
        feat_df = df[self.feature_names].copy().fillna(0.0)
        X_scaled = np.clip(np.nan_to_num(self.scaler.transform(feat_df.values), nan=0.0, posinf=0.0, neginf=0.0), -5.0, 5.0)
        raw_probs = self.model.predict_proba(X_scaled)
        calib_probs = self.calibrator.predict_calibrated(raw_probs)
        classes = self.model.classes_

        # Map classes to probability columns
        class_to_idx = {c: idx for idx, c in enumerate(classes)}

        # Top feature drivers from linear weights
        coefs = self.model.coef_
        top_driver_str = ""
        if len(coefs.shape) > 1 and coefs.shape[0] > 0:
            # Average absolute weights
            weights = np.mean(np.abs(coefs), axis=0)
            top_indices = np.argsort(weights)[-3:][::-1]
            top_drivers = [f"{self.feature_names[idx]}(w={weights[idx]:.2f})" for idx in top_indices]
            top_driver_str = "; ".join(top_drivers)

        for i in range(n):
            c_val = close[i]
            atr_val = atr[i] if not np.isnan(atr[i]) and atr[i] > 0 else 50.0

            p_buy = calib_probs[i, class_to_idx[1]] if 1 in class_to_idx else 0.0
            p_sell = calib_probs[i, class_to_idx[-1]] if -1 in class_to_idx else 0.0
            p_flat = calib_probs[i, class_to_idx[0]] if 0 in class_to_idx else 0.0

            # 3-Class decision logic:
            if p_buy > p_sell and p_buy > p_flat:
                directions[i] = SignalDirection.BUY.value
                confidences[i] = float(p_buy)
                stops[i] = c_val - (self.sl_mult * atr_val)
                targets[i] = c_val + (self.pt_mult * atr_val)
                margins[i] = float(p_buy - max(p_sell, p_flat))
                reasons[i] = f"LOGISTIC_PREDICT_BUY(p={p_buy:.2f},margin={margins[i]:.2f}) | {top_driver_str}"
            elif p_sell > p_buy and p_sell > p_flat:
                directions[i] = SignalDirection.SELL.value
                confidences[i] = float(p_sell)
                stops[i] = c_val + (self.sl_mult * atr_val)
                targets[i] = c_val - (self.pt_mult * atr_val)
                margins[i] = float(p_sell - max(p_buy, p_flat))
                reasons[i] = f"LOGISTIC_PREDICT_SELL(p={p_sell:.2f},margin={margins[i]:.2f}) | {top_driver_str}"
            else:
                directions[i] = SignalDirection.NO_TRADE.value
                confidences[i] = float(p_flat)
                stops[i] = 0.0
                targets[i] = 0.0
                margins[i] = 0.0
                reasons[i] = f"LOGISTIC_PREDICT_NO_TRADE(p_flat={p_flat:.2f})"

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
