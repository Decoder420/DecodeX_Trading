"""Data quality report generator for ingested market data."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
import pandas as pd
import pytz

from config.loader import ConfigManager, config_manager

logger = logging.getLogger(__name__)


class DataQualityReporter:
    """Generates structured data quality reports across instruments and timeframes."""

    def __init__(self, cfg: Optional[ConfigManager] = None) -> None:
        self.cfg = cfg or config_manager
        self.tz = pytz.timezone(self.cfg.get("market.timezone", "Asia/Kolkata"))
        self.reports: List[Dict[str, Any]] = []
        self.gap_details_by_instrument: Dict[str, List[Dict[str, str]]] = {}

    def evaluate_instrument(
        self,
        symbol: str,
        timeframe: str,
        df: pd.DataFrame,
        cleaning_metrics: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Evaluate dataset quality metrics for an instrument."""
        metrics = cleaning_metrics or {}
        gap_details = metrics.get("gap_details", [])
        self.gap_details_by_instrument[symbol] = gap_details

        if df.empty:
            report = {
                "instrument": symbol,
                "timeframe": timeframe,
                "row_count": 0,
                "start_date": "N/A",
                "end_date": "N/A",
                "gaps_count": 0,
                "unexplained_gaps": 0,
                "outliers_flagged": 0,
                "invalid_prices": 0,
                "duplicates_removed": metrics.get("duplicates_removed", 0),
                "last_updated": datetime.now(self.tz).strftime("%Y-%m-%d %H:%M:%S IST"),
                "status": "EMPTY",
            }
            self.reports.append(report)
            return report

        start_str = df["timestamp"].min().strftime("%Y-%m-%d")
        end_str = df["timestamp"].max().strftime("%Y-%m-%d")
        outliers = int(df["is_outlier"].sum()) if "is_outlier" in df.columns else 0
        gaps = metrics.get("gaps_detected", int(df["is_gap"].sum()) if "is_gap" in df.columns else 0)
        unexplained = metrics.get("unexplained_gaps", 0)
        invalid_prices = (
            int(df["is_zero_or_negative"].sum()) if "is_zero_or_negative" in df.columns else 0
        )
        duplicates = metrics.get("duplicates_removed", 0)

        # Strict status determination: Status MUST NOT say HEALTHY if any gap is unexplained
        if invalid_prices > 0:
            status = "CORRUPTED_PRICES"
        elif unexplained > 0:
            status = f"UNEXPLAINED_GAPS ({unexplained})"
        elif gaps > 0:
            status = "HEALTHY (EXPLAINED_GAPS)"
        else:
            status = "HEALTHY"

        report = {
            "instrument": symbol,
            "timeframe": timeframe,
            "row_count": len(df),
            "start_date": start_str,
            "end_date": end_str,
            "gaps_count": gaps,
            "unexplained_gaps": unexplained,
            "outliers_flagged": outliers,
            "invalid_prices": invalid_prices,
            "duplicates_removed": duplicates,
            "last_updated": datetime.now(self.tz).strftime("%Y-%m-%d %H:%M:%S IST"),
            "status": status,
        }
        self.reports.append(report)
        return report

    def to_dataframe(self) -> pd.DataFrame:
        """Return all evaluated reports as a pandas DataFrame."""
        return pd.DataFrame(self.reports)

    def print_summary(self) -> str:
        """Format and return the data quality report and gap audit as markdown tables."""
        df_rep = self.to_dataframe()
        if df_rep.empty:
            return "No data quality records to display."

        md_lines = [
            "### Data Quality Report",
            "",
            "| Instrument | Timeframe | Rows | Start Date | End Date | Gaps | Unexplained Gaps | Outliers Flagged | Invalid Prices | Duplicates Removed | Status | Last Updated |",
            "| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |",
        ]

        for _, r in df_rep.iterrows():
            md_lines.append(
                f"| **{r['instrument']}** | `{r['timeframe']}` | {r['row_count']:,} | "
                f"{r['start_date']} | {r['end_date']} | {r['gaps_count']} | {r['unexplained_gaps']} | {r['outliers_flagged']} | "
                f"{r['invalid_prices']} | {r['duplicates_removed']} | `{r['status']}` | {r['last_updated']} |"
            )

        # Append Flagged Gaps Detail Table if any gaps exist
        has_gaps = any(len(gaps) > 0 for gaps in self.gap_details_by_instrument.values())
        if has_gaps:
            md_lines.extend([
                "",
                "### Flagged Gaps Audit & Root-Cause Explanation",
                "",
                "| Instrument | Missing Date | Resumed Date | Category | Root-Cause Explanation |",
                "| :--- | :---: | :---: | :--- | :--- |",
            ])
            for inst, gaps in self.gap_details_by_instrument.items():
                if not gaps:
                    continue
                for g in gaps:
                    md_lines.append(
                        f"| **{inst}** | `{g['missing_date']}` | `{g['resumed_date']}` | `{g['category']}` | {g['explanation']} |"
                    )

        output = "\n".join(md_lines)
        print("\n" + output + "\n")
        return output
