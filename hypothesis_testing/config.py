"""
Hypothesis Testing Configuration
=================================
Defines configuration containers and execution modes for hypothesis-testing
experiments comparing real connectomes against matched null models.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


class Condition(enum.Enum):
    """Experimental condition."""
    REAL = "real"
    NULL = "null"
    BOTH = "both"


class ExecutionMode(enum.Enum):
    """Pipeline execution mode.

    Modes:
        FULL:
            Execute experiments on both the Real connectome and Null ensemble,
            then run statistical comparisons and export results (default).
        NULL_ONLY:
            Execute experiments ONLY on the randomized Null ensemble, skipping
            expensive Real-graph re-runs, and export replicate-level observations
            for later comparison.
        COMPARE_EXISTING:
            Lightweight statistical comparison mode. Loads existing Real replicate
            observations and previously exported Null observations from disk,
            validates alignment, computes Welch's t-test and BH-FDR, and exports
            reports without loading or perturbing the connectome graph.
    """
    FULL = "full"
    NULL_ONLY = "null_only"
    COMPARE_EXISTING = "compare_existing"


@dataclass
class HypothesisExperimentConfig:
    """All configuration parameters required to run a hypothesis-testing experiment.

    Attributes:
        dataset_name:
            Name of the FlyWire connectome dataset (e.g. "BANC", "FAFB", "MANC", "TEST").
        dataset_root:
            Path to the directory containing dataset folders.
        configs_root:
            Path to the configs/ directory. Defaults to "configs/".
        execution_mode:
            ExecutionMode or string ("full", "null_only", "compare_existing").
            Defaults to ExecutionMode.FULL.
        run_real:
            Whether to execute the perturbation pipeline on the real connectome.
            (Auto-synced with execution_mode for backward compatibility).
        run_null:
            Whether to execute the perturbation pipeline on the randomized null graph.
            (Auto-synced with execution_mode for backward compatibility).
        compare_conditions:
            Whether to perform Real vs. Null statistical comparisons during run.
        real_results_path:
            Path to existing Real experiment results (CSV file, parquet, or historical
            results directory) for COMPARE_EXISTING mode.
        null_results_path:
            Path to existing Null experiment results (CSV file, parquet, or directory)
            for COMPARE_EXISTING mode.
        null_model_name:
            Identifier of the registered null model to use (default: "degree_preserving").
        null_model_config:
            Optional parameter overrides forwarded to the null model generator.
        error_model_names:
            List of error model names to evaluate (e.g. ["missed_synapses", "split_errors"]).
        error_rates:
            List of error rate floats to evaluate (e.g. [0.0, 0.05, 0.20]).
        random_seeds:
            Seeds controlling the *error-model* stochasticity for the REAL condition.
            Each seed produces one independent error-model trial on the real graph.
            For significance testing, use at least 3 seeds (recommended: 5).
        null_graph_seeds:
            Seeds controlling the *null graph generation* (topology randomisation).
            Each seed produces one independently rewired null graph; one error-model
            trial is run per null graph.  This is the primary source of null-network
            variance used in hypothesis testing.
            If None (default), falls back to list(random_seeds) — one null graph per
            real-condition seed (ensuring n_null == n_real).
        null_error_model_seeds:
            Seeds controlling the *error-model* stochasticity applied to each null
            graph.  If None (default), uses [random_seeds[0]] — one trial per null
            graph.
        analysis_names:
            List of registered graph analysis names to run (e.g. "basic_structure", "pagerank").
        analysis_configs:
            Optional per-analysis configuration dicts.
        preprocessing_config:
            Optional kwargs forwarded to preprocess_graph().
        output_root:
            Directory where hypothesis-testing results and comparison reports will be written.
        significance_level:
            Alpha threshold for statistical hypothesis testing (default: 0.05).
        fdr_method:
            Multiple-testing correction method (default: "fdr_bh" for Benjamini-Hochberg).
        extra:
            Free-form dictionary for additional metadata.
    """

    dataset_name: str
    dataset_root: str
    configs_root: str = "configs/"
    execution_mode: ExecutionMode | str = ExecutionMode.FULL
    run_real: bool = True
    run_null: bool = True
    compare_conditions: bool = True
    real_results_path: Optional[str] = None
    null_results_path: Optional[str] = None
    null_model_name: str = "degree_preserving"
    null_model_config: Dict[str, Any] = field(default_factory=dict)
    error_model_names: List[str] = field(default_factory=lambda: [
        "missed_synapses",
        "false_synapses",
        "synapse_count_measurement",
        "split_errors",
        "merge_errors",
    ])
    error_rates: List[float] = field(default_factory=lambda: [
        0.000, 0.005, 0.010, 0.020, 0.030,
        0.050, 0.075, 0.100, 0.150, 0.200,
    ])
    random_seeds: List[int] = field(default_factory=lambda: [1, 2, 3])
    null_graph_seeds: Optional[List[int]] = field(default_factory=lambda: [1])
    null_error_model_seeds: Optional[List[int]] = None
    analysis_names: List[str] = field(default_factory=lambda: [
        "basic_structure",
        "degree_distribution",
        "connected_components",
        "reciprocity",
        "pagerank",
    ])
    analysis_configs: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    preprocessing_config: Dict[str, Any] = field(default_factory=dict)
    output_root: str = "results/hypothesis_testing"
    significance_level: float = 0.05
    fdr_method: str = "fdr_bh"
    extra: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Normalize execution_mode
        if isinstance(self.execution_mode, str):
            norm = self.execution_mode.lower().strip()
            if norm in ("full", "both"):
                self.execution_mode = ExecutionMode.FULL
            elif norm in ("null_only", "null"):
                self.execution_mode = ExecutionMode.NULL_ONLY
            elif norm in ("compare_existing", "compare"):
                self.execution_mode = ExecutionMode.COMPARE_EXISTING
            else:
                raise ValueError(
                    f"[HypothesisExperimentConfig] Invalid execution_mode '{self.execution_mode}'. "
                    f"Must be one of: 'full', 'null_only', 'compare_existing'."
                )

        # Synchronize boolean flags with execution_mode for backward compatibility
        if self.execution_mode == ExecutionMode.NULL_ONLY:
            self.run_real = False
            self.run_null = True
            self.compare_conditions = False
        elif self.execution_mode == ExecutionMode.COMPARE_EXISTING:
            self.run_real = False
            self.run_null = False
            self.compare_conditions = True
        elif self.execution_mode == ExecutionMode.FULL:
            # Respect explicit run_real/run_null overrides if user passed them
            if not self.run_real and self.run_null:
                self.execution_mode = ExecutionMode.NULL_ONLY
                self.compare_conditions = False
            elif not self.run_real and not self.run_null:
                if self.real_results_path or self.null_results_path:
                    self.execution_mode = ExecutionMode.COMPARE_EXISTING
                    self.compare_conditions = True
                else:
                    raise ValueError(
                        "[HypothesisExperimentConfig] Both run_real and run_null are False, "
                        "but no real_results_path or null_results_path was provided for comparison."
                    )
            else:
                self.run_real = True
                self.run_null = True
                self.compare_conditions = True

        if self.execution_mode == ExecutionMode.COMPARE_EXISTING:
            if not self.real_results_path and not self.null_results_path:
                raise ValueError(
                    "[HypothesisExperimentConfig] COMPARE_EXISTING mode requires at least "
                    "real_results_path or null_results_path."
                )

        if self.execution_mode != ExecutionMode.COMPARE_EXISTING:
            if not self.error_model_names:
                raise ValueError(
                    "[HypothesisExperimentConfig] error_model_names cannot be empty."
                )
            if not self.error_rates:
                raise ValueError(
                    "[HypothesisExperimentConfig] error_rates cannot be empty."
                )
            if not self.random_seeds:
                raise ValueError(
                    "[HypothesisExperimentConfig] random_seeds cannot be empty."
                )

    @property
    def effective_null_graph_seeds(self) -> List[int]:
        """Resolved list of seeds used to generate independent null graphs.

        Returns null_graph_seeds if explicitly set; otherwise defaults to [1]
        for a single null graph topology. Set to [1, 2, 3] for 3 independent null graphs.
        """
        if self.null_graph_seeds is not None:
            return list(self.null_graph_seeds)
        return [1]

    @property
    def effective_null_error_seeds(self) -> List[int]:
        """Resolved list of error-model seeds applied to each null graph.

        Returns null_error_model_seeds if explicitly set; otherwise uses
        list(random_seeds) so that multiple perturbation trials are evaluated
        on each null graph topology.
        """
        if self.null_error_model_seeds is not None:
            return list(self.null_error_model_seeds)
        return list(self.random_seeds)


    @property
    def condition_mode(self) -> Condition:
        if self.run_real and self.run_null:
            return Condition.BOTH
        elif self.run_real:
            return Condition.REAL
        else:
            return Condition.NULL

