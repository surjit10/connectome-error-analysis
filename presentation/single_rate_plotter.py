"""
presentation/single_rate_plotter.py
=====================================
Generates figures for a **single error-rate experiment**.

Consumes precomputed :class:`~modules.statistical_evaluation.MetricEvaluation`
objects — never computes statistics itself.

Plots produced:
    plots/distributions/distribution_{metric}.png  — estimated PDF per metric
    plots/structure/spread_{metric}.png             — mean ± std across trials

Design constraints:
    - No statistical computation (no Cohen's d, no CI computation).
    - No HTML. No file export other than saving .png files.
    - All data is consumed from MetricEvaluation objects.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Tuple

import matplotlib
matplotlib.use("Agg")  # non-interactive backend
import matplotlib.pyplot as plt
import numpy as np
from scipy.stats import norm

from modules.statistical_evaluation.evaluator import MetricEvaluation

logger = logging.getLogger(__name__)

# Style constants
_FIG_STYLE   = "dark_background"
_ACCENT      = "#58a6ff"
_ACCENT2     = "#3fb950"
_TEXT_MUTED  = "#8b949e"
_SURFACE     = "#161b22"
_GRID_COLOR  = "#30363d"


def _apply_style(ax: plt.Axes) -> None:
    """Apply the project's dark scientific style to an axis."""
    ax.set_facecolor(_SURFACE)
    ax.figure.patch.set_facecolor("#0d1117")
    ax.tick_params(colors=_TEXT_MUTED, labelsize=8)
    ax.xaxis.label.set_color(_TEXT_MUTED)
    ax.yaxis.label.set_color(_TEXT_MUTED)
    ax.title.set_color("#e6edf3")
    ax.title.set_fontsize(10)
    ax.grid(color=_GRID_COLOR, linewidth=0.5, linestyle="--", alpha=0.6)
    for spine in ax.spines.values():
        spine.set_edgecolor(_GRID_COLOR)


