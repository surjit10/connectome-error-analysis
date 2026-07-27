import sys
import os
import csv
from pathlib import Path
from typing import Dict

# Add parent to path to import modules
sys.path.append(str(Path(__file__).resolve().parent.parent))

from modules.statistical_evaluation.evaluator import StatisticalEvaluationResult, MetricEvaluation, _safe_cohens_d
from presentation.presentation_export import PresentationExporter
from presentation.root_index_exporter import RootIndexExporter

def parse_rate_from_folder(folder_name: str) -> float:
    # "10_percent" -> 10.0 -> 0.1
    # "0_25_percent" -> 0.25 -> 0.0025
    num_str = folder_name.replace("_percent", "").replace("_", ".")
    return float(num_str) / 100.0

import numpy as np

def load_aggregated_summary(folder: Path) -> dict:
    data = {}
    trial_dirs = list(folder.glob("trial_*"))
    if not trial_dirs:
        return {}
        
    all_trials_data = []
    for trial_dir in trial_dirs:
        csv_file = next(trial_dir.glob("*/summary.csv"), None)
        if not csv_file:
            continue
        trial_data = {}
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                analysis = row['analysis']
                metric = row['metric']
                if analysis not in trial_data:
                    trial_data[analysis] = {}
                trial_data[analysis][metric] = float(row['mean'])
        all_trials_data.append(trial_data)
        
    if not all_trials_data:
        return {}
        
    # Aggregate
    for a_name in all_trials_data[0]:
        data[a_name] = {}
        for m_name in all_trials_data[0][a_name]:
            values = [t[a_name][m_name] for t in all_trials_data if a_name in t and m_name in t[a_name]]
            n = len(values)
            mean = np.mean(values)
            std = np.std(values, ddof=1) if n > 1 else 0.0
            margin = 1.96 * std / np.sqrt(n) if n > 0 else 0.0
            data[a_name][m_name] = {
                'mean': float(mean),
                'std': float(std),
                'n': n,
                'ci_lower': float(mean - margin),
                'ci_upper': float(mean + margin),
            }
    return data

def main():
    base_dir = Path("/home/surjit/Desktop/flywire/v1/0-temp/MissedSynapses_BANC_results (1)")
    
    # 1. Find all rate folders
    rate_folders = [d for d in base_dir.iterdir() if d.is_dir() and d.name.endswith("_percent")]
    
    # 2. Load baseline (0_percent)
    baseline_folder = base_dir / "0_percent"
    if not baseline_folder.exists():
        print("Baseline not found!")
        return
        
    baseline_data = load_aggregated_summary(baseline_folder)
    
    results_by_rate = {}
    
    for folder in rate_folders:
        rate = parse_rate_from_folder(folder.name)
        rate_data = load_aggregated_summary(folder)
        if not rate_data:
            continue
        
        # Build StatisticalEvaluationResult
        eval_metrics = {}
        for a_name, m_dict in rate_data.items():
            eval_metrics[a_name] = {}
            for m_name, p_mstat in m_dict.items():
                b_mstat = baseline_data.get(a_name, {}).get(m_name)
                
                # If vector derived (contains spearman or pearson etc), null hypothesis is 0
                if b_mstat:
                    d = _safe_cohens_d(
                        p_mstat['mean'], p_mstat['std'], p_mstat['n'],
                        b_mstat['mean'], b_mstat['std'], b_mstat['n']
                    )
                    b_mean = b_mstat['mean']
                    b_std = b_mstat['std']
                else:
                    d = _safe_cohens_d(
                        p_mstat['mean'], p_mstat['std'], p_mstat['n'],
                        0.0, 0.0, 1
                    )
                    b_mean = 0.0
                    b_std = 0.0
                    
                eval_metrics[a_name][m_name] = MetricEvaluation(
                    metric_name=m_name,
                    baseline_mean=b_mean,
                    baseline_std=b_std,
                    mean=p_mstat['mean'],
                    std=p_mstat['std'],
                    ci_lower=p_mstat['ci_lower'],
                    ci_upper=p_mstat['ci_upper'],
                    effect_size=d
                )
                
        first_analysis = next(iter(rate_data.values())) if rate_data else {}
        first_metric = next(iter(first_analysis.values())) if first_analysis else {}
        n_trials = len(list(folder.glob("trial_*")))
        if n_trials == 0:
            n_trials = first_metric.get('n', 5)
        
        results_by_rate[rate] = StatisticalEvaluationResult(
            dataset_name="BANC",
            error_level=rate,
            n_trials=n_trials,
            runtime_seconds=0.0,
            metrics=eval_metrics
        )
        
    print(f"Loaded {len(results_by_rate)} rates.")
    
    # Run export
    exporter = PresentationExporter(
        output_root=base_dir,
        experiment_name="MissedSynapses_BANC",
        metadata={"dataset_name": "BANC", "error_model": "missed_synapses"}
    )
    exporter.export(results_by_rate)
    
    # Overwrite root index html (it might be wrong, but dataset exporter generates it correctly for the subfolder)
    print("Regeneration complete!")

if __name__ == "__main__":
    main()
