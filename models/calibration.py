"""Probability calibration using separate chronological calibration slices and diagnostics."""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression

logger = logging.getLogger(__name__)


def split_calibration_slice(
    train_df: pd.DataFrame,
    calib_pct: float = 0.20,
    purge_bars: int = 10,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Split training window into a model-training sub-slice and a chronological calibration slice.

    A purge window of `purge_bars` (default 10) is placed between them to ensure no forward
    label leakage touches the calibration slice.

    Args:
        train_df: Full training fold DataFrame.
        calib_pct: Fraction of training window at the end reserved for calibration (default 20%).
        purge_bars: Number of bars purged immediately preceding the calibration slice (default 10).

    Returns:
        (model_train_df, calib_df)
    """
    n = len(train_df)
    n_calib = max(30, int(n * calib_pct))
    split_idx = n - n_calib
    purge_start = max(0, split_idx - purge_bars)

    model_train_df = train_df.iloc[:purge_start].copy().reset_index(drop=True)
    calib_df = train_df.iloc[split_idx:].copy().reset_index(drop=True)

    logger.debug(
        "Split training fold: Total %d bars -> Model Train %d bars, Purged %d bars, Calib Slice %d bars",
        n,
        len(model_train_df),
        split_idx - purge_start,
        len(calib_df),
    )
    return model_train_df, calib_df


def compute_brier_score(y_true: np.ndarray, y_prob: np.ndarray) -> float:
    """Compute multi-class or binary Brier score. Lower is better (0 is perfect)."""
    # If 1D binary probabilities
    if y_prob.ndim == 1:
        return float(np.mean((y_prob - y_true) ** 2))
    # If multi-class (one-hot true vs prob matrix)
    n_classes = y_prob.shape[1]
    y_true_onehot = np.eye(n_classes)[y_true]
    return float(np.mean(np.sum((y_prob - y_true_onehot) ** 2, axis=1)))


def compute_reliability_curve(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    n_bins: int = 5,
) -> Dict[str, Any]:
    """Compute reliability diagram bins and Expected Calibration Error (ECE)."""
    bin_edges = np.linspace(0.0, 1.0, n_bins + 1)
    bin_centers = []
    observed_freqs = []
    bin_counts = []
    ece = 0.0
    total_samples = len(y_true)

    for i in range(n_bins):
        low, high = bin_edges[i], bin_edges[i + 1]
        mask = (y_prob >= low) & (y_prob < high if i < n_bins - 1 else y_prob <= high)
        count = int(np.sum(mask))
        bin_counts.append(count)
        if count > 0:
            mean_prob = float(np.mean(y_prob[mask]))
            observed = float(np.mean(y_true[mask]))
            bin_centers.append(mean_prob)
            observed_freqs.append(observed)
            ece += (count / total_samples) * abs(observed - mean_prob)
        else:
            bin_centers.append((low + high) / 2.0)
            observed_freqs.append(0.0)

    return {
        "bin_centers": bin_centers,
        "observed_frequencies": observed_freqs,
        "bin_counts": bin_counts,
        "expected_calibration_error": float(ece),
    }


class MultiClassCalibrator:
    """Calibrates multi-class or binary probabilities using Platt (sigmoid) or Isotonic regression."""

    def __init__(self, method: str = "sigmoid") -> None:
        self.method = method.lower()
        self.calibrators: List[Any] = []
        self.classes_: Optional[np.ndarray] = None

    def fit(self, raw_probs: np.ndarray, y_true: np.ndarray) -> MultiClassCalibrator:
        """Fit calibrators on separate calibration slice.

        Args:
            raw_probs: Uncalibrated predicted probabilities of shape (N, C) or (N,).
            y_true: True class labels of shape (N,).
        """
        if raw_probs.ndim == 1:
            raw_probs = np.column_stack([1.0 - raw_probs, raw_probs])

        self.classes_ = np.unique(y_true)
        n_classes = raw_probs.shape[1]
        self.calibrators = []

        for c_idx in range(n_classes):
            target_class = self.classes_[c_idx] if c_idx < len(self.classes_) else c_idx
            binary_y = (y_true == target_class).astype(int)

            # Avoid single-class fitting crashes
            if len(np.unique(binary_y)) < 2:
                self.calibrators.append(None)
                continue

            prob_col = raw_probs[:, c_idx]
            if self.method == "isotonic":
                iso = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
                iso.fit(prob_col, binary_y)
                self.calibrators.append(iso)
            else:
                # Platt scaling via univariate logistic regression
                lr = LogisticRegression(C=1.0, solver="lbfgs")
                lr.fit(prob_col.reshape(-1, 1), binary_y)
                self.calibrators.append(lr)

        return self

    def predict_calibrated(self, raw_probs: np.ndarray) -> np.ndarray:
        """Apply fitted calibrators and normalize probabilities across classes."""
        if not self.calibrators:
            return raw_probs

        is_1d = raw_probs.ndim == 1
        if is_1d:
            raw_probs = np.column_stack([1.0 - raw_probs, raw_probs])

        calibrated = np.zeros_like(raw_probs)
        for c_idx, calib in enumerate(self.calibrators):
            prob_col = raw_probs[:, c_idx]
            if calib is None:
                calibrated[:, c_idx] = prob_col
            elif self.method == "isotonic":
                calibrated[:, c_idx] = calib.predict(prob_col)
            else:
                calibrated[:, c_idx] = calib.predict_proba(prob_col.reshape(-1, 1))[:, 1]

        # Clip and re-normalize across classes so probabilities sum to 1.0
        calibrated = np.clip(calibrated, 1e-6, 1.0)
        row_sums = calibrated.sum(axis=1, keepdims=True)
        row_sums[row_sums == 0] = 1.0
        calibrated = calibrated / row_sums

        if is_1d:
            return calibrated[:, 1]
        return calibrated
