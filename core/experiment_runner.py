"""
Phase 009 – Experiment Runner
==============================
Orchestrates the complete FlyWire experiment pipeline by coordinating all
previously implemented framework components.

The runner is a **pure orchestrator**: it calls public APIs from Phases
004–008 but never implements graph algorithms, perturbation logic, or
statistics.

Execution pipeline::

    ExperimentConfig
            │
            ▼
    Data Loader            (core.data_loader.load_dataset)
            │
            ▼
    Graph Builder          (core.graph_builder.GraphBuilder)
            │
            ▼
    Preprocessing          (modules.preprocessing.preprocess_graph)
            │
            ▼
    PreparedGraph
            │
            ├──── Error Model ────┐   (modules.error_models.registry)
            │                    │
            │             Perturbed Graph
            │                    │
            │             Preprocessing  (optional second pass)
            │                    │
            └──── Analyses ←─────┘   (modules.graph_analyses.registry)
                    │
                    ▼
            ExperimentResult

Usage::

    from core.experiment_runner import ExperimentRunner, ExperimentConfig
    from modules.graph_analyses import registry as analysis_registry
    from modules.error_models  import registry as error_registry

    config = ExperimentConfig(
        dataset_name="FAFB",
        dataset_root="/data/flywire",
        error_model_name="missed_synapses",
        error_model_config={"removal_rate": 0.05},
        analysis_names=["degree", "centrality"],
        seed=42,
    )

    runner = ExperimentRunner(
        analysis_registry=analysis_registry,
        error_registry=error_registry,
    )
    result = runner.run(config)
"""

from __future__ import annotations

import copy
import datetime
import enum
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.data_loader import load_dataset, FlyWireDataset
from core.graph_builder import GraphBuilder, GraphBuilderError
from modules.preprocessing import preprocess_graph, PreparedGraph, PreprocessingError
from modules.graph_analyses.analysis_registry import AnalysisRegistry
from modules.graph_analyses.analysis_result import AnalysisResult, AnalysisStatus
from modules.error_models.error_registry import ErrorRegistry
from modules.error_models.error_result import ErrorResult, ErrorModelStatus

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Experiment Configuration
# ---------------------------------------------------------------------------

@dataclass
class ExperimentConfig:
    """All inputs required to run one experiment.

    The Experiment Runner accepts only this object — users never manually
    construct graphs, datasets, or analysis instances.

    Attributes:
        dataset_name:
            Name of the FlyWire dataset to load (e.g. ``"FAFB"``,
            ``"MANC"``).  Passed verbatim to :func:`~core.data_loader.load_dataset`.
        dataset_root:
            Path to the directory that contains the dataset folders.
        error_model_name:
            Name of the error model to apply (must be registered in the
            :class:`~modules.error_models.error_registry.ErrorRegistry`).
            Pass ``None`` to run a baseline experiment with no perturbation.
        error_model_config:
            Configuration dict forwarded to the error model's ``execute()``
            call.  May be empty.
        analysis_names:
            Ordered list of analysis names to run (must all be registered in
            the :class:`~modules.graph_analyses.analysis_registry.AnalysisRegistry`).
            Each analysis runs after the perturbation step.
        analysis_configs:
            Optional per-analysis config dicts keyed by analysis name.
            Analyses not listed here receive an empty dict.
        preprocessing_config:
            Optional kwargs forwarded to :func:`~modules.preprocessing.preprocess_graph`
            (e.g. ``{"expected_edge_attrs": ["syn_count"], "raise_on_error": True}``).
        seed:
            Optional integer random seed forwarded to the error model for
            reproducibility.
        experiment_id:
            Optional human-readable identifier for this experiment.  If not
            provided, a timestamp-based ID is generated automatically.
        extra:
            Free-form metadata stored in the result but not used by the runner.
    """

    dataset_name: str
    dataset_root: str
    error_model_name: Optional[str] = None
    error_model_config: Dict[str, Any] = field(default_factory=dict)
    analysis_names: List[str] = field(default_factory=list)
    analysis_configs: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    preprocessing_config: Dict[str, Any] = field(default_factory=dict)
    seed: Optional[int] = None
    experiment_id: str = ""
    extra: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.experiment_id:
            ts = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
            self.experiment_id = f"{self.dataset_name}_{ts}"


