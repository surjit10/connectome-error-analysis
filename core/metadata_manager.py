"""
Phase 010 – Metadata Manager
==============================
Aggregates all available metadata from a single
:class:`~core.experiment_runner.ExperimentResult` into a single standardised
:class:`ExperimentMetadata` object that the Export Manager serialises.

Responsibilities:
    - Collect dataset, preprocessing, analysis, error-model, and runtime
      information from the existing result objects.
    - Never duplicate fields that are already present in result objects.
    - Return a fully serialisable plain-Python structure.

Constraints:
    - Consumes only ``ExperimentResult``. Never reruns anything.
    - Never modifies any result object.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from core.experiment_runner import ExperimentResult

logger = logging.getLogger(__name__)

# Increment when the metadata schema changes.
_FRAMEWORK_VERSION: str = "1.0.0"


# ---------------------------------------------------------------------------
# Metadata container
# ---------------------------------------------------------------------------

@dataclass
class ExperimentMetadata:
    """Standardised metadata for one experiment.

    Collected by :func:`collect_metadata` and consumed by
    :class:`~core.export_manager.ExportManager`.

    Attributes:
        experiment_id:          Identifier from :class:`~core.experiment_runner.ExperimentConfig`.
        framework_version:      Framework version string.
        dataset_name:           Name of the FlyWire dataset.
        dataset_root:           Path to the dataset root (from config snapshot).
        experiment_status:      Overall status string.
        started_at:             ISO-8601 UTC start timestamp.
        finished_at:            ISO-8601 UTC finish timestamp.
        runtime_seconds:        Total pipeline runtime.
        seed:                   Random seed used (or ``None``).
        error_model_name:       Name of the error model (or ``None``).
        error_model_config:     Error model configuration dict.
        analysis_names:         Ordered list of analysis names run.
        analysis_configs:       Per-analysis configuration dicts.
        preprocessing_metadata: Serialisable dict from ``GraphMetadata.to_dict()``.
        config_snapshot:        Full config snapshot from the result.
        warnings:               Pipeline warnings.
        errors:                 Pipeline errors.
        extra:                  Extra metadata forwarded from the result.
    """
    experiment_id: str = ""
    framework_version: str = _FRAMEWORK_VERSION
    dataset_name: str = ""
    dataset_root: str = ""
    experiment_status: str = ""
    started_at: str = ""
    finished_at: str = ""
    runtime_seconds: float = 0.0
    seed: Optional[int] = None
    error_model_name: Optional[str] = None
    error_model_config: Dict[str, Any] = field(default_factory=dict)
    analysis_names: List[str] = field(default_factory=list)
    analysis_configs: Dict[str, Any] = field(default_factory=dict)
    preprocessing_metadata: Dict[str, Any] = field(default_factory=dict)
    config_snapshot: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Return a fully serialisable ``dict``."""
        return {
            "experiment_id":          self.experiment_id,
            "framework_version":      self.framework_version,
            "dataset_name":           self.dataset_name,
            "dataset_root":           self.dataset_root,
            "experiment_status":      self.experiment_status,
            "started_at":             self.started_at,
            "finished_at":            self.finished_at,
            "runtime_seconds":        self.runtime_seconds,
            "seed":                   self.seed,
            "error_model_name":       self.error_model_name,
            "error_model_config":     self.error_model_config,
            "analysis_names":         self.analysis_names,
            "analysis_configs":       self.analysis_configs,
            "preprocessing_metadata": self.preprocessing_metadata,
            "config_snapshot":        self.config_snapshot,
            "warnings":               self.warnings,
            "errors":                 self.errors,
            "extra":                  self.extra,
        }


# ---------------------------------------------------------------------------
# Collector
# ---------------------------------------------------------------------------

class MetadataManager:
    """Collects metadata from an :class:`~core.experiment_runner.ExperimentResult`.

    Example::

        manager  = MetadataManager()
        metadata = manager.collect(result)
        print(metadata.to_dict())
    """

    def collect(self, result: ExperimentResult) -> ExperimentMetadata:
        """Extract and aggregate metadata from *result*.

        Args:
            result: A completed :class:`~core.experiment_runner.ExperimentResult`.

        Returns:
            A populated :class:`ExperimentMetadata`.
        """
        cfg = result.config_snapshot   # plain dict stored by the runner

        # ── Preprocessing metadata ───────────────────────────────────────
        pp_meta: Dict[str, Any] = {}
        if result.prepared_graph is not None:
            try:
                pp_meta = result.prepared_graph.metadata.to_dict()
            except Exception:  # noqa: BLE001
                pass   # metadata collection is best-effort

        metadata = ExperimentMetadata(
            experiment_id     = result.experiment_id,
            framework_version = _FRAMEWORK_VERSION,
            dataset_name      = result.dataset_name,
            dataset_root      = cfg.get("dataset_root", ""),
            experiment_status = result.status.value,
            started_at        = result.started_at,
            finished_at       = result.finished_at,
            runtime_seconds   = result.runtime_seconds,
            seed              = cfg.get("seed"),
            error_model_name  = cfg.get("error_model_name"),
            error_model_config= cfg.get("error_model_config", {}),
            analysis_names    = cfg.get("analysis_names", []),
            analysis_configs  = cfg.get("analysis_configs", {}),
            preprocessing_metadata = pp_meta,
            config_snapshot   = cfg,
            warnings          = list(result.warnings),
            errors            = list(result.errors),
            extra             = dict(result.extra),
        )

        logger.info(
            "[MetadataManager] Collected metadata for experiment '%s'.",
            result.experiment_id,
        )
        return metadata
