"""
Hypothesis Testing Exporter
===========================
Exports structured trial summaries, statistical test tables, and narrative
markdown reports to designated output directories.
"""

from __future__ import annotations

import csv
import logging
import math
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from ..analysis.secondary_effects import SecondaryEffectRecord
from ..comparison.hypothesis_tests import HypothesisTestResult

logger = logging.getLogger(__name__)


class HypothesisExporter:
    """Handles writing hypothesis-testing deliverables."""

    def __init__(self, output_root: str | Path) -> None:
        self.output_root = Path(output_root)

    def export_null_observations(
        self,
        dataset: str,
        secondary_records: List[SecondaryEffectRecord],
    ) -> Dict[str, Path]:
        """Export replicate-level observations for NULL_ONLY runs.

        Writes replicate_level_effects.csv (and .parquet if available) to
        results/hypothesis_testing/<dataset>/null_observations/.
        """
        null_obs_dir = self.output_root / dataset / "null_observations"
        null_obs_dir.mkdir(parents=True, exist_ok=True)

        paths: Dict[str, Path] = {}
        if not secondary_records:
            return paths

        sec_df = pd.DataFrame([vars(r) for r in secondary_records])
        csv_path = null_obs_dir / "replicate_level_effects.csv"
        sec_df.to_csv(csv_path, index=False)
        paths["null_replicate_effects_csv"] = csv_path
        logger.info(f"[HypothesisExporter] Wrote null observations to {csv_path} ({len(sec_df)} rows).")

        # Also write summary CSV in comparisons dir for easy direct access
        comp_dir = self.output_root / dataset / "comparisons"
        comp_dir.mkdir(parents=True, exist_ok=True)
        comp_csv = comp_dir / "secondary_effect_summary.csv"
        sec_df.to_csv(comp_csv, index=False)
        paths["secondary_effect_summary"] = comp_csv

        try:
            parquet_path = null_obs_dir / "replicate_level_effects.parquet"
            sec_df.to_parquet(parquet_path, index=False)
            paths["null_replicate_effects_parquet"] = parquet_path
            logger.info(f"[HypothesisExporter] Wrote null observations to {parquet_path}.")
        except Exception as exc:
            logger.debug(f"[HypothesisExporter] Parquet export skipped: {exc}")

        return paths

    def export(
        self,
        dataset: str,
        null_model_name: str,
        secondary_records: List[SecondaryEffectRecord],
        test_results: List[HypothesisTestResult],
        extra_metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Path]:
        """Export all comparison tables and summary reports.

        Returns:
            Dict mapping artifact names to written file paths.
        """
        comparisons_dir = self.output_root / dataset / "comparisons"
        comparisons_dir.mkdir(parents=True, exist_ok=True)

        paths: Dict[str, Path] = {}

        # 1. Export secondary_effect_summary.csv
        if secondary_records:
            sec_df = pd.DataFrame([vars(r) for r in secondary_records])
            sec_path = comparisons_dir / "secondary_effect_summary.csv"
            sec_df.to_csv(sec_path, index=False)
            paths["secondary_effect_summary"] = sec_path
            logger.info(f"[HypothesisExporter] Wrote {sec_path} ({len(sec_df)} rows).")

            # Also export replicate_level_effects in null_observations if null records exist
            null_recs = [r for r in secondary_records if r.condition == "null"]
            if null_recs:
                null_paths = self.export_null_observations(dataset, null_recs)
                paths.update(null_paths)


        # 2. Export hypothesis_test_results.csv
        if test_results:
            rows = []
            for tr in test_results:
                row = tr.comparison.to_dict()
                row["adjusted_p_value"] = tr.adjusted_p_value
                row["is_significant"] = tr.is_significant
                row["interpretation"] = tr.interpretation
                rows.append(row)

            res_df = pd.DataFrame(rows)
            res_path = comparisons_dir / "hypothesis_test_results.csv"
            res_df.to_csv(res_path, index=False)
            paths["hypothesis_test_results"] = res_path
            logger.info(f"[HypothesisExporter] Wrote {res_path} ({len(res_df)} rows).")

            # 3. Export corrected_significance_results.csv
            sig_df = res_df[(res_df["is_significant"] == True) & (res_df["category"] == "secondary_emergent")]
            sig_path = comparisons_dir / "corrected_significance_results.csv"
            sig_df.to_csv(sig_path, index=False)
            paths["corrected_significance_results"] = sig_path
            logger.info(f"[HypothesisExporter] Wrote {sig_path} ({len(sig_df)} significant findings).")

            # 4. Export summary.md
            md_path = comparisons_dir / "summary.md"
            self._write_markdown_summary(
                md_path=md_path,
                dataset=dataset,
                null_model_name=null_model_name,
                test_results=test_results,
                extra=extra_metadata or {},
            )
            paths["summary_markdown"] = md_path
            logger.info(f"[HypothesisExporter] Wrote narrative summary to {md_path}.")

        return paths

    def _write_markdown_summary(
        self,
        md_path: Path,
        dataset: str,
        null_model_name: str,
        test_results: List[HypothesisTestResult],
        extra: Dict[str, Any],
    ) -> None:
        """Write human-readable markdown summary report."""
        lines = []
        lines.append(f"# Hypothesis-Testing Report: {dataset}")
        lines.append(f"**Null Model:** `{null_model_name}`  ")
        lines.append(f"**Total Hypotheses Evaluated:** {len(test_results)}  \n")

        lines.append("## Executive Summary\n")
        sig_count = sum(1 for r in test_results if r.is_significant and r.comparison.category == "secondary_emergent")
        lines.append(
            f"Of the secondary emergent structural metrics evaluated across error rates, "
            f"**{sig_count}** exhibited statistically significant differences (FDR-adjusted *p* < 0.05) "
            f"between the real connectome and the matched randomized null network.\n"
        )

        lines.append("## Hypothesis Test Results Table\n")
        lines.append("| Error Model | Rate | Metric | Category | Real Effect | Null Effect | Diff | Effect Size (d) | p-adj | Significant? |")
        lines.append("|:---|---:|:---|:---|---:|---:|---:|---:|---:|:---:|")

        for tr in test_results:
            c = tr.comparison
            rate_str = f"{c.error_rate * 100:.1f}%"
            real_str = f"{c.real_mean_effect:+.2%}"
            null_str = f"{c.null_mean_effect:+.2%}"
            diff_str = f"{c.effect_difference:+.2%}"
            d_str = f"{c.effect_size:.2f}" if math.isfinite(c.effect_size) else "N/A"
            padj_str = f"{tr.adjusted_p_value:.4f}" if tr.adjusted_p_value is not None else "N/A"
            sig_str = "✓ Yes" if tr.is_significant else "No"

            lines.append(
                f"| {c.error_model} | {rate_str} | {c.metric_name} | {c.category} | "
                f"{real_str} | {null_str} | {diff_str} | {d_str} | {padj_str} | {sig_str} |"
            )

        lines.append("\n## Detailed Scientific Interpretations\n")
        for tr in test_results:
            c = tr.comparison
            if c.category == "secondary_emergent":
                lines.append(f"### {c.error_model} @ {c.error_rate * 100:.1f}% error — `{c.metric_name}`")
                lines.append(f"> {tr.interpretation}\n")

        with open(md_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
