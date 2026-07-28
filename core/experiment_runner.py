"""
Phase 009 – Experiment Runner
==============================
Orchestrates the complete FlyWire experiment pipeline by coordinating all
previously implemented framework components.

The runner is a **pure orchestrator**: it calls public APIs from Phases
004–010 but never implements graph algorithms, perturbation logic, or
statistics.

Architecture (Version 3 igraph):
    - No ``graph.copy()`` anywhere.  The baseline igraph.Graph is immutable.
    - Error models return an ``ErrorResult`` containing ``edge_mask`` and
      ``weight_updates`` instead of a perturbed graph copy.
    - The runner builds a **temporary** igraph subgraph from the baseline +
      edge_mask for the duration of analysis, then deletes it immediately.
    - After all analysis, Statistics are computed and the Export Manager
      packages results.
    - A ``RuntimeMonitor`` records RAM + wall time.

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
    PreparedGraph  (immutable baseline — never modified)
            │
            ├──── Baseline Analyses (optional) ──────────────────────┐
            │                                                         │
            ├──── Error Model ────┐   (modules.error_models.registry) │
            │                    │                                    │
            │             ErrorResult (edge_mask + weight_updates)    │
            │                    │                                    │
            │      Build temp igraph subgraph from mask               │
            │                    │                                    │
            └──── Analyses ←─────┘   (modules.graph_analyses.registry)
                    │
                    ▼
            ExperimentResult → Statistics → Export → Delete temp graph
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

import igraph

from core.data_loader import load_dataset, FlyWireDataset
from core.graph_builder import GraphBuilder, GraphBuilderError
from modules.preprocessing import preprocess_graph, PreparedGraph, PreprocessingError
from modules.graph_analyses.analysis_registry import AnalysisRegistry
from modules.graph_analyses.analysis_result import AnalysisResult, AnalysisStatus
from modules.error_models.common.error_registry import ErrorRegistry
from modules.error_models.common.error_result import ErrorResult, ErrorModelStatus

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
            ``"MANC"``).
        dataset_root:
            Path to the directory that contains the dataset folders.
        configs_root:
            Path to the ``configs/`` directory (used for DatasetRegistry
            and ConfigManager).  Defaults to ``"configs/"``.
        error_model_name:
            Name of the error model to apply (must be registered in the
            :class:`~modules.error_models.error_registry.ErrorRegistry`).
            Pass ``None`` to run a baseline experiment with no perturbation.
        error_model_config:
            Configuration dict forwarded to the error model's ``execute()``
            call.  May be empty.
        analysis_names:
            Ordered list of analysis names to run after error model application.
        baseline_analysis_names:
            Optional ordered list of analysis names to run on the unperturbed
            baseline before the error model is applied.  Empty by default.
        analysis_configs:
            Optional per-analysis config dicts keyed by analysis name.
        preprocessing_config:
            Optional kwargs forwarded to :func:`~modules.preprocessing.preprocess_graph`.
        seed:
            Optional integer random seed forwarded to the error model.
        experiment_id:
            Optional human-readable identifier.  Auto-generated if omitted.
        output_root:
            Root directory for result export packages.  Pass ``None`` to
            disable automatic export.
        create_zip:
            Whether to create a ZIP archive of the export package.
        extra:
            Free-form metadata stored in the result but not used by the runner.
    """

    dataset_name: str
    dataset_root: str
    configs_root: str = "configs/"
    error_model_name: Optional[str] = None
    error_model_config: Dict[str, Any] = field(default_factory=dict)
    analysis_names: List[str] = field(default_factory=list)
    baseline_analysis_names: List[str] = field(default_factory=list)
    analysis_configs: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    preprocessing_config: Dict[str, Any] = field(default_factory=dict)
    seed: Optional[int] = None
    experiment_id: str = ""
    output_root: Optional[str] = None
    create_zip: bool = False
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

    Attributes:
        experiment_id:         Identifier copied from :class:`ExperimentConfig`.
        status:                Overall execution status.
        dataset_name:          Name of the dataset that was processed.
        config_snapshot:       Deep copy of the config used.
        prepared_graph:        The baseline :class:`~modules.preprocessing.PreparedGraph`.
        error_result:          :class:`~modules.error_models.ErrorResult` or
                               ``None`` for baseline runs.
        baseline_analysis_results: Analysis results on unperturbed baseline.
        analysis_results:      Ordered list of :class:`~modules.graph_analyses.AnalysisResult`.
        runtime_seconds:       Total wall-clock time for the complete pipeline.
        peak_ram_mb:           Peak RAM usage during the run (MB), if monitored.
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
    baseline_analysis_results: List[AnalysisResult] = field(default_factory=list)
    analysis_results: List[AnalysisResult] = field(default_factory=list)
    runtime_seconds: float = 0.0
    peak_ram_mb: float = 0.0
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
            "experiment_id":              self.experiment_id,
            "status":                     self.status.value,
            "dataset_name":               self.dataset_name,
            "runtime_seconds":            self.runtime_seconds,
            "peak_ram_mb":                self.peak_ram_mb,
            "started_at":                 self.started_at,
            "finished_at":                self.finished_at,
            "error_model":                self.error_result.model_name if self.error_result else None,
            "error_model_status":         self.error_result.status.value if self.error_result else None,
            "baseline_analyses":          [r.to_dict() for r in self.baseline_analysis_results],
            "analyses":                   [r.to_dict() for r in self.analysis_results],
            "warnings":                   self.warnings,
            "errors":                     self.errors,
            "extra":                      self.extra,
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
            singleton.
        error_registry:
            The :class:`~modules.error_models.error_registry.ErrorRegistry`
            singleton.
        graph_builder:
            Optional :class:`~core.graph_builder.GraphBuilder` instance.
            A default instance is created if not provided.
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

        # ── Auto-export (optional) ───────────────────────────────────────
        if config.output_root:
            self._step_export(config, result)

            # ── Release heavyweight graph reference ──────────────────────
            # PreparedGraph is no longer needed after export.
            # MetadataManager.collect() captured all serialisable metadata
            # (graph structure, preprocessing info) into ExperimentMetadata
            # before this point.  No framework component accesses
            # result.prepared_graph after export completes.
            result.prepared_graph = None

        return result

    # ------------------------------------------------------------------ #
    # Internal pipeline steps                                              #
    # ------------------------------------------------------------------ #

    def _run_pipeline(
        self, config: ExperimentConfig, result: ExperimentResult
    ) -> None:
        """Execute each pipeline step in order, aborting on fatal errors."""

        # ── Step 1: Load dataset ─────────────────────────────────────────
        dataset = self._step_load_dataset(config, result)
        if dataset is None:
            result.status = ExperimentStatus.FAILED
            return

        # ── Step 2: Build graph ──────────────────────────────────────────
        graph = self._step_build_graph(dataset, result)
        if graph is None:
            result.status = ExperimentStatus.FAILED
            return

        # Release the raw dataframes — graph holds all required data.
        del dataset

        # ── Step 3: Preprocess graph ─────────────────────────────────────
        prepared = self._step_preprocess(graph, config, result)
        if prepared is None:
            result.status = ExperimentStatus.FAILED
            return
        result.prepared_graph = prepared

        # ── Step 3.6: Biological Vulnerability (Phase 013) ───────────────
        from modules.error_models.common.biology import BiologicalAssumptions
        from modules.preprocessing.missed_synapses.vulnerability import VulnerabilityModel
        
        try:
            bio_assumptions = BiologicalAssumptions.from_config(config)
            vuln_model = VulnerabilityModel(assumptions=bio_assumptions)
            
            if prepared.edge_features is not None:
                vuln_table = vuln_model.compute_scores(prepared.edge_features)
                setattr(prepared, "edge_vulnerability", vuln_table)
        except Exception as exc:
            msg = f"Phase 013 Vulnerability Model failed: {exc}"
            logger.error("[ExperimentRunner] %s", msg)
            result.errors.append(msg)
            result.status = ExperimentStatus.FAILED
            return

        # ── Release edge_features after Phase 013 ────────────────────────
        # The vulnerability model and Phase 013 checkpoint (if configured)
        # have both consumed edge_features.  No downstream phase needs this
        # Polars DataFrame — calibration uses edge_vulnerability instead.
        if prepared.edge_features is not None:
            prepared.edge_features = None

        # ── Step 3.7: Probability Calibration (Phase 014) ────────────────
        from modules.error_models.common.calibration import ProbabilityCalibrator
        
        try:
            target_error_rate = float(config.error_model_config.get("error_rate", 0.0))
            # Optional calibration configs
            calibration_config = config.error_model_config.get("biology", {}).get("calibration", {})
            max_iter = int(calibration_config.get("max_iterations", 50))
            tol = float(calibration_config.get("tolerance", 1e-6))
            
            if hasattr(prepared, "edge_vulnerability"):
                calibrator = ProbabilityCalibrator(
                    target_error_rate=target_error_rate,
                    max_iterations=max_iter,
                    tolerance=tol
                )
                calibrated_table = calibrator.calibrate(prepared.edge_vulnerability)
                setattr(prepared, "calibrated_probabilities", calibrated_table)
        except Exception as exc:
            msg = f"Phase 014 Probability Calibration failed: {exc}"
            logger.error("[ExperimentRunner] %s", msg)
            result.errors.append(msg)
            result.status = ExperimentStatus.FAILED
            return

        # ── Release edge_vulnerability after Phase 014 ───────────────────
        # The calibrator and Phase 014 checkpoint have both consumed
        # edge_vulnerability.  Downstream phases use calibrated_probabilities.
        if hasattr(prepared, "edge_vulnerability"):
            prepared.edge_vulnerability = None

        # ── Step 4: Run baseline analyses (optional) ─────────────────────
        if config.baseline_analysis_names:
            self._step_run_baseline_analyses(prepared, config, result)

        # ── Step 5: Apply error model (optional) ─────────────────────────
        error_result: Optional[ErrorResult] = None

        if config.error_model_name:
            error_result = self._step_apply_error_model(prepared, config, result)
            result.error_result = error_result

            if error_result and error_result.status == ErrorModelStatus.FAILED:
                msg = (
                    f"Error model '{config.error_model_name}' failed; "
                    "running analyses on baseline graph."
                )
                logger.warning("[ExperimentRunner] %s", msg)
                result.warnings.append(msg)
                error_result = None  # fall back to baseline

        # ── Step 6: Build temporary analysis graph ───────────────────────
        # If an error model produced a mask or added_edges, build a
        # temporary subgraph.  Otherwise analyses run directly on the
        # immutable baseline graph.
        temp_graph: Optional[igraph.Graph] = None
        analysis_target: PreparedGraph = prepared   # default: baseline

        has_mask = (
            error_result is not None
            and error_result.edge_mask is not None
        )
        has_added_edges = (
            error_result is not None
            and len(error_result.added_edges) > 0
        )
        has_weight_perturbation = (
            error_result is not None
            and len(error_result.weight_updates) > 0
        )

        if has_mask or has_added_edges or has_weight_perturbation:
            temp_graph, temp_prepared = self._build_temp_graph(
                prepared, error_result, config, result
            )
            if temp_prepared is not None:
                analysis_target = temp_prepared

        # ── Release calibrated probabilities after error model ───────────
        # The error model consumed calibrated_probabilities during execute().
        # No downstream phase (analyses, statistics, export) needs them.
        if hasattr(prepared, "calibrated_probabilities"):
            prepared.calibrated_probabilities = None

        # ── Step 7: Run analyses ─────────────────────────────────────────
        if config.analysis_names:
            self._step_run_analyses(analysis_target, config, result)

        # ── Step 8: Destroy temporary graph immediately ──────────────────
        if temp_graph is not None:
            del temp_graph
            del analysis_target
            logger.debug(
                "[ExperimentRunner] Temporary perturbed graph released."
            )

        # ── Release edge_mask and weight_updates ─────────────────────────
        # These were consumed by _build_temp_graph to construct the temporary
        # subgraph.  Export and statistics only need perturbation_metadata
        # (separate field), not the full mask or weight updates.
        if error_result is not None:
            error_result.edge_mask = None
            error_result.weight_updates = {}

        # ── Release intermediate DataFrames from PreparedGraph ───────────
        # edge_features, edge_vulnerability, and calibrated_probabilities
        # were consumed during their respective pipeline steps.  They are
        # not accessed by analyses, statistics, or export.
        # (Already released calibrated_probabilities above.)
        if hasattr(prepared, "edge_vulnerability"):
            prepared.edge_vulnerability = None
        if hasattr(prepared, "edge_features"):
            prepared.edge_features = None

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
            dataset = load_dataset(
                config.dataset_name,
                config.dataset_root,
                configs_root=config.configs_root,
            )
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
    ) -> Optional[igraph.Graph]:
        """Delegate to :class:`~core.graph_builder.GraphBuilder`."""
        logger.info("[ExperimentRunner] Building graph.")
        try:
            graph = self._graph_builder.build(dataset)
            logger.info(
                "[ExperimentRunner] Graph built: %d nodes, %d edges.",
                graph.vcount(), graph.ecount(),
            )
            return graph
        except GraphBuilderError as exc:
            msg = f"Graph build failed: {exc}"
            logger.error("[ExperimentRunner] %s", msg)
            result.errors.append(msg)
            return None

    def _step_preprocess(
        self,
        graph: igraph.Graph,
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
                feature_config=pp_cfg.get("features"),
            )
            if not prepared.is_valid:
                msg = (
                    f"PreparedGraph for '{config.dataset_name}' has "
                    "validation errors (see validation_report for details)."
                )
                logger.warning("[ExperimentRunner] %s", msg)
                result.warnings.append(msg)
            return prepared
        except (PreprocessingError, TypeError) as exc:
            msg = f"Preprocessing failed: {exc}"
            logger.error("[ExperimentRunner] %s", msg)
            result.errors.append(msg)
            return None

    def _step_run_baseline_analyses(
        self,
        prepared: PreparedGraph,
        config: ExperimentConfig,
        result: ExperimentResult,
    ) -> None:
        """Run analyses on the unperturbed baseline graph."""
        logger.info(
            "[ExperimentRunner] Running %d baseline analysis/analyses.",
            len(config.baseline_analysis_names),
        )
        for name in config.baseline_analysis_names:
            a_result = self._run_single_analysis(
                name, prepared, config, result, is_baseline=True
            )
            result.baseline_analysis_results.append(a_result)

    def _step_apply_error_model(
        self,
        prepared: PreparedGraph,
        config: ExperimentConfig,
        result: ExperimentResult,
    ) -> Optional[ErrorResult]:
        """Instantiate and execute the configured error model.

        Returns an :class:`ErrorResult` containing ``edge_mask`` and
        ``weight_updates``.  The baseline graph is never touched.
        """
        name = config.error_model_name
        logger.info("[ExperimentRunner] Applying error model '%s'.", name)

        # ── Instantiate ──────────────────────────────────────────────────
        try:
            model = self._error_registry.instantiate(name)
        except Exception as exc:  # noqa: BLE001
            msg = f"Could not instantiate error model '{name}': {exc}"
            logger.error("[ExperimentRunner] %s", msg)
            result.errors.append(msg)
            return None

        # ── Execute ──────────────────────────────────────────────────────
        error_result: ErrorResult = model.execute(
            prepared,
            config=config.error_model_config,
            seed=config.seed,
        )
        return error_result

    def _build_temp_graph(
        self,
        prepared: PreparedGraph,
        error_result: ErrorResult,
        config: ExperimentConfig,
        result: ExperimentResult,
    ) -> tuple:
        """Build a temporary igraph subgraph from the baseline + perturbation.

        Supports two perturbation types:

        1. **Edge mask (missed-synapse style):**
           ``error_result.edge_mask`` — boolean list, ``True`` = keep edge.
           Creates a subgraph with only active edges via
           ``baseline.subgraph_edges(mask)``.

        2. **Added edges (false-synapse style):**
           ``error_result.added_edges`` — list of ``(pre_root_id,
           post_root_id, weight)`` tuples.  Creates a copy of the baseline
           via ``baseline.copy()`` and calls ``add_edges()``.

        Both perturbation types can coexist (e.g. a model that removes some
        edges and adds others).

        The baseline graph is **never** modified.

        Returns:
            ``(temp_graph, temp_PreparedGraph)`` on success, or
            ``(None, None)`` on failure.
        """
        logger.info("[ExperimentRunner] Building temporary perturbed subgraph.")

        try:
            baseline: igraph.Graph = prepared.graph
            mask: Optional[List[bool]] = error_result.edge_mask
            weight_updates: Dict[int, float] = error_result.weight_updates
            added_edges: List[tuple] = error_result.added_edges

            has_mask = mask is not None
            has_added = len(added_edges) > 0

            # ------------------------------------------------------------------
            # Build base temporary graph
            # ------------------------------------------------------------------
            # Common: build added_indices + added_edge_weights for any added_edges.
            added_indices_list: List[tuple] = []
            added_weights_list: List[int] = []
            if has_added:
                id_to_idx = prepared.lookup.id_to_idx
                for pre_rid, post_rid, weight in added_edges:
                    src = id_to_idx.get(pre_rid)
                    dst = id_to_idx.get(post_rid)
                    if src is not None and dst is not None:
                        added_indices_list.append((src, dst))
                        added_weights_list.append(int(weight))

            # Build base temporary graph based on the perturbation type.
            if has_mask and not has_added:
                # Missed-synapse style: subgraph from mask.
                active_edge_indices = [
                    i for i, active in enumerate(mask) if active
                ]
                temp_graph: igraph.Graph = baseline.subgraph_edges(
                    active_edge_indices, delete_vertices=False
                )

            elif has_added and not has_mask:
                # False-synapse style: copy + add_edges.
                temp_graph = baseline.copy()
                if added_indices_list:
                    temp_graph.add_edges(added_indices_list)

            elif has_mask and has_added:
                # Combined: apply mask first, then add edges.
                active_edge_indices = [
                    i for i, active in enumerate(mask) if active
                ]
                temp_graph = baseline.subgraph_edges(
                    active_edge_indices, delete_vertices=False
                )
                if added_indices_list:
                    temp_graph.add_edges(added_indices_list)

            else:
                # No perturbation — use baseline as-is.
                temp_graph = baseline  # type: ignore[unreachable]

            # ------------------------------------------------------------------
            # Apply weight updates (for all perturbation types)
            # ------------------------------------------------------------------
            has_weight_updates = len(weight_updates) > 0

            if has_weight_updates:
                # Weight-only perturbations (no mask, no added_edges) use the
                # baseline graph directly and must copy it to avoid mutation.
                if temp_graph is baseline:
                    temp_graph = baseline.copy()

                weight_attr = (
                    "syn_count"
                    if "syn_count" in temp_graph.edge_attributes()
                    else "weight"
                )
                if weight_attr in temp_graph.edge_attributes():
                    for edge_idx, new_weight in weight_updates.items():
                        if edge_idx < temp_graph.ecount():
                            temp_graph.es[edge_idx][weight_attr] = new_weight

            # ------------------------------------------------------------------
            # Set weight attributes for added edges
            # ------------------------------------------------------------------
            if added_weights_list:
                # The added edges are the last N edges in the temp graph.
                base_count = temp_graph.ecount() - len(added_weights_list)
                weight_attr = (
                    "syn_count"
                    if "syn_count" in temp_graph.edge_attributes()
                    else "weight"
                )
                for i, w in enumerate(added_weights_list):
                    edge_idx = base_count + i
                    if edge_idx < temp_graph.ecount():
                        temp_graph.es[edge_idx][weight_attr] = w

            # ------------------------------------------------------------------
            # Copy graph-level metadata so preprocessing works
            # ------------------------------------------------------------------
            for attr in baseline.attributes():
                temp_graph[attr] = baseline[attr]
            temp_graph["edge_count"] = temp_graph.ecount()
            temp_graph["node_count"] = temp_graph.vcount()

            # ------------------------------------------------------------------
            # Wrap in a PreparedGraph (lightweight — reuse baseline features)
            # ------------------------------------------------------------------
            temp_prepared = preprocess_graph(
                temp_graph,
                expected_node_attrs=config.preprocessing_config.get(
                    "expected_node_attrs"
                ),
                expected_edge_attrs=config.preprocessing_config.get(
                    "expected_edge_attrs"
                ),
                index_node_attrs=config.preprocessing_config.get(
                    "index_node_attrs"
                ),
                feature_config={
                    "indegree": False,
                    "outdegree": False,
                    "total_degree": False,
                    "pagerank": False,
                    "reciprocal_ratio": False,
                    "hub_neighbor_count": False,
                    "two_hop_size": False,
                },
            )
            temp_prepared.baseline_features = prepared.baseline_features

            return temp_graph, temp_prepared

        except Exception as exc:  # noqa: BLE001
            msg = (
                f"Failed to build temporary perturbed subgraph: {exc}. "
                "Analyses will run on baseline graph."
            )
            logger.warning("[ExperimentRunner] %s", msg)
            result.warnings.append(msg)
            return None, None

    def _step_run_analyses(
        self,
        target: PreparedGraph,
        config: ExperimentConfig,
        result: ExperimentResult,
    ) -> None:
        """Instantiate and execute each configured analysis in order."""
        for name in config.analysis_names:
            a_result = self._run_single_analysis(
                name, target, config, result, is_baseline=False
            )
            result.analysis_results.append(a_result)

    def _run_single_analysis(
        self,
        name: str,
        target: PreparedGraph,
        config: ExperimentConfig,
        result: ExperimentResult,
        *,
        is_baseline: bool,
    ) -> AnalysisResult:
        """Instantiate and run one analysis; return its result."""
        tag = "baseline " if is_baseline else ""
        logger.info("[ExperimentRunner] Running %sanalysis '%s'.", tag, name)

        # ── Instantiate ──────────────────────────────────────────────────
        try:
            analysis = self._analysis_registry.instantiate(name)
        except Exception as exc:  # noqa: BLE001
            msg = f"Could not instantiate analysis '{name}': {exc}"
            logger.error("[ExperimentRunner] %s", msg)
            result.errors.append(msg)
            return AnalysisResult(
                analysis_name=name,
                status=AnalysisStatus.FAILED,
                dataset_name=config.dataset_name,
                errors=[msg],
            )

        # ── Execute ──────────────────────────────────────────────────────
        a_config = config.analysis_configs.get(name, {})
        a_result: AnalysisResult = analysis.execute(target, config=a_config)

        if a_result.status == AnalysisStatus.FAILED:
            logger.warning(
                "[ExperimentRunner] Analysis '%s' failed: %s",
                name, a_result.errors,
            )
        return a_result

    def _step_export(
        self,
        config: ExperimentConfig,
        result: ExperimentResult,
    ) -> None:
        """Run Statistics + Export Manager and write result package to disk."""
        try:
            from core.statistics_engine import StatisticsEngine
            from core.metadata_manager import MetadataManager
            from core.export_manager import ExportManager

            stats    = StatisticsEngine().aggregate([result])
            metadata = MetadataManager().collect(result)
            package  = ExportManager().export(
                result=result,
                metadata=metadata,
                stats=stats,
                output_root=Path(config.output_root),
                create_zip=config.create_zip,
            )
            logger.info(
                "[ExperimentRunner] Export complete: %s", package.summary()
            )
        except Exception as exc:  # noqa: BLE001
            msg = f"Export failed: {exc}"
            logger.warning("[ExperimentRunner] %s", msg)
            result.warnings.append(msg)

    # ------------------------------------------------------------------ #
    # Repr                                                                 #
    # ------------------------------------------------------------------ #

    def __repr__(self) -> str:
        return (
            f"ExperimentRunner("
            f"analyses={self._analysis_registry.list_names()}, "
            f"error_models={self._error_registry.list_names()})"
        )
