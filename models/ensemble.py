"""Voting Ensemble Model requiring consensus between at least two independent model families."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd

from models.base import BaseSignalModel, SignalDirection

logger = logging.getLogger(__name__)


class ConsensusVotingEnsemble(BaseSignalModel):
    """Ensemble model that generates a trade signal ONLY when >= 2 independent models agree on direction."""

    def __init__(
        self,
        models: Optional[List[BaseSignalModel]] = None,
        min_agreement: int = 2,
        name: str = "Consensus_Ensemble",
        params: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(name=name, params=params)
        self.models = models or []
        self.min_agreement = min_agreement
        self.voting_audit: Dict[str, Any] = {}

    def fit(self, train_df: pd.DataFrame, **kwargs: Any) -> ConsensusVotingEnsemble:
        """Fit all component models on the provided training partition."""
        for m in self.models:
            m.fit(train_df, **kwargs)
        self.is_fitted = True
        return self

    def predict_signals(self, df: pd.DataFrame, **kwargs: Any) -> pd.DataFrame:
        n = len(df)
        if not self.models:
            return pd.DataFrame(
                {
                    "direction": [SignalDirection.NO_TRADE.value] * n,
                    "confidence": [0.0] * n,
                    "suggested_entry": df["close"].values,
                    "stop_loss": [0.0] * n,
                    "take_profit": [0.0] * n,
                    "reasons": ["NO_MODELS_REGISTERED"] * n,
                    "margin": [0.0] * n,
                },
                index=df.index,
            )

        # Collect predictions from all sub-models
        sub_preds: List[pd.DataFrame] = [m.predict_signals(df, **kwargs) for m in self.models]

        directions = [SignalDirection.NO_TRADE.value] * n
        confidences = [0.0] * n
        stops = [0.0] * n
        targets = [0.0] * n
        reasons = ["NO_CONSENSUS"] * n
        margins = [0.0] * n
        close = df["close"].values

        # Auditing metrics per member
        member_names = [m.name for m in self.models]
        vote_counts = {name: {"BUY": 0, "SELL": 0, "NO_TRADE": 0} for name in member_names}
        agreement_counts = {name: 0 for name in member_names}
        deciding_vote_counts = {name: 0 for name in member_names}
        total_consensus_buys = 0
        total_consensus_sells = 0

        for i in range(n):
            buy_votes: List[int] = []
            sell_votes: List[int] = []

            for m_idx, pred in enumerate(sub_preds):
                d = pred["direction"].iloc[i]
                m_name = member_names[m_idx]
                if d == SignalDirection.BUY.value:
                    buy_votes.append(m_idx)
                    vote_counts[m_name]["BUY"] += 1
                elif d == SignalDirection.SELL.value:
                    sell_votes.append(m_idx)
                    vote_counts[m_name]["SELL"] += 1
                else:
                    vote_counts[m_name]["NO_TRADE"] += 1

            if len(buy_votes) >= self.min_agreement and len(sell_votes) == 0:
                total_consensus_buys += 1
                agreeing_names = [member_names[idx] for idx in buy_votes]
                agreeing_confs = [sub_preds[idx]["confidence"].iloc[i] for idx in buy_votes]
                agreeing_stops = [sub_preds[idx]["stop_loss"].iloc[i] for idx in buy_votes if sub_preds[idx]["stop_loss"].iloc[i] > 0]
                agreeing_targets = [sub_preds[idx]["take_profit"].iloc[i] for idx in buy_votes if sub_preds[idx]["take_profit"].iloc[i] > 0]

                directions[i] = SignalDirection.BUY.value
                confidences[i] = float(np.mean(agreeing_confs))
                stops[i] = float(np.max(agreeing_stops)) if agreeing_stops else close[i] * 0.98  # Conservative tightest stop
                targets[i] = float(np.mean(agreeing_targets)) if agreeing_targets else close[i] * 1.02
                margins[i] = confidences[i] - 0.33
                reasons[i] = f"CONSENSUS_BUY({len(buy_votes)}/{len(self.models)} models: {', '.join(agreeing_names)})"

                # Track agreement & decisive votes
                for idx in buy_votes:
                    agreement_counts[member_names[idx]] += 1
                    # Member was decisive if removing their vote drops count below min_agreement
                    if len(buy_votes) == self.min_agreement:
                        deciding_vote_counts[member_names[idx]] += 1

            elif len(sell_votes) >= self.min_agreement and len(buy_votes) == 0:
                total_consensus_sells += 1
                agreeing_names = [member_names[idx] for idx in sell_votes]
                agreeing_confs = [sub_preds[idx]["confidence"].iloc[i] for idx in sell_votes]
                agreeing_stops = [sub_preds[idx]["stop_loss"].iloc[i] for idx in sell_votes if sub_preds[idx]["stop_loss"].iloc[i] > 0]
                agreeing_targets = [sub_preds[idx]["take_profit"].iloc[i] for idx in sell_votes if sub_preds[idx]["take_profit"].iloc[i] > 0]

                directions[i] = SignalDirection.SELL.value
                confidences[i] = float(np.mean(agreeing_confs))
                stops[i] = float(np.min(agreeing_stops)) if agreeing_stops else close[i] * 1.02
                targets[i] = float(np.mean(agreeing_targets)) if agreeing_targets else close[i] * 0.98
                margins[i] = confidences[i] - 0.33
                reasons[i] = f"CONSENSUS_SELL({len(sell_votes)}/{len(self.models)} models: {', '.join(agreeing_names)})"

                for idx in sell_votes:
                    agreement_counts[member_names[idx]] += 1
                    if len(sell_votes) == self.min_agreement:
                        deciding_vote_counts[member_names[idx]] += 1
            else:
                directions[i] = SignalDirection.NO_TRADE.value
                confidences[i] = 0.0
                stops[i] = 0.0
                targets[i] = 0.0
                margins[i] = 0.0
                reasons[i] = f"NO_CONSENSUS(buy={len(buy_votes)}, sell={len(sell_votes)}, required>={self.min_agreement})"

        self.voting_audit = {
            "total_bars": n,
            "total_consensus_signals": total_consensus_buys + total_consensus_sells,
            "total_buys": total_consensus_buys,
            "total_sells": total_consensus_sells,
            "vote_distribution_by_member": vote_counts,
            "agreement_count_by_member": agreement_counts,
            "deciding_votes_by_member": deciding_vote_counts,
        }

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


class MajorityOfThreeEnsemble(ConsensusVotingEnsemble):
    """Simple 2-out-of-3 majority voting ensemble across 3 specified models."""

    def __init__(
        self,
        models: List[BaseSignalModel],
        name: str = "Majority_3_Ensemble",
        params: Optional[Dict[str, Any]] = None,
    ) -> None:
        if len(models) != 3:
            raise ValueError(f"MajorityOfThreeEnsemble requires exactly 3 models, got {len(models)}.")
        super().__init__(models=models, min_agreement=2, name=name, params=params)
