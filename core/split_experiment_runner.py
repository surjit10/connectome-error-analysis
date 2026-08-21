"""
EM4 – Split Experiment Runner
===============================
Dedicated execution pipeline for topology-changing error models (EM4 split
errors) that require temporary fragment vertices.

Architecture (per ``docs/error model/em4/em4 integration report.md``):

    - EM4 must **not** use :class:`~core.experiment_runner.ExperimentRunner`.
    - This runner mirrors the execution flow of ``ExperimentRunner`` but
      implements an independent temporary graph construction stage,
      :meth:`_split_build_temp_graph`, that supports temporary fragment
      vertices and extended lookup tables.
    - :meth:`_split_build_temp_graph` is private to this runner, responsible
      only for EM4, and is **guaranteed to never modify the baseline
      :class:`PreparedGraph`** or its ``lookup``.
    - ``ExperimentRunner._build_temp_graph`` remains completely untouched and
      continues to serve EM1–EM3.

Execution pipeline::

    SplitExperimentRunner.run(ExperimentConfig)
            │
            ▼
    Data Loader → Graph Builder → Preprocessing → PreparedGraph (immutable)
            │
            ▼
    Error Model "split_errors" (registry) → ErrorResult
            │                                 │ extra["split_plan"]
            ▼                                 ▼
    _split_build_temp_graph()  ─────────────► temp igraph + temp lookup
            │
            ▼
    Existing analyses (AnalysisRegistry) → ExperimentResult
            │
            ▼
    StatisticsEngine → ExportManager

Design notes:
    - Reuses the shared :class:`ExperimentConfig` / :class:`ExperimentResult`
      / :class:`ExperimentStatus` contracts from ``core.experiment_runner``
      (imported, never modified), so the existing Statistics Engine, Metadata
      Manager and Export Manager consume EM4 results unchanged.
    - The runner composes the shared ``ExperimentRunner`` step implementations
      (dataset load, graph build, preprocess, analyses, export) without
      modifying them, while the pipeline orchestration excludes the
      EM1-specific biological vulnerability / probability calibration phases
      (EM4's methodology has no dependency on them) and routes temporary
      graph construction through :meth:`_split_build_temp_graph`.
"""

from __future__ import annotations

import copy
import datetime
import logging
import time
from typing import Any, Dict, List, Optional

import igraph

from core.experiment_runner import (
    ExperimentConfig,
    ExperimentResult,
    ExperimentStatus,
)
from modules.error_models.common.error_result import ErrorModelStatus
from modules.preprocessing import preprocess_graph

logger = logging.getLogger(__name__)


