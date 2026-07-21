# presentation/presentation_models.py
from dataclasses import dataclass
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
    effect_sizes: Dict[str, Dict[str, float]]
    confidence_intervals: Dict[str, Dict[str, Dict[str, float]]]
    summary_tables: Dict[str, Any]
