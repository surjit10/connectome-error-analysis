"""
presentation/trend_plotter.py
================================
Generates figures for the **trend analysis** across all error rates.

Consumes a precomputed :class:`~modules.reporting.trend_analysis.TrendAnalysisResult`
and a :class:`~modules.reporting.sensitivity_analysis.SensitivityResult` —
never computes statistics itself.

Plot groups produced:
    plots/metric_trends/    — one response curve per metric (Mean ± CI vs Rate)
    plots/global_summaries/ — all-metric preservation overlay
    plots/heatmaps/         — preservation heatmap, CI width heatmap
    plots/rankings/         — preservation ranking bar chart

Design constraints:
    - No statistical computation (no Cohen's d, no CI computation, no rankings).
    - No HTML. No file export other than saving .png files.
    - Receives pre-computed TrendAnalysisResult and SensitivityResult.
"""
from __future__ import annotations

import logging
import math
from pathlib import Path
from typing import Dict, List, Tuple

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import numpy as np
import pandas as pd
import seaborn as sns

from modules.reporting.trend_analysis import TrendAnalysisResult
from modules.reporting.sensitivity_analysis import SensitivityResult
from presentation.preservation_config import (
    calculate_preservation,
    get_biological_status,
    higher_is_better,
    is_preservation_metric,
)

logger = logging.getLogger(__name__)

# Style
_FIG_STYLE  = "dark_background"
_ACCENT     = "#58a6ff"
_ACCENT2    = "#3fb950"
_WARN       = "#d29922"
_DANGER     = "#f85149"
_TEXT       = "#e6edf3"
_TEXT_MUTED = "#8b949e"
_SURFACE    = "#161b22"
_GRID_COLOR = "#30363d"

_PALETTE = [
    "#58a6ff", "#3fb950", "#d29922", "#f85149",
    "#a5d6ff", "#7ee787", "#ffa657", "#ff7b72",
    "#bc8cff", "#79c0ff", "#56d364", "#e3b341",
]

_THRESHOLD_COLORS = {
    "Preserved": _ACCENT2,
    "Minor Impact": _WARN,
    "Moderate Impact": "#f0883e",
    "Significant Disruption": _DANGER,
}


def _apply_style(ax: plt.Axes) -> None:
    ax.set_facecolor(_SURFACE)
    ax.figure.patch.set_facecolor("#0d1117")
    ax.tick_params(colors=_TEXT_MUTED, labelsize=8)
    ax.xaxis.label.set_color(_TEXT_MUTED)
    ax.yaxis.label.set_color(_TEXT_MUTED)
    ax.title.set_color(_TEXT)
    ax.title.set_fontsize(10)
    ax.grid(color=_GRID_COLOR, linewidth=0.5, linestyle="--", alpha=0.6)
    for spine in ax.spines.values():
        spine.set_edgecolor(_GRID_COLOR)

def _preservation_color(preservation: float) -> str:
    """Return a color based on preservation percentage."""
    if preservation >= 99.0:
        return _ACCENT2
    elif preservation >= 95.0:
        return _WARN
    elif preservation >= 90.0:
        return "#f0883e"
    return _DANGER


