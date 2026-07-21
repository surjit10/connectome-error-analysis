# presentation/presentation_export.py
import json
import csv
import os
import zipfile
from pathlib import Path
from typing import Dict, Any

from modules.statistical_evaluation.evaluator import StatisticalEvaluationResult
from .dashboard_serializer import DashboardSerializer
from .graph_generator import GraphGenerator

class PresentationExporter:
    def __init__(self, output_root: Path, experiment_name: str, metadata: Dict[str, Any]):
        self.output_root = Path(output_root)
        self.experiment_name = experiment_name
        self.metadata = metadata or {}
        
        self.pres_dir = self.output_root / "presentation"
        self.plots_dir = self.pres_dir / "plots"
        
    def export(self, results_by_rate: Dict[float, StatisticalEvaluationResult]) -> None:
        self.pres_dir.mkdir(parents=True, exist_ok=True)
        self.plots_dir.mkdir(parents=True, exist_ok=True)
        
        # 1. Dashboard Serialization
        serializer = DashboardSerializer(results_by_rate, self.metadata)
        dash_data = serializer.generate_dashboard_data()
        
        self._write_json(dash_data, self.pres_dir / "dashboard_data.json")
        self._write_json(dash_data["metadata"], self.pres_dir / "dashboard_metadata.json")
        self._write_json(self._generate_experiment_index(results_by_rate), self.pres_dir / "experiment_index.json")
        self._write_json(dash_data["effect_sizes"], self.pres_dir / "global_statistics.json")
        
        # 2. CSV Exports
        self._export_csvs(results_by_rate)
        
        # 3. Plots
        generator = GraphGenerator(results_by_rate, self.plots_dir)
        generator.generate_all()
        
        # 4. Zip the experiment package
        self._zip_directory()
        
    def _write_json(self, data: Any, path: Path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            
    def _generate_experiment_index(self, results_by_rate: Dict[float, StatisticalEvaluationResult]) -> list:
        index = []
        for rate, res in results_by_rate.items():
            index.append({
                "error_rate": rate,
                "n_trials": res.n_trials,
                "runtime": res.runtime_seconds
            })
        return index

    def _export_csvs(self, results_by_rate: Dict[float, StatisticalEvaluationResult]):
        rows = []
        for rate, res in results_by_rate.items():
            for a_name, m_dict in res.metrics.items():
                for m_name, ev in m_dict.items():
                    rows.append({
                        "rate": rate,
                        "analysis": a_name,
                        "metric": m_name,
                        "baseline_mean": ev.baseline_mean,
                        "mean": ev.mean,
                        "std": ev.std,
                        "ci_lower": ev.ci_lower,
                        "ci_upper": ev.ci_upper,
                        "effect_size": ev.effect_size
                    })
                    
        if not rows:
            return
            
        fieldnames = list(rows[0].keys())
        
        with open(self.pres_dir / "global_statistics.csv", "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
            
        with open(self.pres_dir / "effect_sizes.csv", "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["rate", "analysis", "metric", "effect_size"])
            writer.writeheader()
            for r in rows:
                writer.writerow({k: r[k] for k in ["rate", "analysis", "metric", "effect_size"]})

        with open(self.pres_dir / "confidence_intervals.csv", "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["rate", "analysis", "metric", "ci_lower", "ci_upper"])
            writer.writeheader()
            for r in rows:
                writer.writerow({k: r[k] for k in ["rate", "analysis", "metric", "ci_lower", "ci_upper"]})

        with open(self.pres_dir / "summary_statistics.csv", "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["rate", "analysis", "metric", "mean", "std"])
            writer.writeheader()
            for r in rows:
                writer.writerow({k: r[k] for k in ["rate", "analysis", "metric", "mean", "std"]})
                
    def _zip_directory(self):
        # Creates a ZIP of the ENTIRE output_root
        zip_name = f"{self.experiment_name.replace(' ', '_')}_complete.zip"
        zip_path = self.output_root.parent / zip_name
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for root, _, files in os.walk(self.output_root):
                for file in files:
                    file_path = Path(root) / file
                    zf.write(file_path, arcname=file_path.relative_to(self.output_root.parent))
