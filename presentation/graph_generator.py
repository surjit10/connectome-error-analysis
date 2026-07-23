# presentation/graph_generator.py
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import numpy as np
from typing import Dict
from pathlib import Path
from scipy.stats import norm
from modules.statistical_evaluation.evaluator import StatisticalEvaluationResult
from presentation.preservation_config import (
    calculate_preservation,
    higher_is_better,
    is_preservation_metric,
)

def _preservation_color(preservation: float) -> str:
    if preservation >= 99.0:
        return "#3fb950"
    elif preservation >= 95.0:
        return "#d29922"
    elif preservation >= 90.0:
        return "#f0883e"
    return "#f85149"


class GraphGenerator:
    def __init__(self, results_by_rate: Dict[float, StatisticalEvaluationResult], output_dir: Path):
        self.results = results_by_rate
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.rates = sorted(list(self.results.keys()))
        
        all_rows = []
        pres_rows = []
        for rate in self.rates:
            for a_name, m_dict in self.results[rate].metrics.items():
                for m_name, ev in m_dict.items():
                    key = f"{a_name}.{m_name}"
                    row = {
                        "Rate": rate,
                        "Analysis": a_name,
                        "Metric": m_name,
                        "FullMetric": key,
                        "Mean": ev.mean,
                        "Std": ev.std,
                        "CILower": ev.ci_lower,
                        "CIUpper": ev.ci_upper,
                    }
                    all_rows.append(row)
                    if is_preservation_metric(key):
                        preservation = calculate_preservation(
                            ev.baseline_mean, ev.mean,
                            higher_is_better=higher_is_better(key),
                        )
                        row_with_pres = {**row, "Preservation": preservation}
                        pres_rows.append(row_with_pres)
        self.df = pd.DataFrame(all_rows)
        self.df_pres = pd.DataFrame(pres_rows)

    def generate_all(self):
        if self.df.empty:
            return
        sns.set_theme(style="whitegrid")
        if not self.df_pres.empty:
            self._plot_preservation_vs_error_rate()
        self._plot_confidence_interval_vs_error_rate()
        self._plot_metric_response()
        self._plot_boxplots()
        self._plot_distributions()
        self._plot_heatmaps()
        self._plot_correlation_matrix()
        self._plot_experiment_summary()
        
    def _plot_preservation_vs_error_rate(self):
        plt.figure(figsize=(10, 6))
        sns.lineplot(data=self.df_pres, x="Rate", y="Preservation", hue="FullMetric", marker="o")
        plt.axhline(99.0, color="#3fb950", linestyle=":", linewidth=1, label="99% Preserved", alpha=0.7)
        plt.axhline(95.0, color="#d29922", linestyle=":", linewidth=1, label="95% Preserved", alpha=0.7)
        plt.axhline(90.0, color="#f85149", linestyle=":", linewidth=1, label="90% Preserved", alpha=0.7)
        plt.title("Biological Preservation vs Error Rate")
        plt.xlabel("Error Rate")
        plt.ylabel("Preservation (%)")
        plt.ylim(0, 105)
        plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
        plt.tight_layout()
        plt.savefig(self.output_dir / "preservation_vs_error_rate.png")
        plt.close()

    def _plot_confidence_interval_vs_error_rate(self):
        plt.figure(figsize=(10, 6))
        for metric in self.df["FullMetric"].unique():
            subset = self.df[self.df["FullMetric"] == metric]
            plt.plot(subset["Rate"], subset["Mean"], label=metric, marker="o")
            plt.fill_between(subset["Rate"], subset["CILower"], subset["CIUpper"], alpha=0.2)
        plt.title("Distribution Across Trials: Mean & 95% CI vs Error Rate")
        plt.xlabel("Error Rate")
        plt.ylabel("Metric Value")
        plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
        plt.tight_layout()
        plt.savefig(self.output_dir / "confidence_interval_vs_error_rate.png")
        plt.close()

    def _plot_metric_response(self):
        for metric in self.df["FullMetric"].unique():
            subset = self.df[self.df["FullMetric"] == metric]
            plt.figure(figsize=(6, 4))
            plt.plot(subset["Rate"], subset["Mean"], marker="o", color="blue")
            plt.fill_between(subset["Rate"], subset["CILower"], subset["CIUpper"], alpha=0.3, color="blue")
            plt.title(f"Distribution Across Trials: {metric}")
            plt.xlabel("Error Rate")
            plt.ylabel("Mean Value")
            plt.tight_layout()
            safe_name = metric.replace(".", "_")
            plt.savefig(self.output_dir / f"metric_response_vs_error_rate_{safe_name}.png")
            plt.close()

    def _plot_boxplots(self):
        for metric in self.df["FullMetric"].unique():
            subset = self.df[self.df["FullMetric"] == metric]
            plt.figure(figsize=(8, 5))
            rates = subset["Rate"].values
            means = subset["Mean"].values
            stds = subset["Std"].values
            
            plt.errorbar(rates, means, yerr=stds, fmt='o', capsize=5, capthick=2, label='Mean ± Std')
            plt.title(f"Spread: {metric}")
            plt.xlabel("Error Rate")
            plt.ylabel("Value")
            plt.xticks(rates, [f"{r*100:.1f}%" for r in rates])
            plt.tight_layout()
            safe_name = metric.replace(".", "_")
            plt.savefig(self.output_dir / f"boxplot_{safe_name}.png")
            plt.close()

    def _plot_distributions(self):
        for metric in self.df["FullMetric"].unique():
            subset = self.df[self.df["FullMetric"] == metric]
            plt.figure(figsize=(8, 5))
            
            for _, row in subset.iterrows():
                rate = row["Rate"]
                mean = row["Mean"]
                std = row["Std"]
                if pd.isna(mean) or pd.isna(std) or std == 0:
                    continue
                x = np.linspace(mean - 4*std, mean + 4*std, 100)
                plt.plot(x, norm.pdf(x, mean, std), label=f"Rate {rate*100:.1f}%")
                
            plt.title(f"Distribution Across Trials: {metric}")
            plt.xlabel("Value")
            plt.ylabel("Density")
            plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
            plt.tight_layout()
            safe_name = metric.replace(".", "_")
            plt.savefig(self.output_dir / f"distribution_{safe_name}.png")
            plt.close()

    def _plot_heatmaps(self):
        # CI Width (all metrics)
        self.df["CI_Width"] = self.df["CIUpper"] - self.df["CILower"]
        pivot_ci = self.df.pivot(index="FullMetric", columns="Rate", values="CI_Width")
        plt.figure(figsize=(8, 6))
        sns.heatmap(pivot_ci, annot=True, cmap="viridis", fmt=".2f")
        plt.title("Confidence Interval Width Heatmap")
        plt.tight_layout()
        plt.savefig(self.output_dir / "confidence_interval_heatmap.png")
        plt.close()

        # Preservation heatmap (preservation metrics only)
        if not self.df_pres.empty:
            pivot_pres = self.df_pres.pivot(index="FullMetric", columns="Rate", values="Preservation")
            plt.figure(figsize=(8, 6))
            sns.heatmap(pivot_pres, annot=True, cmap="RdYlGn", vmin=0, vmax=100, fmt=".2f")
            plt.title("Biological Preservation Heatmap (%)")
            plt.tight_layout()
            plt.savefig(self.output_dir / "preservation_heatmap.png")
            plt.close()

    def _plot_correlation_matrix(self):
        pivot = self.df.pivot(index="Rate", columns="FullMetric", values="Mean")
        corr = pivot.corr()
        plt.figure(figsize=(10, 8))
        sns.heatmap(corr, annot=True, cmap="RdBu", center=0, fmt=".2f")
        plt.title("Metric Correlation Matrix")
        plt.tight_layout()
        plt.savefig(self.output_dir / "metric_correlation_heatmap.png")
        plt.close()

    def _plot_experiment_summary(self):
        plt.figure(figsize=(8, 4))
        plt.text(0.1, 0.9, "Experiment Summary", fontsize=16, fontweight='bold')
        dataset = self.results[self.rates[0]].dataset_name if self.rates else "N/A"
        plt.text(0.1, 0.7, f"Dataset: {dataset}", fontsize=12)
        plt.text(0.1, 0.5, f"Error Rates Analyzed: {[f'{r*100:.1f}%' for r in self.rates]}", fontsize=12)
        plt.text(0.1, 0.3, f"Metrics Evaluated: {len(self.df['FullMetric'].unique())}", fontsize=12)
        plt.text(0.1, 0.1, "All figures and stats are generated from Phase 017 exported packages.", fontsize=10, style='italic')
        plt.axis("off")
        plt.tight_layout()
        plt.savefig(self.output_dir / "experiment_summary.png")
        plt.close()
