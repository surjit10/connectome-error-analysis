"""
modules/reporting/data_loader.py
================================
Loads raw per-trial summary CSVs produced by the Export Manager and
aggregates them into :class:`~modules.statistical_evaluation.StatisticalEvaluationResult`
objects ready for reporting.

This module isolates all I/O and aggregation logic that was previously
embedded directly in ``generate_plots.py``.  Moving it here enforces the
principle that ``generate_plots.py`` is a pure orchestrator with no
statistical knowledge.

Responsibilities:
    - Discover and load per-trial summary CSV files from an experiment root.
    - Aggregate trial-level statistics into cross-trial means and CIs.
    - Compute Cohen's d effect size relative to a provided baseline.
    - Return :class:`StatisticalEvaluationResult` objects per error rate.

Constraints:
    - No plotting.
    - No HTML.
    - No presentation logic.
    - No modification of the statistical evaluation module.
"""
from __future__ import annotations

import math
import logging
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from modules.statistical_evaluation.evaluator import (
    MetricEvaluation,
    StatisticalEvaluationResult,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Standalone helpers (preserved from original generate_plots.py logic)
# ---------------------------------------------------------------------------

def cohens_d(
    mean1: float, std1: float, n1: int,
    mean2: float, std2: float, n2: int,
) -> float:
    """Compute Cohen's d effect size between two groups."""
    if n1 + n2 <= 2 or std1 is None or std2 is None:
        return 0.0
    pooled_var = ((n1 - 1) * (std1 ** 2) + (n2 - 1) * (std2 ** 2)) / (n1 + n2 - 2)
    if pooled_var <= 0:
        return 0.0
    d = (mean1 - mean2) / math.sqrt(pooled_var)
    return d if math.isfinite(d) else 0.0


def load_trial_summaries(rate_dir: Path) -> pd.DataFrame:
    """Load all trial summary CSVs for a given error rate directory.

    Expected structure::

        rate_dir/
            trial_001/
                BANC_*/
                    summary.csv
            trial_002/
                ...

    Args:
        rate_dir: Path to the error-rate directory (e.g. ``0_percent/``).

    Returns:
        A concatenated :class:`~pandas.DataFrame` with columns
        ``[analysis, metric, n, mean, std, variance, min, max, ci_lower,
        ci_upper, trial, result_dir]``.  Empty if no CSVs are found.
    """
    rows: List[pd.DataFrame] = []
    if not rate_dir.exists() or not rate_dir.is_dir():
        logger.warning("[DataLoader] Rate directory not found: %s", rate_dir)
        return pd.DataFrame()

    trial_dirs = sorted(rate_dir.iterdir())
    for trial_dir in trial_dirs:
        if not trial_dir.is_dir():
            continue
        result_dirs = [
            d for d in trial_dir.iterdir()
            if d.is_dir() and d.name.startswith("BANC_")
        ]
        for rd in result_dirs:
            summary_csv = rd / "summary.csv"
            if summary_csv.exists():
                df = pd.read_csv(summary_csv)
                df["trial"] = trial_dir.name
                df["result_dir"] = str(rd.name)
                rows.append(df)
            else:
                logger.debug("[DataLoader] No summary.csv in %s", rd)

    if not rows:
        logger.info("[DataLoader] No trial data found in %s", rate_dir)
        return pd.DataFrame()

    return pd.concat(rows, ignore_index=True)


def aggregate_by_rate(
    summary_df: pd.DataFrame,
    baseline_df: Optional[pd.DataFrame] = None,
) -> Dict[str, Dict[str, MetricEvaluation]]:
    """Aggregate trial-level summaries into MetricEvaluation objects.

    Computes cross-trial mean, std, CI and Cohen's d effect size relative to
    the provided baseline.

    Args:
        summary_df:  DataFrame with all trials for one error rate.
        baseline_df: DataFrame with all baseline (0%) trials.  Required for
                     effect size computation; pass ``None`` for baseline itself.

    Returns:
        ``{analysis_name: {metric_name: MetricEvaluation}}``
    """
    metrics: Dict[str, Dict[str, MetricEvaluation]] = {}

    if summary_df.empty:
        return metrics

    pairs = summary_df[["analysis", "metric"]].drop_duplicates()

    for _, pair in pairs.iterrows():
        a_name = pair["analysis"]
        m_name = pair["metric"]

        subset = summary_df[
            (summary_df["analysis"] == a_name) &
            (summary_df["metric"] == m_name)
        ]

        trial_means = subset["mean"].values
        trial_stds  = subset["std"].values
        n_trials    = len(trial_means)

        avg_mean = float(np.mean(trial_means)) if n_trials > 0 else 0.0

        if n_trials > 1:
            std_means = float(np.std(trial_means, ddof=1))
        else:
            std_means = float(trial_stds[0]) if n_trials > 0 else 0.0

        avg_ci_lower = (
            float(subset["ci_lower"].mean())
            if "ci_lower" in subset.columns
            else avg_mean - 1.96 * std_means
        )
        avg_ci_upper = (
            float(subset["ci_upper"].mean())
            if "ci_upper" in subset.columns
            else avg_mean + 1.96 * std_means
        )

        # ── Effect size vs baseline ─────────────────────────────────────
        baseline_mean  = 0.0
        baseline_std   = 0.0
        effect_size    = 0.0

        if baseline_df is not None and not baseline_df.empty:
            b_sub = baseline_df[
                (baseline_df["analysis"] == a_name) &
                (baseline_df["metric"] == m_name)
            ]
            if not b_sub.empty:
                b_means       = b_sub["mean"].values
                b_stds        = b_sub["std"].values
                baseline_mean = float(np.mean(b_means))
                baseline_std  = float(np.mean(b_stds)) if len(b_stds) > 0 else 0.0

                pooled_std = math.sqrt(
                    ((len(b_means) - 1) * (baseline_std ** 2) +
                     (n_trials - 1)     * (std_means ** 2)) /
                    max(len(b_means) + n_trials - 2, 1)
                )
                if pooled_std > 0 and math.isfinite(pooled_std):
                    effect_size = (avg_mean - baseline_mean) / pooled_std
                if not math.isfinite(effect_size):
                    effect_size = 0.0

        if a_name not in metrics:
            metrics[a_name] = {}

        metrics[a_name][m_name] = MetricEvaluation(
            metric_name    = m_name,
            baseline_mean  = float(baseline_mean),
            baseline_std   = float(baseline_std),
            mean           = avg_mean,
            std            = std_means,
            ci_lower       = avg_ci_lower,
            ci_upper       = avg_ci_upper,
            effect_size    = float(effect_size),
        )

    return metrics


# ---------------------------------------------------------------------------
# High-level loader class
# ---------------------------------------------------------------------------

class ReportingDataLoader:
    """Discovers and loads all error-rate results for one experiment.

    Example::

        loader = ReportingDataLoader(
            results_root = Path("MissedSynapses_BANC_results"),
            dataset_name = "BANC",
        )
        results_by_rate = loader.load()

    Args:
        results_root: Root directory containing one sub-folder per error rate.
        dataset_name: Human-readable dataset name forwarded to result objects.
    """

    def __init__(self, results_root: Path, dataset_name: str) -> None:
        self.results_root = Path(results_root)
        self.dataset_name = dataset_name

    def load(self) -> Dict[float, StatisticalEvaluationResult]:
        """Load all error rates and return one result object per rate.

        Returns:
            ``{error_rate_float: StatisticalEvaluationResult}`` sorted by rate.

        Raises:
            FileNotFoundError: If the 0% baseline directory is absent.
        """
        baseline_path = self.results_root / "0_percent"
        if not baseline_path.exists():
            raise FileNotFoundError(
                f"Baseline (0%) directory not found: {baseline_path}"
            )

        baseline_df = load_trial_summaries(baseline_path)
        logger.info(
            "[DataLoader] Baseline: %d rows from %d trial(s).",
            len(baseline_df),
            baseline_df["trial"].nunique() if not baseline_df.empty else 0,
        )

        rate_dirs = sorted(
            d for d in self.results_root.iterdir() if d.is_dir()
        )
        results: Dict[float, StatisticalEvaluationResult] = {}

        for rate_dir in rate_dirs:
            rate_num = self._parse_rate(rate_dir.name)
            if rate_num is None:
                continue

            summary_df = load_trial_summaries(rate_dir)
            if summary_df.empty:
                logger.warning("[DataLoader] Skipping %s — no data.", rate_dir.name)
                continue

            n_trials = summary_df["trial"].nunique()
            logger.info(
                "[DataLoader] %s (%.0f%%): %d rows from %d trial(s).",
                rate_dir.name, rate_num * 100, len(summary_df), n_trials,
            )

            metrics = aggregate_by_rate(
                summary_df,
                baseline_df=None if rate_num == 0.0 else baseline_df,
            )

            avg_runtime = self._read_runtime(rate_dir)

            results[rate_num] = StatisticalEvaluationResult(
                dataset_name    = self.dataset_name,
                error_level     = rate_num,
                n_trials        = n_trials,
                runtime_seconds = avg_runtime,
                metrics         = metrics,
            )

        return dict(sorted(results.items()))

    # ------------------------------------------------------------------ #
    # Helpers                                                              #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _parse_rate(dir_name: str) -> Optional[float]:
        """Convert ``'10_percent'`` → ``0.10``.  Returns ``None`` on failure."""
        try:
            return float(dir_name.replace("_percent", "").replace("percent", "")) / 100.0
        except ValueError:
            return None

    @staticmethod
    def _read_runtime(rate_dir: Path) -> float:
        """Best-effort: read total runtime from trial_001's runtime report."""
        trial_001 = rate_dir / "trial_001"
        if not trial_001.exists():
            return 0.0
        for rd in trial_001.iterdir():
            if not rd.is_dir() or not rd.name.startswith("BANC_"):
                continue
            runtime_txt = rd / "runtime_report.txt"
            if runtime_txt.exists():
                try:
                    text = runtime_txt.read_text()
                    for line in text.splitlines():
                        if "total" in line.lower() or "duration" in line.lower():
                            parts = line.split(":")
                            if len(parts) > 1:
                                return float(parts[1].strip().split()[0])
                except Exception:  # noqa: BLE001
                    pass
        return 0.0