class SplitExperimentRunner:
    """Dedicated execution pipeline for EM4 (split errors).

    Mirrors the orchestration of
    :class:`~core.experiment_runner.ExperimentRunner` but owns its temporary
    graph construction so that fragment vertices never leak into the shared
    EM1–EM3 path.

    Args:
        analysis_registry:
            The :class:`~modules.graph_analyses.analysis_registry.AnalysisRegistry`
            singleton.
        error_registry:
            The :class:`~modules.error_models.error_registry.ErrorRegistry`
            singleton.
        graph_builder:
            Optional :class:`~core.graph_builder.GraphBuilder` instance.
    """

    def __init__(
        self,
        analysis_registry: Any,
        error_registry: Any,
        graph_builder: Optional[Any] = None,
    ) -> None:
        # Compose (never modify) the shared ExperimentRunner step logic.
        from core.experiment_runner import ExperimentRunner

        self._runner = ExperimentRunner(
            analysis_registry=analysis_registry,
            error_registry=error_registry,
            graph_builder=graph_builder,
        )
        self._analysis_registry = analysis_registry
        self._error_registry = error_registry

    # ------------------------------------------------------------------ #
    # Public entry-point                                                   #
    # ------------------------------------------------------------------ #

    def run(self, config: ExperimentConfig) -> ExperimentResult:
        """Execute the full EM4 experiment pipeline defined by *config*.

        Returns an :class:`ExperimentResult` in exactly the same format the
        shared runner produces, so the existing statistics / export pipeline
        consumes it unchanged.
        """
        started_at = datetime.datetime.utcnow().isoformat() + "Z"
        t_start = time.perf_counter()

        logger.info(
            "[SplitExperimentRunner] Starting experiment '%s' | dataset=%s "
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
                "[SplitExperimentRunner] Unhandled error in experiment '%s': %s",
                config.experiment_id, exc,
            )

        result.runtime_seconds = time.perf_counter() - t_start
        result.finished_at = datetime.datetime.utcnow().isoformat() + "Z"

        if result.status == ExperimentStatus.SUCCESS and result.failed_analyses:
            result.status = ExperimentStatus.PARTIAL

        logger.info("[SplitExperimentRunner] Finished. %s", result.summary())

        # ── Auto-export (optional) — identical semantics to ExperimentRunner
        if config.output_root:
            self._runner._step_export(config, result)  # noqa: SLF001
            # Release heavyweight graph reference after export.
            result.prepared_graph = None

        return result

    # ------------------------------------------------------------------ #
    # Internal pipeline steps                                              #
    # ------------------------------------------------------------------ #

    def _run_pipeline(
        self, config: ExperimentConfig, result: ExperimentResult
    ) -> None:
        """Execute each EM4 pipeline step in order, aborting on fatal errors.

        Mirrors ``ExperimentRunner._run_pipeline`` but:
          - omits the EM1-specific biological vulnerability / probability
            calibration phases (no dependency in EM4's methodology);
          - builds the temporary graph via :meth:`_split_build_temp_graph`.
        """

        # ── Step 1: Load dataset ─────────────────────────────────────────
        dataset = self._runner._step_load_dataset(config, result)  # noqa: SLF001
        if dataset is None:
            result.status = ExperimentStatus.FAILED
            return

        # ── Step 2: Build graph ──────────────────────────────────────────
        graph = self._runner._step_build_graph(dataset, result)  # noqa: SLF001
        if graph is None:
            result.status = ExperimentStatus.FAILED
            return

        del dataset

        # ── Step 3: Preprocess graph ─────────────────────────────────────
        prepared = self._runner._step_preprocess(graph, config, result)  # noqa: SLF001
        if prepared is None:
            result.status = ExperimentStatus.FAILED
            return
        result.prepared_graph = prepared

        # ── Step 4: Baseline analyses (optional) ─────────────────────────
        if config.baseline_analysis_names:
            self._runner._step_run_baseline_analyses(  # noqa: SLF001
                prepared, config, result
            )

        # ── Step 5: Apply error model (optional) ─────────────────────────
        error_result = None
        if config.error_model_name:
            error_result = self._runner._step_apply_error_model(  # noqa: SLF001
                prepared, config, result
            )
            result.error_result = error_result
            if (
                error_result
                and error_result.status == ErrorModelStatus.FAILED
            ):
                err_details = "; ".join(error_result.errors) if error_result.errors else "Unknown error"
                msg = (
                    f"Error model '{config.error_model_name}' failed: {err_details}. "
                    "Execution aborted to prevent generating invalid baseline-fallback results."
                )
                logger.error("[SplitExperimentRunner] %s", msg)
                result.errors.append(msg)
                raise RuntimeError(msg)

        # ── Step 6: Build temporary split graph (EM4-specific) ───────────
        temp_graph: Optional[igraph.Graph] = None
        analysis_target: Any = prepared

        split_plan = None
        if error_result is not None:
            split_plan = (error_result.extra or {}).get("split_plan")

        if split_plan:
            temp_graph, temp_prepared = self._split_build_temp_graph(
                prepared, error_result, config, result
            )
            if temp_prepared is not None:
                analysis_target = temp_prepared

        # ── Step 7: Run analyses ─────────────────────────────────────────
        if config.analysis_names:
            self._runner._step_run_analyses(  # noqa: SLF001
                analysis_target, config, result
            )

        # ── Step 7.5: EM4 PageRank alignment (isolated, EM4-only) ───────
        # EM4 deletes parent vertices, so temp-graph vectors live in a
        # different vertex-index space than the baseline vectors.  The shared
        # comparison pipeline (StatisticsEngine / VectorComparisonRegistry)
        # compares vectors positionally, which collapses Pearson/Spearman and
        # Top-K overlap.  Rebuild the PageRank vector in baseline ordering
        # here — entirely inside EM4 — before any temporary mapping is
        # destroyed, then clean up exactly as before (the split_plan pop
        # below is unchanged).  The shared framework never sees the alignment.
        if temp_graph is not None:
            self._align_pagerank_vector(result, prepared, split_plan, temp_graph)

        # ── Step 8: Destroy temporary graph immediately ──────────────────
        if temp_graph is not None:
            del temp_graph
            del analysis_target
            logger.debug(
                "[SplitExperimentRunner] Temporary split graph released."
            )

        # Release the transient split plan (only needed for temp construction).
        if error_result is not None and error_result.extra:
            error_result.extra.pop("split_plan", None)

    # ------------------------------------------------------------------ #
    # EM4-only vector alignment (isolated stage)                            #
    # ------------------------------------------------------------------ #

    def _align_pagerank_vector(
        self,
        result: ExperimentResult,
        prepared: Any,
        split_plan: Dict[Any, Dict[str, Any]],
        temp_graph: igraph.Graph,
    ) -> None:
        """Replace the PageRank vector in EM4 analysis results with one
        aligned to the baseline vertex ordering.

        Called immediately after analyses complete and before the temporary
        graph is destroyed.  Only the ``pagerank_scores`` metric of the
        ``pagerank`` analysis is touched; every other metric continues to
        flow through the existing pipeline untouched.

        All logic lives in the EM4-only helper
        :mod:`core.split_vector_alignment`; the shared framework modules are
        never modified and never learn that alignment occurred.
        """
        if not split_plan:
            return

        from core.split_vector_alignment import (
            align_pagerank_vectors,
            build_baseline_order,
            build_split_parents,
            build_temp_root_to_index,
        )

        baseline_order = build_baseline_order(
            prepared.lookup.id_map, prepared.graph.vcount()
        )
        temp_root_to_index = build_temp_root_to_index(temp_graph)
        split_parents = build_split_parents(split_plan)

        for a_res in result.analysis_results:
            if a_res.analysis_name != "pagerank":
                continue
            vector = a_res.metrics.get("pagerank_scores")
            if vector is None:
                continue
            aligned = align_pagerank_vectors(
                list(vector),
                baseline_order,
                temp_root_to_index,
                split_parents,
            )
            a_res.metrics["pagerank_scores"] = aligned
            logger.info(
                "[SplitExperimentRunner] Aligned pagerank_scores to baseline "
                "ordering: %d -> %d entries (%d split neurons aggregated).",
                len(vector), len(aligned), len(split_plan),
            )

    # ------------------------------------------------------------------ #
    # EM4-specific temporary graph construction (isolated stage)            #
    # ------------------------------------------------------------------ #

    def _split_build_temp_graph(
        self,
        prepared: Any,
        error_result: Any,
        config: ExperimentConfig,
        result: ExperimentResult,
    ) -> tuple:
        """Build a temporary igraph with fragment vertices from the split plan.

        **Isolated EM4 stage.**  This function is private to
        :class:`SplitExperimentRunner` and is the only component allowed to
        create temporary fragment vertices.  It:

          - copies the baseline igraph (the baseline is never modified);
          - for every split neuron, replaces the neuron by two fragment
            vertices (synthetic negative root IDs) and rewires every incident
            edge exactly once to the fragment of its partner, preserving all
            edge attributes (synapse counts are unchanged);
          - deletes the original neuron vertices and rebuilds the temporary
            ``id_to_idx`` / ``id_map`` lookup tables from the temp graph;
          - wraps the temp graph in a fresh ``PreparedGraph`` with feature
            extraction disabled (identical to ``ExperimentRunner``'s temp
            graph strategy).

        Returns:
            ``(temp_graph, temp_PreparedGraph)`` on success, or
            ``(None, None)`` on failure (analyses then run on the baseline).
        """
        baseline: igraph.Graph = prepared.graph
        split_plan: Dict[Any, Dict[str, Any]] = (
            (error_result.extra or {}).get("split_plan") or {}
        )

        if not split_plan:
            return None, None

        logger.info(
            "[SplitExperimentRunner] Building temporary split graph "
            "(%d neurons split).",
            len(split_plan),
        )

        try:
            # baseline.copy() preserves vertex and edge indices, so baseline
            # lookups remain valid on the copy until vertices are deleted.
            temp: igraph.Graph = baseline.copy()

            baseline_id_to_idx = (
                temp["id_to_idx"]
                if "id_to_idx" in temp.attributes()
                else prepared.lookup.id_to_idx
            )

            vertex_attrs = temp.vertex_attributes()
            edge_attrs = temp.edge_attributes()

            # ── Phase 1: capture rewiring operations (no edge mutation) ──
            # Each op describes one split: the original neuron's root id, its
            # synthetic fragment ids, a partner-root -> fragment mapping, and
            # one entry per incident edge (partner root id, edge attrs,
            # outgoing?).  Partner ROOTS (not vertex indices) are captured
            # here so that endpoint resolution never depends on igraph
            # renumbering caused by vertex deletion.
            rewire_ops: List[Dict[str, Any]] = []
            vertices_to_delete: List[int] = []
            total_self_loops_dropped = 0
            planned_self_loops = sum(
                plan.get("self_loops_dropped", 0)
                for plan in split_plan.values()
            )

            for root_id, plan in split_plan.items():
                base_idx = baseline_id_to_idx.get(root_id)
                if base_idx is None:
                    logger.warning(
                        "[SplitExperimentRunner] Split root %r not found in "
                        "baseline id_to_idx; skipping.", root_id,
                    )
                    continue

                fragment_ids = plan["fragment_ids"]
                fragment_partners = plan["fragment_partners"]

                # partner root -> fragment id (every partner exactly once).
                partner_to_fragment: Dict[Any, int] = {}
                for fid, partners in fragment_partners.items():
                    for partner in partners:
                        if partner in partner_to_fragment:
                            raise ValueError(
                                f"[SplitErrors] Partner {partner} assigned "
                                f"to more than one fragment of {root_id}."
                            )
                        partner_to_fragment[partner] = fid

                # O(degree) incident edge collection via igraph's index.
                # An edge between TWO split neurons is incident to both ops;
                # it is owned by exactly one op — the one with the smaller
                # root id — to avoid double counting.  Phase 3 chains the
                # partner endpoint through the partner's own split plan.
                incident_edges: List[tuple] = []
                op_self_loop_ids: set = set()
                for e_idx in temp.incident(base_idx, mode="all"):
                    e = temp.es[e_idx]
                    if e.source == base_idx:
                        partner_root = temp.vs[e.target]["root_id"]
                        outgoing = True
                    else:
                        partner_root = temp.vs[e.source]["root_id"]
                        outgoing = False
                    if partner_root == root_id:
                        # Self-loop (autapse): the centre is not a fragment
                        # partner, so the edge is dropped and counted (mirrors
                        # EM5's self-loop bookkeeping).  igraph returns a
                        # self-loop twice from incident(mode="all"), so count
                        # unique edge ids.
                        op_self_loop_ids.add(e_idx)
                        continue
                    if partner_root in split_plan and root_id > partner_root:
                        continue  # owned by the partner's op
                    attrs = {a: e[a] for a in edge_attrs}
                    incident_edges.append((partner_root, attrs, outgoing))

                total_self_loops_dropped += len(op_self_loop_ids)
                if op_self_loop_ids:
                    logger.info(
                        "[SplitExperimentRunner] Neuron %r: %d self-loop "
                        "edge(s) dropped (autapse).",
                        root_id, len(op_self_loop_ids),
                    )

                if not incident_edges:
                    logger.warning(
                        "[SplitExperimentRunner] Neuron %r has no incident "
                        "edges in the temp graph; skipping split.", root_id,
                    )
                    continue

                # The two fragment vertices.  igraph 1.0 add_vertices()
                # returns None; the new indices are the last two slots of the
                # pre-mutation vertex count (fragments are added before the
                # deletion, so their indices shift by the deletion count —
                # resolved through the rebuilt root -> index map in Phase 3).
                first_new = temp.vcount()
                temp.add_vertices(2)
                for k, fid in enumerate(fragment_ids):
                    idx = first_new + k
                    temp.vs[idx]["root_id"] = fid
                    for attr in vertex_attrs:
                        if attr != "root_id":
                            temp.vs[idx][attr] = temp.vs[base_idx][attr]

                rewire_ops.append({
                    "root_id": root_id,
                    "fragment_ids": fragment_ids,
                    "partner_to_fragment": partner_to_fragment,
                    "edges": incident_edges,
                })
                vertices_to_delete.append(base_idx)

            # ── Self-loop bookkeeping QC (mirrors EM5) ───────────────────
            if total_self_loops_dropped != planned_self_loops:
                msg = (
                    "[SplitExperimentRunner] Self-loop bookkeeping mismatch: "
                    f"runner dropped {total_self_loops_dropped}, plan "
                    f"recorded {planned_self_loops}."
                )
                logger.warning("%s", msg)
                result.warnings.append(msg)

            # ── Phase 2: delete all original split neurons (one batch) ──
            if vertices_to_delete:
                temp.delete_vertices(vertices_to_delete)

            # ── Phase 3: resolve endpoints via the rebuilt root->index map ─
            # Deleting vertices renumbers everything, so indices are never
            # assumed: both fragment vertices and surviving partners are
            # looked up by root id after deletion.  If a split neuron's
            # partner was itself split in the same trial, the edge is chained
            # to the partner's fragment for that neuron (methodology: every
            # edge is assigned to the fragment of its partner's community).
            root_to_idx: Dict[Any, int] = {
                v["root_id"]: v.index for v in temp.vs
            }

            ops_by_root: Dict[Any, Dict[str, Any]] = {
                op["root_id"]: op for op in rewire_ops
            }
            replacements: List[tuple] = []       # (src, dst, attrs)
            for op in rewire_ops:
                a_frag_id_by_partner = op["partner_to_fragment"]
                for partner_root, attrs, outgoing in op["edges"]:
                    a_frag_id = a_frag_id_by_partner[partner_root]
                    src_root: Any = a_frag_id
                    if partner_root in ops_by_root:
                        # Partner was itself split in this trial: the edge
                        # chains to the partner's fragment for this neuron.
                        dst_root = ops_by_root[partner_root][
                            "partner_to_fragment"
                        ][op["root_id"]]
                    else:
                        dst_root = partner_root
                    src = root_to_idx[src_root]
                    dst = root_to_idx[dst_root]
                    if not outgoing:
                        src, dst = dst, src
                    replacements.append((src, dst, attrs))

            # ── Phase 4: add the rewired edges with their attributes ─────
            if replacements:
                temp.add_edges([(s, t) for s, t, _ in replacements])
                base_count = temp.ecount() - len(replacements)
                for i, (_, _, attrs) in enumerate(replacements):
                    e_idx = base_count + i
                    for attr, value in attrs.items():
                        temp.es[e_idx][attr] = value

            # ── Rebuild the temporary lookup tables (post-deletion) ──────
            temp_id_to_idx: Dict[Any, int] = {}
            temp_id_map: Dict[int, Any] = {}
            for v in temp.vs:
                rid = v["root_id"]
                temp_id_to_idx[rid] = v.index
                temp_id_map[v.index] = rid
            temp["id_to_idx"] = temp_id_to_idx
            temp["id_map"] = temp_id_map

            # Copy remaining graph-level metadata.
            for attr in baseline.attributes():
                if attr not in ("id_to_idx", "id_map"):
                    temp[attr] = baseline[attr]
            temp["edge_count"] = temp.ecount()
            temp["node_count"] = temp.vcount()

            # ── Wrap in a PreparedGraph (features disabled, as upstream) ─
            pp_cfg = config.preprocessing_config or {}
            temp_prepared = preprocess_graph(
                temp,
                expected_node_attrs=pp_cfg.get("expected_node_attrs"),
                expected_edge_attrs=pp_cfg.get("expected_edge_attrs"),
                index_node_attrs=pp_cfg.get("index_node_attrs"),
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

            logger.info(
                "[SplitExperimentRunner] Temp split graph built: "
                "nodes=%d edges=%d (baseline %d/%d) | %d self-loops dropped.",
                temp.vcount(), temp.ecount(),
                baseline.vcount(), baseline.ecount(),
                total_self_loops_dropped,
            )

            # Record the ground-truth autapse count (from the temp graph) so
            # downstream exports can account for the dropped edges.
            if total_self_loops_dropped:
                meta = error_result.perturbation_metadata or {}
                meta["self_loops_dropped"] = total_self_loops_dropped
                error_result.perturbation_metadata = meta

            return temp, temp_prepared

        except Exception as exc:  # noqa: BLE001
            msg = (
                f"Failed to build temporary split graph: {exc}. "
                "Analyses will run on baseline graph."
            )
            logger.warning("[SplitExperimentRunner] %s", msg)
            result.warnings.append(msg)
            return None, None

    # ------------------------------------------------------------------ #
    # Repr                                                                 #
    # ------------------------------------------------------------------ #

    def __repr__(self) -> str:
        return (
            f"SplitExperimentRunner("
            f"analyses={self._analysis_registry.list_names()}, "
            f"error_models={self._error_registry.list_names()})"
        )
