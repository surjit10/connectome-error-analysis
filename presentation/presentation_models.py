# presentation/presentation_models.py
from dataclasses import dataclass, field
from typing import Dict, List, Any

@dataclass
class DashboardMetadata:
    experiment_name: str
    dataset_name: str
    framework_version: str
    timestamp: str

@dataclass
class DashboardData:
    metadata: DashboardMetadata
    experiment_information: Dict[str, Any]
    available_metrics: List[str]
    available_plots: List[str]
    preservation: Dict[str, Dict[str, float]]
    confidence_intervals: Dict[str, Dict[str, Dict[str, float]]]
    summary_tables: Dict[str, Any]
    integrity_score: float = 0.0
    integrity_verdict: str = ""
    integrity_marker: str = ""
    biological_status: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    metric_types: Dict[str, str] = field(default_factory=dict)
