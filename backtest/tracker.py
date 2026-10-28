"""Experiment tracking, configuration hashing, and versioned model artifact storage."""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

EXPERIMENT_LOG_PATH = Path("data/experiments/experiment_log.jsonl")
ARTIFACTS_DIR = Path("models/artifacts")


class ExperimentTracker:
    """Logs every model run and saves immutable versioned model artifacts."""

    def __init__(
        self,
        log_path: Optional[Path] = None,
        artifacts_dir: Optional[Path] = None,
    ) -> None:
        self.log_path = log_path or EXPERIMENT_LOG_PATH
        self.artifacts_dir = artifacts_dir or ARTIFACTS_DIR
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def compute_config_hash(config_dict: Dict[str, Any]) -> str:
        serialized = json.dumps(config_dict, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:12]

    def log_experiment(
        self,
        model_name: str,
        symbol: str,
        config: Dict[str, Any],
        metrics: Dict[str, Any],
        decision_class: str,
        notes: str = "",
    ) -> str:
        """Append experiment run to local JSON Lines registry.

        Returns:
            Unique run ID.
        """
        cfg_hash = self.compute_config_hash(config)
        timestamp_str = datetime.now().isoformat()
        run_id = f"{model_name}_{symbol}_{cfg_hash}_{int(datetime.now().timestamp())}"

        record = {
            "run_id": run_id,
            "timestamp": timestamp_str,
            "model_name": model_name,
            "symbol": symbol,
            "config_hash": cfg_hash,
            "decision_class": decision_class,
            "metrics": metrics,
            "config": config,
            "notes": notes,
        }

        with open(self.log_path, "a") as f:
            f.write(json.dumps(record, default=str) + "\n")

        logger.info("Logged experiment run %s (Decision Class %s)", run_id, decision_class)
        return run_id

    def save_versioned_artifact(
        self,
        model_name: str,
        symbol: str,
        feature_names: List[str],
        train_window: str,
        config: Dict[str, Any],
        model_metadata: Dict[str, Any],
    ) -> Path:
        """Save versioned model metadata and parameters without overwriting older versions."""
        model_safe = model_name.replace(" ", "_").replace("/", "_")
        sym_safe = symbol.replace(" ", "_").replace("^", "")

        # Find next version number
        existing_versions = list(self.artifacts_dir.glob(f"{model_safe}_{sym_safe}_v*"))
        version = len(existing_versions) + 1

        artifact_dir = self.artifacts_dir / f"{model_safe}_{sym_safe}_v{version}"
        artifact_dir.mkdir(parents=True, exist_ok=False)

        manifest = {
            "model_name": model_name,
            "symbol": symbol,
            "version": version,
            "created_at": datetime.now().isoformat(),
            "training_window": train_window,
            "feature_count": len(feature_names),
            "feature_names": feature_names,
            "config": config,
            "metadata": model_metadata,
        }

        manifest_file = artifact_dir / "manifest.json"
        with open(manifest_file, "w") as f:
            json.dump(manifest, f, indent=2, default=str)

        logger.info("Saved versioned model artifact to %s", artifact_dir)
        return artifact_dir