class SingleRatePlotter:
    """Generate figures for one error-rate experiment.

    Args:
        metrics:     ``{analysis_name: {metric_name: MetricEvaluation}}``
        output_dir:  Root ``error_x/plots/`` directory for this experiment.
        error_rate:  Numeric error rate (e.g. ``0.10`` for 10%).
        baseline_rate: Numeric baseline error rate (always ``0.0``).
    """

    def __init__(
        self,
        metrics:       Dict[str, Dict[str, MetricEvaluation]],
        output_dir:    Path,
        error_rate:    float = 0.0,
        baseline_rate: float = 0.0,
    ) -> None:
        self._metrics   = metrics
        self._out       = Path(output_dir)
        self._rate      = error_rate
        self._baseline  = baseline_rate

        self._dist_dir   = self._out / "distributions"
        self._struct_dir = self._out / "structure"

    def generate_all(self) -> Tuple[List[str], List[str]]:
        """Generate all plots.

        Returns:
            Tuple of ``(dist_filenames, struct_filenames)``.
        """
        self._dist_dir.mkdir(parents=True, exist_ok=True)
        self._struct_dir.mkdir(parents=True, exist_ok=True)

        dist_files   = self._plot_distributions()
        struct_files = self._plot_spread()
        return dist_files, struct_files

    # ------------------------------------------------------------------ #
    # Distribution plots                                                   #
    # ------------------------------------------------------------------ #

    def _plot_distributions(self) -> List[str]:
        """Plot estimated Gaussian PDF for each metric.  Returns filenames."""
        filenames: List[str] = []

        with plt.style.context(_FIG_STYLE):
            for a_name, m_dict in self._metrics.items():
                for m_name, ev in m_dict.items():
                    if ev.std == 0 or not np.isfinite(ev.mean):
                        continue

                    fig, ax = plt.subplots(figsize=(7, 4))
                    _apply_style(ax)

                    # Baseline distribution (if available)
                    if np.isfinite(ev.baseline_mean) and ev.baseline_std > 0:
                        x_b = np.linspace(
                            ev.baseline_mean - 4 * ev.baseline_std,
                            ev.baseline_mean + 4 * ev.baseline_std, 200,
                        )
                        ax.plot(
                            x_b, norm.pdf(x_b, ev.baseline_mean, ev.baseline_std),
                            color=_ACCENT2, linewidth=1.5, linestyle="--",
                            label=f"Baseline (0%)",
                            alpha=0.8,
                        )

                    from presentation.dataset_exporter import _rate_label
                    rate_str = _rate_label(self._rate).replace("_", ".")
                    
                    # Perturbed distribution
                    x_p = np.linspace(ev.mean - 4 * ev.std, ev.mean + 4 * ev.std, 200)
                    ax.plot(
                        x_p, norm.pdf(x_p, ev.mean, ev.std),
                        color=_ACCENT, linewidth=2,
                        label=f"Error {rate_str}%",
                    )
                    ax.fill_between(
                        x_p, norm.pdf(x_p, ev.mean, ev.std),
                        alpha=0.15, color=_ACCENT,
                    )

                    ax.set_title(f"Distribution: {a_name}.{m_name}")
                    ax.set_xlabel("Value")
                    ax.set_ylabel("Density")
                    ax.legend(fontsize=8, facecolor=_SURFACE, edgecolor=_GRID_COLOR,
                              labelcolor=_TEXT_MUTED)

                    safe = f"{a_name}_{m_name}".replace(".", "_")
                    fname = f"distribution_{safe}.png"
                    fig.tight_layout()
                    fig.savefig(self._dist_dir / fname, dpi=120, bbox_inches="tight")
                    plt.close(fig)
                    filenames.append(fname)

        logger.info("[SingleRatePlotter] Generated %d distribution plot(s).", len(filenames))
        return filenames

    # ------------------------------------------------------------------ #
    # Spread (mean ± std) plots                                           #
    # ------------------------------------------------------------------ #

    def _plot_spread(self) -> List[str]:
        """Plot a compact mean ± std summary for each metric.  Returns filenames."""
        filenames: List[str] = []

        # Collect all (label, mean, std, baseline_mean) tuples
        entries = []
        for a_name, m_dict in self._metrics.items():
            for m_name, ev in m_dict.items():
                if not np.isfinite(ev.mean):
                    continue
                entries.append((f"{a_name}\n{m_name}", ev.mean, ev.std, ev.baseline_mean))

        if not entries:
            return filenames

        labels = [e[0] for e in entries]
        means  = np.array([e[1] for e in entries])
        stds   = np.array([e[2] for e in entries])
        blines = np.array([e[3] for e in entries])

        n = len(entries)
        x = np.arange(n)

        with plt.style.context(_FIG_STYLE):
            fig, ax = plt.subplots(figsize=(max(8, n * 0.9 + 1), 5))
            _apply_style(ax)

            ax.bar(x, means, color=_ACCENT, alpha=0.7, width=0.4, label="Perturbed mean")
            ax.errorbar(x, means, yerr=stds, fmt="none", color=_ACCENT, capsize=4, linewidth=1.5)

            # Baseline dots
            mask = np.isfinite(blines)
            if mask.any():
                ax.scatter(x[mask], blines[mask], color=_ACCENT2, zorder=5,
                           s=40, label="Baseline mean")

            ax.set_xticks(x)
            ax.set_xticklabels(labels, fontsize=7, rotation=30, ha="right")
            from presentation.dataset_exporter import _rate_label
            rate_str = _rate_label(self._rate).replace("_", ".")
            ax.set_title(f"Metric Spread — Error {rate_str}%")
            ax.set_ylabel("Mean ± Std")
            ax.legend(fontsize=8, facecolor=_SURFACE, edgecolor=_GRID_COLOR,
                      labelcolor=_TEXT_MUTED)

            fname = "metric_spread_summary.png"
            fig.tight_layout()
            fig.savefig(self._struct_dir / fname, dpi=120, bbox_inches="tight")
            plt.close(fig)
            filenames.append(fname)

        logger.info("[SingleRatePlotter] Generated %d structure plot(s).", len(filenames))
        return filenames