# ---------------------------------------------------------------------------
# Experiment Status
# ---------------------------------------------------------------------------

class ExperimentStatus(enum.Enum):
    """Overall status of a completed experiment run."""
    SUCCESS  = "SUCCESS"
    FAILED   = "FAILED"
    PARTIAL  = "PARTIAL"   # some analyses failed but others succeeded


# ---------------------------------------------------------------------------
# Experiment Result
# ---------------------------------------------------------------------------

@dataclass
class ExperimentResult:
    """Orchestration output of a single experiment run.

    Consumed downstream by Phase 010 (Statistics Engine + Export Manager).
    Neither phase should need to know how the results were produced.

    Attributes:
        experiment_id:         Identifier copied from :class:`ExperimentConfig`.
        status:                Overall execution status.
        dataset_name:          Name of the dataset that was processed.
        config_snapshot:       Deep copy of the config used.
        prepared_graph:        The baseline :class:`~modules.preprocessing.PreparedGraph`.
        error_result:          :class:`~modules.error_models.ErrorResult` or
                               ``None`` for baseline runs.
        analysis_results:      Ordered list of :class:`~modules.graph_analyses.AnalysisResult`.
        runtime_seconds:       Total wall-clock time for the complete pipeline.
        started_at:            ISO-8601 UTC timestamp when the run began.
        finished_at:           ISO-8601 UTC timestamp when the run ended.
        warnings:              Non-fatal warnings from the pipeline.
        errors:                Error messages from failed pipeline steps.
        extra:                 Forwarded from :class:`ExperimentConfig`.
    """

    experiment_id: str
    status: ExperimentStatus = ExperimentStatus.SUCCESS
    dataset_name: str = ""
    config_snapshot: Dict[str, Any] = field(default_factory=dict)
    prepared_graph: Optional[PreparedGraph] = None
    error_result: Optional[ErrorResult] = None
    analysis_results: List[AnalysisResult] = field(default_factory=list)
    runtime_seconds: float = 0.0
    started_at: str = ""
    finished_at: str = ""
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    extra: Dict[str, Any] = field(default_factory=dict)

    # ------------------------------------------------------------------ #
    # Convenience helpers                                                  #
    # ------------------------------------------------------------------ #

    @property
    def succeeded(self) -> bool:
        """``True`` iff overall status is ``SUCCESS``."""
        return self.status == ExperimentStatus.SUCCESS

    @property
    def successful_analyses(self) -> List[AnalysisResult]:
        """Return only analysis results with status ``SUCCESS``."""
        return [r for r in self.analysis_results if r.status == AnalysisStatus.SUCCESS]

    @property
    def failed_analyses(self) -> List[AnalysisResult]:
        """Return only analysis results with status ``FAILED``."""
        return [r for r in self.analysis_results if r.status == AnalysisStatus.FAILED]

    def to_dict(self) -> Dict[str, Any]:
        """Return a serialisable summary (omits graph objects)."""
        return {
            "experiment_id":    self.experiment_id,
            "status":           self.status.value,
            "dataset_name":     self.dataset_name,
            "runtime_seconds":  self.runtime_seconds,
            "started_at":       self.started_at,
            "finished_at":      self.finished_at,
            "error_model":      self.error_result.model_name if self.error_result else None,
            "error_model_status": self.error_result.status.value if self.error_result else None,
            "analyses":         [r.to_dict() for r in self.analysis_results],
            "warnings":         self.warnings,
            "errors":           self.errors,
            "extra":            self.extra,
        }

    def summary(self) -> str:
        """Return a compact one-liner for logging."""
        return (
            f"ExperimentResult(id={self.experiment_id!r}, "
            f"status={self.status.value}, "
            f"analyses={len(self.analysis_results)}, "
            f"runtime={self.runtime_seconds:.2f}s)"
        )

    def __repr__(self) -> str:
        return self.summary()


