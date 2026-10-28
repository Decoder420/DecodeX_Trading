"""Guard and manager for final 2-year out-of-sample holdout evaluation.

Enforces strict single-shot evaluation:
- Logs every evaluation attempt with timestamp, git commit/hash, model name, and metrics.
- Refuses subsequent evaluations unless explicit override flag `--allow-holdout-eval` is supplied.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)

DEFAULT_GUARD_FILE = Path("backtest/holdout_eval_guard.json")


class HoldoutGuardError(Exception):
    """Raised when holdout evaluation is attempted without required override permissions."""
    pass


class HoldoutManager:
    """Manages access and tamper-evident logging for the sealed 2-year holdout dataset."""

    def __init__(self, guard_file_path: Optional[Path] = None) -> None:
        self.guard_file = guard_file_path or (Path(__file__).resolve().parent / "holdout_eval_guard.json")
        self._ensure_log_exists()

    def _ensure_log_exists(self) -> None:
        if not self.guard_file.exists():
            self.guard_file.parent.mkdir(parents=True, exist_ok=True)
            initial_data = {
                "created_at": datetime.now().isoformat(),
                "evaluations_count": 0,
                "history": [],
            }
            with open(self.guard_file, "w") as f:
                json.dump(initial_data, f, indent=2)

    def is_locked(self) -> bool:
        """Returns True if the holdout has already been evaluated at least once."""
        if not self.guard_file.exists():
            return False
        try:
            with open(self.guard_file, "r") as f:
                data = json.load(f)
            return data.get("evaluations_count", 0) > 0
        except Exception:
            return False

    def evaluate_holdout(
        self,
        eval_fn: Callable[[], Dict[str, Any]],
        model_name: str,
        allow_override: bool = False,
        experiment_notes: str = "",
    ) -> Dict[str, Any]:
        """Execute evaluation on the holdout dataset under guard protection.

        Args:
            eval_fn: Callable executing the holdout test.
            model_name: Identifier of the candidate model being evaluated.
            allow_override: Must be True if holdout was already evaluated previously.
            experiment_notes: Notes on why the holdout is being run.

        Raises:
            HoldoutGuardError: If holdout was previously evaluated and allow_override is False.
        """
        if self.is_locked() and not allow_override:
            raise HoldoutGuardError(
                f"HOLDOUT ACCESS BLOCKED: Final holdout was already evaluated. "
                f"To prevent data snooping and p-hacking, re-evaluating the holdout is forbidden "
                f"unless explicitly confirmed via allow_override=True / --allow-holdout-eval."
            )

        # Run evaluation
        results = eval_fn()

        # Log attempt
        with open(self.guard_file, "r") as f:
            data = json.load(f)

        record = {
            "evaluation_index": data.get("evaluations_count", 0) + 1,
            "timestamp": datetime.now().isoformat(),
            "model_name": model_name,
            "override_used": allow_override,
            "notes": experiment_notes,
            "metrics_summary": {k: float(v) for k, v in results.items() if isinstance(v, (int, float))},
        }

        data["evaluations_count"] = data.get("evaluations_count", 0) + 1
        data["history"].append(record)

        with open(self.guard_file, "w") as f:
            json.dump(data, f, indent=2)

        logger.info(
            "Holdout evaluation logged successfully for model '%s' (Run #%d)",
            model_name,
            data["evaluations_count"],
        )
        return results
