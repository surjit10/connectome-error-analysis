# presentation/dashboard_serializer.py
import dataclasses
import datetime
from typing import Dict, Any
from modules.statistical_evaluation.evaluator import StatisticalEvaluationResult
from .presentation_models import DashboardMetadata, DashboardData

class DashboardSerializer:
    def __init__(self, results_by_rate: Dict[float, StatisticalEvaluationResult], metadata: Dict[str, Any]):
        self.results = results_by_rate
        self.metadata = metadata
        self.rates = sorted(list(self.results.keys()))

    def generate_dashboard_data(self) -> dict:
        dataset_name = next(iter(self.results.values())).dataset_name if self.results else "Unknown"
        
        meta = DashboardMetadata(
            experiment_name=self.metadata.get("experiment_name", "Unknown"),
            dataset_name=dataset_name,
            framework_version="1.0.0",
            timestamp=datetime.datetime.utcnow().isoformat() + "Z"
        )
        
        available_metrics = []
        if self.rates:
            first_res = self.results[self.rates[0]]
            for a_name, m_dict in first_res.metrics.items():
                for m_name in m_dict.keys():
                    available_metrics.append(f"{a_name}.{m_name}")
                    
        effect_sizes = {m: {} for m in available_metrics}
        cis = {m: {} for m in available_metrics}
        
        for rate in self.rates:
            res = self.results[rate]
            rate_str = str(rate)
            for a_name, m_dict in res.metrics.items():
                for m_name, ev in m_dict.items():
                    key = f"{a_name}.{m_name}"
                    if key not in effect_sizes:
                        effect_sizes[key] = {}
                        cis[key] = {}
                    effect_sizes[key][rate_str] = ev.effect_size
                    cis[key][rate_str] = {"lower": ev.ci_lower, "upper": ev.ci_upper}
                    
        dash = DashboardData(
            metadata=meta,
            experiment_information=self.metadata,
            available_metrics=available_metrics,
            available_plots=["effect_size_vs_error_rate.png", "confidence_interval_vs_error_rate.png", "experiment_summary.png"],
            effect_sizes=effect_sizes,
            confidence_intervals=cis,
            summary_tables={}
        )
        
        return dataclasses.asdict(dash)