# ---------------------------------------------------------------------------
# Experiment Runner
# ---------------------------------------------------------------------------

class ExperimentRunner:
    """Orchestrates the complete FlyWire experiment pipeline.

    The runner is stateless with respect to experiments — every call to
    :meth:`run` is independent.  It holds only references to the registries
    and the graph builder.

    Args:
        analysis_registry:
            The :class:`~modules.graph_analyses.analysis_registry.AnalysisRegistry`
            singleton.  Import from ``modules.graph_analyses``.
        error_registry:
            The :class:`~modules.error_models.error_registry.ErrorRegistry`
            singleton.  Import from ``modules.error_models``.
        graph_builder:
            Optional :class:`~core.graph_builder.GraphBuilder` instance.
            A default instance is created if not provided.

    Example::

        from core.experiment_runner import ExperimentRunner, ExperimentConfig
        from modules.graph_analyses import registry as a_reg
        from modules.error_models  import registry as e_reg

        runner = ExperimentRunner(analysis_registry=a_reg, error_registry=e_reg)
        result = runner.run(config)
    """

    def __init__(
        self,
        analysis_registry: AnalysisRegistry,
        error_registry: ErrorRegistry,
        graph_builder: Optional[GraphBuilder] = None,
    ) -> None:
        self._analysis_registry = analysis_registry
        self._error_registry    = error_registry
        self._graph_builder     = graph_builder or GraphBuilder()

    # ------------------------------------------------------------------ #
    # Public entry-point                                                   #
    # ------------------------------------------------------------------ #

    def run(self, config: ExperimentConfig) -> ExperimentResult:
        """Execute the full experiment pipeline defined by *config*.

        Args:
            config: A fully populated :class:`ExperimentConfig`.

        Returns:
            An :class:`ExperimentResult` containing every pipeline output.
            The runner never raises — failures are captured in
            ``result.errors`` and ``result.status``.
        """
        started_at = datetime.datetime.utcnow().isoformat() + "Z"
        t_start    = time.perf_counter()

        logger.info(
            "[ExperimentRunner] Starting experiment '%s' | dataset=%s "
            "error_model=%s analyses=%s",
            config.experiment_id,
            config.dataset_name,
            config.error_model_name or "None (baseline)",
            config.analysis_names,
        )

        result = ExperimentResult(
            experiment_id=config.experiment_id,
            dataset_name=config.dataset_name,
            config_snapshot=copy.deepcopy(vars(config)),
            started_at=started_at,
            extra=copy.copy(config.extra),
        )

        try:
            self._run_pipeline(config, result)
        except Exception as exc:  # noqa: BLE001
            result.status = ExperimentStatus.FAILED
            result.errors.append(f"Unexpected runner failure: {exc}")
            logger.exception(
                "[ExperimentRunner] Unhandled error in experiment '%s': %s",
                config.experiment_id, exc,
            )

        # Finalise runtime and status.
        result.runtime_seconds = time.perf_counter() - t_start
        result.finished_at     = datetime.datetime.utcnow().isoformat() + "Z"

        if result.status == ExperimentStatus.SUCCESS and result.failed_analyses:
            result.status = ExperimentStatus.PARTIAL

        logger.info(
            "[ExperimentRunner] Finished. %s",
            result.summary(),
        )

        return result

    # ------------------------------------------------------------------ #
    # Internal pipeline steps                                              #
    # ------------------------------------------------------------------ #

    def _run_pipeline(
        self, config: ExperimentConfig, result: ExperimentResult
    ) -> None:
        """Execute each pipeline step in order, aborting on fatal errors."""

        # ── Step 1: Load dataset ────────────────────────────────────────
        dataset = self._step_load_dataset(config, result)
        if dataset is None:
            result.status = ExperimentStatus.FAILED
            return

        # ── Step 2: Build graph ─────────────────────────────────────────
        graph = self._step_build_graph(dataset, result)
        if graph is None:
            result.status = ExperimentStatus.FAILED
            return

        # ── Step 3: Preprocess graph ────────────────────────────────────
        prepared = self._step_preprocess(graph, config, result)
        if prepared is None:
            result.status = ExperimentStatus.FAILED
            return
        result.prepared_graph = prepared

        # ── Step 4: Apply error model (optional) ────────────────────────
        analysis_target: PreparedGraph = prepared   # default: baseline

        if config.error_model_name:
            error_result, perturbed = self._step_apply_error_model(
                prepared, config, result
            )
            result.error_result = error_result

            if perturbed is not None:
                analysis_target = perturbed          # analyses run on perturbed graph
            elif error_result and error_result.status == ErrorModelStatus.FAILED:
                # Non-fatal: log, warn, fall back to baseline.
                msg = (
                    f"Error model '{config.error_model_name}' failed; "
                    "running analyses on baseline graph."
                )
                logger.warning("[ExperimentRunner] %s", msg)
                result.warnings.append(msg)

        # ── Step 5: Run analyses ────────────────────────────────────────
        if config.analysis_names:
            self._step_run_analyses(analysis_target, config, result)

        # Mark success only if we reach here without a FAILED status set
        # by an earlier step.
        if result.status == ExperimentStatus.SUCCESS:
            pass   # status already correct; partial detection happens in run()

    # ------------------------------------------------------------------ #
    # Step implementations                                                 #
    # ------------------------------------------------------------------ #

    def _step_load_dataset(
        self,
        config: ExperimentConfig,
        result: ExperimentResult,
    ) -> Optional[FlyWireDataset]:
        """Delegate to :func:`~core.data_loader.load_dataset`."""
        logger.info(
            "[ExperimentRunner] Loading dataset '%s' from '%s'.",
            config.dataset_name, config.dataset_root,
        )
        try:
            dataset = load_dataset(config.dataset_name, config.dataset_root)
            logger.info(
                "[ExperimentRunner] Dataset loaded: %d neurons, %d connections.",
                len(dataset.neurons), len(dataset.connections),
            )
            return dataset
        except Exception as exc:  # noqa: BLE001
            msg = f"Dataset load failed for '{config.dataset_name}': {exc}"
            logger.error("[ExperimentRunner] %s", msg)
            result.errors.append(msg)
            return None

    def _step_build_graph(
        self,
        dataset: FlyWireDataset,
        result: ExperimentResult,
    ) -> Optional[Any]:
        """Delegate to :class:`~core.graph_builder.GraphBuilder`."""
        logger.info("[ExperimentRunner] Building graph.")
        try:
            graph = self._graph_builder.build(dataset)
            logger.info(
                "[ExperimentRunner] Graph built: %d nodes, %d edges.",
                graph.number_of_nodes(), graph.number_of_edges(),
            )
            return graph
        except GraphBuilderError as exc:
            msg = f"Graph build failed: {exc}"
            logger.error("[ExperimentRunner] %s", msg)
            result.errors.append(msg)
            return None

    def _step_preprocess(
        self,
        graph: Any,
        config: ExperimentConfig,
        result: ExperimentResult,
    ) -> Optional[PreparedGraph]:
        """Delegate to :func:`~modules.preprocessing.preprocess_graph`."""
        logger.info("[ExperimentRunner] Preprocessing graph.")
        try:
            pp_cfg = config.preprocessing_config
            prepared = preprocess_graph(
                graph,
                expected_node_attrs=pp_cfg.get("expected_node_attrs"),
                expected_edge_attrs=pp_cfg.get("expected_edge_attrs"),
                index_node_attrs=pp_cfg.get("index_node_attrs"),
                raise_on_error=pp_cfg.get("raise_on_error", False),
            )
            if not prepared.is_valid:
                msg = (
                    f"PreparedGraph for '{config.dataset_name}' has "
                    "validation errors (see validation_report for details)."
                )
                logger.warning("[ExperimentRunner] %s", msg)
                result.warnings.append(msg)
            return prepared
        except PreprocessingError as exc:
            msg = f"Preprocessing failed: {exc}"
            logger.error("[ExperimentRunner] %s", msg)
            result.errors.append(msg)
            return None

    def _step_apply_error_model(
        self,
        prepared: PreparedGraph,
        config: ExperimentConfig,
        result: ExperimentResult,
    ) -> tuple:
        """Instantiate and execute the configured error model.

        Returns:
            ``(ErrorResult, perturbed PreparedGraph | None)``
        """
        name = config.error_model_name
        logger.info("[ExperimentRunner] Applying error model '%s'.", name)

        # ── Instantiate ─────────────────────────────────────────────────
        try:
            model = self._error_registry.instantiate(name)
        except Exception as exc:  # noqa: BLE001
            msg = f"Could not instantiate error model '{name}': {exc}"
            logger.error("[ExperimentRunner] %s", msg)
            result.errors.append(msg)
            return None, None

        # ── Execute ─────────────────────────────────────────────────────
        error_result: ErrorResult = model.execute(
            prepared,
            config=config.error_model_config,
            seed=config.seed,
        )

        if error_result.status != ErrorModelStatus.SUCCESS:
            return error_result, None

        # ── Preprocess the perturbed graph ───────────────────────────────
        # The perturbed graph is a raw nx.DiGraph; wrap it in a PreparedGraph
        # so that analyses always receive the full framework contract.
        try:
            perturbed_prepared = preprocess_graph(
                error_result.perturbed_graph,
                # Inherit the same preprocessing config as the baseline.
                expected_node_attrs=config.preprocessing_config.get(
                    "expected_node_attrs"
                ),
                expected_edge_attrs=config.preprocessing_config.get(
                    "expected_edge_attrs"
                ),
                index_node_attrs=config.preprocessing_config.get(
                    "index_node_attrs"
                ),
            )
        except Exception as exc:  # noqa: BLE001
            msg = (
                f"Preprocessing of perturbed graph failed: {exc}. "
                "Analyses will run on baseline graph."
            )
            logger.warning("[ExperimentRunner] %s", msg)
            result.warnings.append(msg)
            return error_result, None

        return error_result, perturbed_prepared

    def _step_run_analyses(
        self,
        target: PreparedGraph,
        config: ExperimentConfig,
        result: ExperimentResult,
    ) -> None:
        """Instantiate and execute each configured analysis in order."""
        for name in config.analysis_names:
            logger.info("[ExperimentRunner] Running analysis '%s'.", name)

            # ── Instantiate ──────────────────────────────────────────────
            try:
                analysis = self._analysis_registry.instantiate(name)
            except Exception as exc:  # noqa: BLE001
                msg = f"Could not instantiate analysis '{name}': {exc}"
                logger.error("[ExperimentRunner] %s", msg)
                result.errors.append(msg)
                # Record a failed placeholder so the caller knows this ran.
                placeholder = AnalysisResult(
                    analysis_name=name,
                    status=AnalysisStatus.FAILED,
                    dataset_name=config.dataset_name,
                    errors=[msg],
                )
                result.analysis_results.append(placeholder)
                continue

            # ── Execute ──────────────────────────────────────────────────
            a_config = config.analysis_configs.get(name, {})
            a_result: AnalysisResult = analysis.execute(target, config=a_config)
            result.analysis_results.append(a_result)

            if a_result.status == AnalysisStatus.FAILED:
                logger.warning(
                    "[ExperimentRunner] Analysis '%s' failed: %s",
                    name, a_result.errors,
                )

    # ------------------------------------------------------------------ #
    # Repr                                                                 #
    # ------------------------------------------------------------------ #

    def __repr__(self) -> str:
        return (
            f"ExperimentRunner("
            f"analyses={self._analysis_registry.list_names()}, "
            f"error_models={self._error_registry.list_names()})"
        )
