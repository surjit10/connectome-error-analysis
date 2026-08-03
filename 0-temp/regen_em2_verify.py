"""Regenerate the EM2 (false_synapses) presentation with the NEW symmetric
preservation formula, into a temp directory, and compare before/after.

This mirrors 0-temp/regenerate_presentation.py but for EM2 and never touches
the user's stored results under dataset/.
"""
import csv
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from modules.statistical_evaluation.evaluator import StatisticalEvaluationResult, MetricEvaluation, _safe_cohens_d
from presentation.presentation_export import PresentationExporter

BASE = Path("/home/surjit/Desktop/flywire/v1/dataset/error-2/results/BANC/false_synapses")
OUT = Path("/home/surjit/Desktop/flywire/v1/0-temp/em2_regen_verify")
OUT.mkdir(parents=True, exist_ok=True)


def parse_rate_from_folder(name: str) -> float:
    num = name.replace("_percent", "").replace("_", ".")
    return float(num) / 100.0


def load_aggregated_summary(folder: Path) -> dict:
    data = {}
    trial_dirs = sorted(folder.glob("trial_*"))
    all_trials = []
    for t in trial_dirs:
        csv_file = next(t.glob("*/summary.csv"), None)
        if not csv_file:
            continue
        trial = {}
        with open(csv_file, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                trial.setdefault(row["analysis"], {})[row["metric"]] = float(row["mean"])
        all_trials.append(trial)
    if not all_trials:
        return {}
    for a_name in all_trials[0]:
        data[a_name] = {}
        for m_name in all_trials[0][a_name]:
            vals = [t[a_name][m_name] for t in all_trials if a_name in t and m_name in t[a_name]]
            n = len(vals)
            mean = float(np.mean(vals))
            std = float(np.std(vals, ddof=1)) if n > 1 else 0.0
            margin = 1.96 * std / np.sqrt(n) if n > 0 else 0.0
            data[a_name][m_name] = {
                "mean": mean, "std": std, "n": n,
                "ci_lower": mean - margin, "ci_upper": mean + margin,
            }
    return data


def main():
    baseline = load_aggregated_summary(BASE / "0_percent")
    results_by_rate = {}
    for folder in sorted(BASE.glob("*_percent")):
        rate = parse_rate_from_folder(folder.name)
        rate_data = load_aggregated_summary(folder)
        if not rate_data:
            continue
        metrics = {}
        for a_name, m_dict in rate_data.items():
            metrics[a_name] = {}
            for m_name, pm in m_dict.items():
                bm = baseline.get(a_name, {}).get(m_name)
                if bm:
                    b_mean, b_std, b_n = bm["mean"], bm["std"], bm["n"]
                    d = _safe_cohens_d(pm["mean"], pm["std"], pm["n"], b_mean, b_std, b_n)
                else:
                    b_mean, b_std, b_n = 0.0, 0.0, 1
                    d = _safe_cohens_d(pm["mean"], pm["std"], pm["n"], 0.0, 0.0, 1)
                metrics[a_name][m_name] = MetricEvaluation(
                    metric_name=m_name, baseline_mean=b_mean, baseline_std=b_std,
                    mean=pm["mean"], std=pm["std"], ci_lower=pm["ci_lower"],
                    ci_upper=pm["ci_upper"], effect_size=d,
                )
        n_trials = len(list(folder.glob("trial_*")))
        results_by_rate[rate] = StatisticalEvaluationResult(
            dataset_name="BANC", error_level=rate, n_trials=n_trials,
            runtime_seconds=0.0, metrics=metrics,
        )

    print(f"Loaded {len(results_by_rate)} rates for EM2.")
    exporter = PresentationExporter(
        output_root=OUT,
        experiment_name="FalseSynapses_BANC",
        metadata={"dataset_name": "BANC", "error_model": "false_synapses"},
    )
    exporter.export(results_by_rate)
    print("Regeneration complete ->", OUT)


if __name__ == "__main__":
    main()
