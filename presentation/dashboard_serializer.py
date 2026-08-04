# presentation/dashboard_serializer.py
import dataclasses
import datetime
from typing import Dict, Any
from modules.statistical_evaluation.evaluator import StatisticalEvaluationResult
from .presentation_models import DashboardMetadata, DashboardData
from .preservation_config import (
    calculate_preservation,
    get_biological_status,
    get_integrity_verdict,
    get_metric_type,
    is_preservation_metric,
    higher_is_better,
    KEY_INTEGRITY_METRICS,
)

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
                    
        preservation = {m: {} for m in available_metrics}
        cis = {m: {} for m in available_metrics}
        bio_status: Dict[str, Any] = {}
        metric_types: Dict[str, str] = {}
        
        for rate in self.rates:
            res = self.results[rate]
            rate_str = str(rate)
            for a_name, m_dict in res.metrics.items():
                for m_name, ev in m_dict.items():
                    key = f"{a_name}.{m_name}"
                    if key not in cis:
                        cis[key] = {}
                    cis[key][rate_str] = {"lower": ev.ci_lower, "upper": ev.ci_upper}
                    
                    # Only compute preservation for preservation-type metrics
                    if is_preservation_metric(key):
                        if key not in preservation:
                            preservation[key] = {}
                        pres = calculate_preservation(
                            ev.baseline_mean, ev.mean,
                            higher_is_better=higher_is_better(key), metric_key=key,
                        )
                        preservation[key][rate_str] = round(pres, 2)
                    
                    # Collect biological status for the first non-baseline rate
                    if rate > 0.0:
                        if key not in metric_types:
                            metric_types[key] = get_metric_type(key)
                        if key not in bio_status and is_preservation_metric(key):
                            emoji, label, css = get_biological_status(pres)
                            bio_status[key] = {
                                "preservation": round(pres, 2),
                                "status": label,
                                "emoji": emoji,
                                "css": css,
                            }
        
        # Compute integrity score from key metrics
        integrity_score = 100.0
        if self.rates:
            first_perturbed = next((r for r in self.rates if r > 0.0), None)
            if first_perturbed is not None:
                res = self.results[first_perturbed]
                preservations = []
                for a_name, m_dict in res.metrics.items():
                    for m_name, ev in m_dict.items():
                        key = f"{a_name}.{m_name}"
                        if key in KEY_INTEGRITY_METRICS:
                            pres = calculate_preservation(
                                ev.baseline_mean, ev.mean,
                                higher_is_better=higher_is_better(key), metric_key=key,
                            )
                            preservations.append(pres)
                if preservations:
                    integrity_score = round(sum(preservations) / len(preservations), 2)
        
        integrity_emoji, integrity_verdict, _ = get_integrity_verdict(integrity_score)
                    
        dash = DashboardData(
            metadata=meta,
            experiment_information=self.metadata,
            available_metrics=available_metrics,
            available_plots=["preservation_vs_error_rate.png", "confidence_interval_vs_error_rate.png", "experiment_summary.png"],
            preservation=preservation,
            confidence_intervals=cis,
            summary_tables={},
            integrity_score=integrity_score,
            integrity_verdict=integrity_verdict,
            integrity_emoji=integrity_emoji,
            biological_status=bio_status,
            metric_types=metric_types,
        )
        
        return dataclasses.asdict(dash)