class TrendPlotter:
    """Generate all trend analysis figures.

    Args:
        trend:       Pre-computed :class:`TrendAnalysisResult`.
        sensitivity: Pre-computed :class:`SensitivityResult`.
        output_dir:  Root ``trend_analysis/plots/`` directory.
    """

    def __init__(
        self,
        trend:       TrendAnalysisResult,
        sensitivity: SensitivityResult,
        output_dir:  Path,
    ) -> None:
        self._trend       = trend
        self._sensitivity = sensitivity
        self._out         = Path(output_dir)

        self._metric_trends_dir  = self._out / "metric_trends"
        self._global_dir         = self._out / "global_summaries"
        self._heatmaps_dir       = self._out / "heatmaps"
        self._rankings_dir       = self._out / "rankings"

    def generate_all(self) -> Dict[str, List[str]]:
        """Generate all trend plots.

        Returns:
            Dict mapping group name → list of filenames.
        """
        for d in [self._metric_trends_dir, self._global_dir,
                  self._heatmaps_dir, self._rankings_dir]:
            d.mkdir(parents=True, exist_ok=True)

        return {
            "metric_trends":   self._plot_metric_trends(),
            "global_summaries": self._plot_global_summaries(),
            "heatmaps":        self._plot_heatmaps(),
            "rankings":        self._plot_rankings(),
        }

    # ------------------------------------------------------------------ #
    # Per-metric response curves                                           #
    # ------------------------------------------------------------------ #

    def _plot_metric_trends(self) -> List[str]:
        """One line chart per metric: Mean ± CI vs Error Rate."""
        filenames: List[str] = []
        rates = self._trend.rates
        rate_pcts = [r * 100 for r in rates]

        if not rates:
            return filenames

        all_keys = set()
        for m_dict in self._trend.metrics_by_rate.values():
            all_keys.update(m_dict.keys())

        with plt.style.context(_FIG_STYLE):
            for key in sorted(all_keys):
                means  = []
                ci_lo  = []
                ci_hi  = []
                valid_rates = []

                for rate in rates:
                    ev = self._trend.metrics_by_rate.get(rate, {}).get(key)
                    if ev is None or not math.isfinite(ev.mean):
                        continue
                    means.append(ev.mean)
                    ci_lo.append(ev.ci_lower)
                    ci_hi.append(ev.ci_upper)
                    valid_rates.append(rate * 100)

                if len(valid_rates) < 2:
                    continue

                fig, ax = plt.subplots(figsize=(7, 4))
                _apply_style(ax)

                ax.plot(valid_rates, means, color=_ACCENT, marker="o",
                        linewidth=2, markersize=5, label="Mean")
                ax.fill_between(valid_rates, ci_lo, ci_hi,
                                color=_ACCENT, alpha=0.15, label="95% CI")

                # Baseline reference line
                ev0 = self._trend.metrics_by_rate.get(0.0, {}).get(key)
                if ev0 and math.isfinite(ev0.mean):
                    ax.axhline(ev0.mean, color=_ACCENT2, linestyle="--",
                               linewidth=1, label="Baseline", alpha=0.7)

                ax.set_title(f"Distribution Across Trials: {key}")
                ax.set_xlabel("Error Rate (%)")
                ax.set_ylabel("Mean Value")
                ax.set_xticks(valid_rates)
                ax.set_xticklabels([f"{r:g}%" for r in valid_rates], fontsize=8)
                ax.legend(fontsize=8, facecolor=_SURFACE, edgecolor=_GRID_COLOR,
                          labelcolor=_TEXT_MUTED)

                safe = key.replace(".", "_")
                fname = f"trend_{safe}.png"
                fig.tight_layout()
                fig.savefig(self._metric_trends_dir / fname, dpi=120, bbox_inches="tight")
                plt.close(fig)
                filenames.append(fname)

        logger.info("[TrendPlotter] Generated %d metric trend plot(s).", len(filenames))
        return filenames

    # ------------------------------------------------------------------ #
    # Global summaries                                                     #
    # ------------------------------------------------------------------ #

    def _plot_global_summaries(self) -> List[str]:
        """Preservation vs error rate — preservation metrics only."""
        filenames: List[str] = []
        rates = self._trend.rates
        if not rates:
            return filenames

        all_keys = sorted(set().union(*[m.keys() for m in self._trend.metrics_by_rate.values()]))
        # Filter to preservation metrics only
        pres_keys = [k for k in all_keys if is_preservation_metric(k)]
        if not pres_keys:
            return filenames

        rate_pcts = [r * 100 for r in rates]

        with plt.style.context(_FIG_STYLE):
            fig, ax = plt.subplots(figsize=(10, 6))
            _apply_style(ax)

            for i, key in enumerate(pres_keys):
                preservations = []
                for rate in rates:
                    ev = self._trend.metrics_by_rate.get(rate, {}).get(key)
                    if ev and math.isfinite(ev.mean):
                        pres = calculate_preservation(
                            ev.baseline_mean, ev.mean,
                            higher_is_better=higher_is_better(key),
                        )
                        preservations.append(pres)
                    else:
                        preservations.append(float("nan"))

                color = _PALETTE[i % len(_PALETTE)]
                ax.plot(rate_pcts, preservations, color=color, marker="o",
                        linewidth=1.5, markersize=4, label=key, alpha=0.85)

            ax.axhline(99.0, color=_ACCENT2, linestyle=":", linewidth=1,
                       label="99% Preserved", alpha=0.7)
            ax.axhline(95.0, color=_WARN, linestyle=":", linewidth=1,
                       label="95% Preserved", alpha=0.7)
            ax.axhline(90.0, color=_DANGER, linestyle=":", linewidth=1,
                       label="90% Preserved", alpha=0.7)

            ax.set_title("Biological Preservation vs Error Rate — All Metrics")
            ax.set_xlabel("Error Rate (%)")
            ax.set_ylabel("Preservation (%)")
            ax.set_ylim(0, 105)
            ax.set_xticks(rate_pcts)
            ax.set_xticklabels([f"{r:g}%" for r in rate_pcts], fontsize=8)
            ax.legend(
                bbox_to_anchor=(1.02, 1), loc="upper left", fontsize=7,
                facecolor=_SURFACE, edgecolor=_GRID_COLOR, labelcolor=_TEXT_MUTED,
            )

            fname = "preservation_all_metrics.png"
            fig.tight_layout()
            fig.savefig(self._global_dir / fname, dpi=120, bbox_inches="tight")
            plt.close(fig)
            filenames.append(fname)

        logger.info("[TrendPlotter] Generated %d global summary plot(s).", len(filenames))
        return filenames

    # ------------------------------------------------------------------ #
    # Heatmaps                                                             #
    # ------------------------------------------------------------------ #

    def _plot_heatmaps(self) -> List[str]:
        """Preservation heatmap, CI width heatmap, and correlation heatmap."""
        filenames: List[str] = []
        rates = self._trend.rates
        if not rates:
            return filenames

        all_keys = sorted(set().union(*[m.keys() for m in self._trend.metrics_by_rate.values()]))
        # Filter to preservation metrics only for preservation heatmap
        pres_keys = [k for k in all_keys if is_preservation_metric(k)]
        rate_pcts = [f"{r*100:g}%" for r in rates]

        # Build DataFrames (CI data for all metrics, preservation data only for preservation metrics)
        ci_data: Dict[str, list] = {k: [] for k in all_keys}
        pres_data: Dict[str, list] = {k: [] for k in pres_keys}

        for rate in rates:
            for key in all_keys:
                ev = self._trend.metrics_by_rate.get(rate, {}).get(key)
                ci_val = (ev.ci_upper - ev.ci_lower) if (ev and math.isfinite(ev.ci_upper)) else float("nan")
                ci_data[key].append(ci_val)
                # Preservation data only for preservation metrics
                if is_preservation_metric(key):
                    if ev and math.isfinite(ev.mean):
                        pres = calculate_preservation(
                            ev.baseline_mean, ev.mean,
                            higher_is_better=higher_is_better(key),
                        )
                        pres_data[key].append(pres)
                    else:
                        pres_data[key].append(float("nan"))

        pres_df = pd.DataFrame(pres_data, index=rate_pcts).T if pres_keys else pd.DataFrame()
        ci_df = pd.DataFrame(ci_data, index=rate_pcts).T

        sns.set_theme(style="dark")

        # Preservation heatmap
        with plt.style.context(_FIG_STYLE):
            fig, ax = plt.subplots(figsize=(max(6, len(rates) * 1.2 + 2), max(4, len(all_keys) * 0.45 + 1.5)))
            fig.patch.set_facecolor("#0d1117")
            sns.heatmap(
                pres_df, annot=True, cmap="RdYlGn", vmin=0, vmax=100, fmt=".4f",
                ax=ax, linewidths=0.3, linecolor=_GRID_COLOR,
                annot_kws={"size": 7},
                cbar_kws={"shrink": 0.8, "label": "Preservation (%)"},
            )
            ax.set_title("Biological Preservation Heatmap (%)", color=_TEXT, pad=12)
            ax.tick_params(colors=_TEXT_MUTED, labelsize=7)
            fig.tight_layout()
            fname = "preservation_heatmap.png"
            fig.savefig(self._heatmaps_dir / fname, dpi=120, bbox_inches="tight",
                        facecolor="#0d1117")
            plt.close(fig)
            filenames.append(fname)

        # CI width heatmap
        with plt.style.context(_FIG_STYLE):
            fig, ax = plt.subplots(figsize=(max(6, len(rates) * 1.2 + 2), max(4, len(all_keys) * 0.45 + 1.5)))
            fig.patch.set_facecolor("#0d1117")
            sns.heatmap(
                ci_df, annot=True, cmap="viridis", fmt=".2f",
                ax=ax, linewidths=0.3, linecolor=_GRID_COLOR,
                annot_kws={"size": 7},
                cbar_kws={"shrink": 0.8},
            )
            ax.set_title("95% CI Width Heatmap", color=_TEXT, pad=12)
            ax.tick_params(colors=_TEXT_MUTED, labelsize=7)
            fig.tight_layout()
            fname = "ci_width_heatmap.png"
            fig.savefig(self._heatmaps_dir / fname, dpi=120, bbox_inches="tight",
                        facecolor="#0d1117")
            plt.close(fig)
            filenames.append(fname)

        # Correlation heatmap (if available)
        if self._trend.metric_correlations:
            keys_with_corr = sorted(self._trend.metric_correlations.keys())
            corr_matrix = np.array([
                [self._trend.metric_correlations[k1].get(k2, float("nan"))
                 for k2 in keys_with_corr]
                for k1 in keys_with_corr
            ])
            corr_df = pd.DataFrame(corr_matrix, index=keys_with_corr, columns=keys_with_corr)

            with plt.style.context(_FIG_STYLE):
                n = len(keys_with_corr)
                fig, ax = plt.subplots(figsize=(max(5, n * 0.6 + 1.5), max(4, n * 0.6 + 1.5)))
                fig.patch.set_facecolor("#0d1117")
                sns.heatmap(
                    corr_df, annot=True, cmap="RdBu_r", center=0, fmt=".2f",
                    ax=ax, linewidths=0.3, linecolor=_GRID_COLOR,
                    annot_kws={"size": 6},
                    vmin=-1, vmax=1,
                )
                ax.set_title("Metric Correlation Matrix", color=_TEXT, pad=12)
                ax.tick_params(colors=_TEXT_MUTED, labelsize=6)
                fig.tight_layout()
                fname = "metric_correlation.png"
                fig.savefig(self._heatmaps_dir / fname, dpi=120, bbox_inches="tight",
                            facecolor="#0d1117")
                plt.close(fig)
                filenames.append(fname)

        logger.info("[TrendPlotter] Generated %d heatmap(s).", len(filenames))
        return filenames

    # ------------------------------------------------------------------ #
    # Preservation ranking                                                 #
    # ------------------------------------------------------------------ #

    def _compute_preservation_ranking(self) -> List[Tuple[str, float]]:
        """Rank preservation metrics by minimum preservation (worst first)."""
        all_keys = sorted(set().union(*[m.keys() for m in self._trend.metrics_by_rate.values()]))
        ranking: List[Tuple[str, float]] = []
        for key in all_keys:
            if not is_preservation_metric(key):
                continue
            preservations = []
            for rate in self._trend.rates:
                ev = self._trend.metrics_by_rate.get(rate, {}).get(key)
                if ev and math.isfinite(ev.mean):
                    pres = calculate_preservation(
                        ev.baseline_mean, ev.mean,
                        higher_is_better=higher_is_better(key),
                    )
                    preservations.append(pres)
            if preservations:
                ranking.append((key, min(preservations)))
        ranking.sort(key=lambda x: x[1])
        return ranking

    def _plot_rankings(self) -> List[str]:
        """Horizontal bar chart of preservation ranking."""
        filenames: List[str] = []
        ranking = self._compute_preservation_ranking()
        if not ranking:
            return filenames

        ranking = ranking[:20]  # cap at 20 for readability
        labels    = [k for k, _ in reversed(ranking)]
        values    = [v for _, v in reversed(ranking)]
        colors    = [_preservation_color(v) for v in values]

        with plt.style.context(_FIG_STYLE):
            fig, ax = plt.subplots(figsize=(9, max(4, len(labels) * 0.38 + 1.5)))
            _apply_style(ax)

            bars = ax.barh(labels, values, color=colors, height=0.6, alpha=0.85)

            # Threshold lines
            ax.axvline(99.0, color=_ACCENT2, linestyle="--", linewidth=1,
                       label="99% Preserved", alpha=0.7)
            ax.axvline(95.0, color=_WARN, linestyle="--", linewidth=1,
                       label="95% Preserved", alpha=0.7)
            ax.axvline(90.0, color=_DANGER, linestyle="--", linewidth=1,
                       label="90% Preserved", alpha=0.7)

            # Value labels
            for bar, val in zip(bars, values):
                ax.text(val + 0.5, bar.get_y() + bar.get_height() / 2,
                        f"{val:.4f}%", va="center", ha="left",
                        fontsize=7, color=_TEXT_MUTED)

            ax.set_xlim(0, 105)
            ax.set_xlabel("Minimum Preservation (%)")
            ax.set_title("Biological Preservation Ranking (Worst Preservation First)")
            ax.legend(fontsize=8, facecolor=_SURFACE, edgecolor=_GRID_COLOR,
                      labelcolor=_TEXT_MUTED)

            fname = "preservation_ranking.png"
            fig.tight_layout()
            fig.savefig(self._rankings_dir / fname, dpi=120, bbox_inches="tight")
            plt.close(fig)
            filenames.append(fname)

        logger.info("[TrendPlotter] Generated %d ranking plot(s).", len(filenames))
        return filenames
