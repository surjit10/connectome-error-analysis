"""
EM5 – Merge Experiment Runner
===============================
Dedicated execution pipeline for topology-changing error models (EM5 merge
errors) that require temporary merged vertices.

Architecture (per ``docs/error model/em5/implementation roadmap.md``):

    - EM5 must **not** use :class:`~core.experiment_runner.ExperimentRunner`.
    - This runner mirrors the execution flow of ``ExperimentRunner`` but
      implements an independent temporary graph construction stage,
      :meth:`_merge_build_temp_graph`, that supports temporary merged
      vertices and rebuilt lookup tables.
    - :meth:`_merge_build_temp_graph` is private to this runner, responsible
      only for EM5, and is **guaranteed to never modify the baseline
      :class:`PreparedGraph`** or its ``lookup``.
    - ``ExperimentRunner._build_temp_graph`` remains completely untouched and
      continues to serve EM1–EM4.

Execution pipeline::

    MergeExperimentRunner.run(ExperimentConfig)
            │
            ▼
    Data Loader → Graph Builder → Preprocessing → PreparedGraph (immutable)
            │
            ▼
    Error Model "merge_errors" (registry) → ErrorResult
            │                                 │ extra["merge_plan"]
            ▼                                 ▼
    _merge_build_temp_graph()  ─────────────► temp igraph + temp lookup
            │
            ▼
    Existing analyses (AnalysisRegistry) → ExperimentResult
            │
            ▼
    _align_pagerank_vectors()   (EM5-only: baseline-collapse alignment)
            │
            ▼
    StatisticsEngine → ExportManager

Design notes:
    - Reuses the shared :class:`ExperimentConfig` / :class:`ExperimentResult`
      / :class:`ExperimentStatus` contracts from ``core.experiment_runner``
      (imported, never modified).
    - The runner composes the shared ``ExperimentRunner`` step
      implementations (dataset load, graph build, preprocess, analyses,
      export) without modifying them; the pipeline orchestration omits the
      EM1-specific biological vulnerability / probability calibration phases
      and routes temporary graph construction through
      :meth:`_merge_build_temp_graph`.
"""

from __future__ import annotations

import copy
import datetime
import logging
import time
from typing import Any, Dict, List, Optional, Tuple

import igraph

from core.experiment_runner import (
    ExperimentConfig,
    ExperimentResult,
    ExperimentStatus,
)
from modules.error_models.common.error_result import ErrorModelStatus
from modules.preprocessing import preprocess_graph

logger = logging.getLogger(__name__)


class MergeExperimentRunner:
    """Dedicated execution pipeline for EM5 (merge errors).

    Mirrors the orchestration of
    :class:`~core.experiment_runner.ExperimentRunner` but owns its temporary
    graph construction so that merged vertices never leak into the shared
    EM1–EM4 path.

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
        """Execute the full EM5 experiment pipeline defined by *config*.

        Returns an :class:`ExperimentResult` in exactly the same format the
        shared runner produces, so the existing statistics / export pipeline
        consumes it unchanged.
        """
        started_at = datetime.datetime.utcnow().isoformat() + "Z"
        t_start = time.perf_counter()

        logger.info(
            "[MergeExperimentRunner] Starting experiment '%s' | dataset=%s "
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
                "[MergeExperimentRunner] Unhandled error in experiment '%s': %s",
                config.experiment_id, exc,
            )

        result.runtime_seconds = time.perf_counter() - t_start
        result.finished_at = datetime.datetime.utcnow().isoformat() + "Z"

        if result.status == ExperimentStatus.SUCCESS and result.failed_analyses:
            result.status = ExperimentStatus.PARTIAL

        logger.info("[MergeExperimentRunner] Finished. %s", result.summary())

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
        """Execute each EM5 pipeline step in order, aborting on fatal errors.

        Mirrors ``ExperimentRunner._run_pipeline`` but:
          - omits the EM1-specific biological vulnerability / probability
            calibration phases (no dependency in EM5's methodology);
          - builds the temporary graph via :meth:`_merge_build_temp_graph`;
          - re-aligns PageRank vectors into the merged coordinate space
            (EM5-only, both baseline and perturbed).
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
                logger.warning(
                    "[MergeExperimentRunner] Error model '%s' failed; "
                    "running analyses on baseline graph.",
                    config.error_model_name,
                )
                result.warnings.append(
                    f"Error model '{config.error_model_name}' failed; "
                    "running analyses on baseline graph."
                )
                error_result = None

        # ── Step 6: Build temporary merged graph (EM5-specific) ──────────
        temp_graph: Optional[igraph.Graph] = None
        analysis_target: Any = prepared

        merge_plan = None
        if error_result is not None:
            merge_plan = (error_result.extra or {}).get("merge_plan")

        if merge_plan:
            temp_graph, temp_prepared = self._merge_build_temp_graph(
                prepared, error_result, config, result
            )
            if temp_prepared is not None:
                analysis_target = temp_prepared

        # ── Step 7: Run analyses ─────────────────────────────────────────
        if config.analysis_names:
            self._runner._step_run_analyses(  # noqa: SLF001
                analysis_target, config, result
            )

        # ── Step 7.5: EM5 PageRank alignment (isolated, EM5-only) ───────
        # EM5 deletes absorbed vertices, so both the baseline and the
        # temp-graph vectors live in different coordinate spaces (different
        # lengths too).  The shared comparison pipeline compares vectors
        # positionally, so both vectors are re-expressed in the merged
        # coordinate space here — entirely inside EM5 — before the temporary
        # mapping is destroyed.
        if temp_graph is not None:
            self._align_pagerank_vectors(result, prepared, merge_plan, temp_graph)

        # ── Step 8: Destroy temporary graph immediately ──────────────────
        if temp_graph is not None:
            del temp_graph
            del analysis_target
            logger.debug(
                "[MergeExperimentRunner] Temporary merged graph released."
            )

        # Release the transient merge plan (only needed for temp construction).
        if error_result is not None and error_result.extra:
            error_result.extra.pop("merge_plan", None)

    # ------------------------------------------------------------------ #
    # EM5-only vector alignment (isolated stage)                            #
    # ------------------------------------------------------------------ #

    def _align_pagerank_vectors(
        self,
        result: ExperimentResult,
        prepared: Any,
        merge_plan: Dict[Any, Dict[str, Any]],
        temp_graph: igraph.Graph,
    ) -> None:
        """Replace the PageRank vectors (baseline AND perturbed) with
        aligned ones in the merged coordinate space, then immediately compute
        per-trial comparison metrics from those aligned vectors.

        Called immediately after analyses complete and before the temporary
        graph is destroyed.  Only the ``pagerank_scores`` metric of the
        ``pagerank`` analysis is touched; every other metric continues to
        flow through the existing pipeline untouched.

        Three phases:

        1. **Collapse baseline** — ``collapse_baseline_vector`` sums the two
           source neurons' scores into one merged slot (sum rule already
           defined in ``core.merge_vector_alignment``).
        2. **Reindex perturbed** — ``reindex_temp_vector`` places each merged
           vertex's score into the same merged slot.
        3. **Per-trial comparison** — Pearson, Spearman and top-K overlap are
           computed *here*, between the two correctly-aligned vectors, and
           stored as plain float scalars in ``result.analysis_results`` using
           the same key convention the vector pathway would have produced
           (``pagerank_scores_pearson`` / ``pagerank_scores_spearman`` /
           ``pagerank_scores_topk_overlap``).
           The raw ``pagerank_scores`` vector is then *removed* from
           ``result.analysis_results`` so the shared ``StatisticsEngine``
           vector pathway — which has no knowledge of the merge mapping and
           would compare positionally against the 0%-rate unaligned baseline
           of a different length — cannot produce a second, invalid result.

        All logic lives in the EM5-only helper
        :mod:`core.merge_vector_alignment`; the shared framework modules are
        never modified and never learn that alignment occurred.
        """
        if not merge_plan:
            return

        from core.merge_vector_alignment import (
            build_merged_order,
            build_temp_root_to_index,
            collapse_baseline_vector,
            reindex_temp_vector,
        )

        id_map = prepared.lookup.id_map
        id_to_idx = prepared.lookup.id_to_idx
        vcount = prepared.graph.vcount()
        temp_root_to_index = build_temp_root_to_index(temp_graph)
        merged_order = build_merged_order(id_map, vcount, merge_plan)

        # ── Phase 1: Collapse baseline into merged space ──────────────────
        for a_res in result.baseline_analysis_results:
            if a_res.analysis_name != "pagerank":
                continue
            vector = a_res.metrics.get("pagerank_scores")
            if vector is None:
                continue
            a_res.metrics["pagerank_scores"] = collapse_baseline_vector(
                list(vector), id_to_idx, merge_plan, merged_order
            )
            logger.info(
                "[MergeExperimentRunner] Collapsed baseline pagerank_scores "
                "into merged space: %d -> %d entries.",
                len(vector), len(merged_order),
            )

        # ── Phase 2: Reindex perturbed vector into merged space ───────────
        for a_res in result.analysis_results:
            if a_res.analysis_name != "pagerank":
                continue
            vector = a_res.metrics.get("pagerank_scores")
            if vector is None:
                continue
            a_res.metrics["pagerank_scores"] = reindex_temp_vector(
                list(vector), temp_root_to_index, merge_plan, merged_order
            )
            logger.info(
                "[MergeExperimentRunner] Re-indexed temp pagerank_scores "
                "into merged space: %d -> %d entries.",
                len(vector), len(merged_order),
            )

        # ── Phase 3: Per-trial comparison on the aligned vectors ──────────
        # Both vectors are now in the same merged coordinate space.  Compute
        # Pearson, Spearman and top-K overlap *now*, before the temp graph is
        # destroyed, and store them as scalar metrics so the StatisticsEngine
        # scalar pathway aggregates them correctly across trials.
        #
        # The raw ``pagerank_scores`` vector is then removed from
        # ``analysis_results`` so the StatisticsEngine vector pathway cannot
        # run a second, positionally-invalid comparison: the vector pathway
        # has no merge-mapping knowledge and would compare the merged-space
        # perturbed vector (length vcount−k) against an averaged baseline
        # vector of full length (vcount), producing misleading metrics via
        # silent zip-truncation.
        from modules.statistical_evaluation.vector_comparison import (
            compare_pagerank,
        )

        # Build a lookup: analysis_name → collapsed baseline vector.
        collapsed_by_name: Dict[str, list] = {}
        for b_res in result.baseline_analysis_results:
            if b_res.analysis_name == "pagerank":
                bv = b_res.metrics.get("pagerank_scores")
                if bv is not None:
                    collapsed_by_name["pagerank"] = list(bv)

        if not collapsed_by_name:
            logger.warning(
                "[MergeExperimentRunner] No collapsed baseline pagerank vector "
                "found in baseline_analysis_results.  Per-trial comparison "
                "scalars will not be computed.  Ensure ExperimentConfig sets "
                "baseline_analysis_names=[\"pagerank\"]."
            )

        top_k = 100  # matches StatisticsEngine / vector_comparison defaults
        comparison_cfg = {"top_k_overlap": top_k}

        for a_res in result.analysis_results:
            if a_res.analysis_name != "pagerank":
                continue
            collapsed_baseline = collapsed_by_name.get("pagerank")
            if collapsed_baseline is None:
                # baseline_analysis_names not configured — skip scalar phase.
                continue
            perturbed_vec = a_res.metrics.get("pagerank_scores")
            if perturbed_vec is None:
                continue

            try:
                comparison = compare_pagerank(
                    collapsed_baseline, list(perturbed_vec), comparison_cfg
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "[MergeExperimentRunner] Per-trial aligned pagerank "
                    "comparison failed: %s", exc
                )
                continue

            # Store scalars with the same naming convention the vector
            # pathway would have produced, so the evaluation layer sees
            # consistent keys across rates.
            # Vector pathway convention: f"{metric_key}_{derived_key}"
            #   metric_key = "pagerank_scores"
            #   derived_key = "pearson" | "spearman" | "topk_overlap"
            for comp_key, comp_val in comparison.items():
                a_res.metrics[f"pagerank_scores_{comp_key}"] = float(comp_val)

            logger.info(
                "[MergeExperimentRunner] Per-trial aligned PageRank: "
                "pearson=%.4f  spearman=%.4f  topk=%.4f  (merged-space len=%d)",
                comparison.get("pearson", float("nan")),
                comparison.get("spearman", float("nan")),
                comparison.get("topk_overlap", float("nan")),
                len(perturbed_vec),
            )

            # Remove the raw vector so the StatisticsEngine vector pathway
            # skips this metric entirely (no vector → no comparison).
            del a_res.metrics["pagerank_scores"]

    # ------------------------------------------------------------------ #
    # EM5-specific temporary graph construction (isolated stage)            #
    # ------------------------------------------------------------------ #

    def _merge_build_temp_graph(
        self,
        prepared: Any,
        error_result: Any,
        config: ExperimentConfig,
        result: ExperimentResult,
    ) -> Tuple[Optional[igraph.Graph], Optional[Any]]:
        """Build a temporary igraph with merged vertices from the merge plan.

        **Isolated EM5 stage.**  This function is private to
        :class:`MergeExperimentRunner` and is the only component allowed to
        create temporary merged vertices.  It:

          - copies the baseline igraph (the baseline is never modified);
          - for every merge, deletes the two absorbed neurons, adds one
            synthetic merged vertex (negative root ID), re-attaches every
            incident edge exactly once (endpoints resolved by **root ID**
            after deletion — never by stale igraph indices), collapses
            parallel pairs with summed ``syn_count``, and drops A<->B edges
            (self-loops), counting them explicitly;
          - rebuilds the temporary ``id_to_idx`` / ``id_map`` lookup tables
            from the temp graph (the post-merge index space);
          - wraps the temp graph in a fresh ``PreparedGraph`` with feature
            extraction disabled (identical to the other runners' strategy).

        Returns:
            ``(temp_graph, temp_PreparedGraph)`` on success, or
            ``(None, None)`` on failure (analyses then run on the baseline).
        """
        baseline: igraph.Graph = prepared.graph
        merge_plan: Dict[Any, Dict[str, Any]] = (
            (error_result.extra or {}).get("merge_plan") or {}
        )

        if not merge_plan:
            return None, None

        logger.info(
            "[MergeExperimentRunner] Building temporary merged graph "
            "(%d merges).",
            len(merge_plan),
        )

        try:
            # baseline.copy() preserves vertex/edge indices AND graph
            # attributes, so baseline lookups remain valid on the copy until
            # vertices are deleted.
            temp: igraph.Graph = baseline.copy()

            baseline_id_to_idx = (
                temp["id_to_idx"]
                if "id_to_idx" in temp.attributes()
                else prepared.lookup.id_to_idx
            )

            vertex_attrs = temp.vertex_attributes()
            edge_attrs = temp.edge_attributes()

            # absorbed root -> merge_id (a neuron appears in at most one merge).
            absorbed_to_merge: Dict[Any, Any] = {}
            pairs: List[Tuple[Any, Any, Any]] = []  # (merge_id, a, b)
            for merge_id, plan in merge_plan.items():
                srcs = plan["source_ids"]
                a, b = srcs[0], srcs[1]
                absorbed_to_merge[a] = merge_id
                absorbed_to_merge[b] = merge_id
                pairs.append((merge_id, a, b))

            # ── Phase 1: capture re-attachment ops (no edge mutation) ──
            # Each captured entry describes one incident edge of one absorbed
            # root: the owning merge, the PARTNER ROOT, direction, attrs, and
            # whether it is a same-pair (self-loop) edge.
            # Edges between two absorbed roots (same or different pairs) are
            # incident to both endpoints; they are owned by exactly one of
            # them — the one with the smaller root id — to avoid double
            # capture (and double weight summation downstream).
            captured: List[Tuple[Any, Any, bool, Dict[str, Any], bool]] = []
            vertices_to_delete: List[int] = []

            for merge_id, a, b in pairs:
                for src_root in (a, b):
                    base_idx = baseline_id_to_idx.get(src_root)
                    if base_idx is None:
                        logger.warning(
                            "[MergeExperimentRunner] Merge source %r not "
                            "found in baseline id_to_idx; skipping.",
                            src_root,
                        )
                        continue
                    vertices_to_delete.append(base_idx)
                    for e_idx in temp.incident(base_idx, mode="all"):
                        e = temp.es[e_idx]
                        if e.source == base_idx:
                            partner_root = temp.vs[e.target]["root_id"]
                            outgoing = True
                        else:
                            partner_root = temp.vs[e.source]["root_id"]
                            outgoing = False
                        if partner_root in absorbed_to_merge:
                            # Edge between two absorbed neurons: single
                            # ownership by the smaller root id.
                            if src_root > partner_root:
                                continue
                            is_selfloop = (
                                absorbed_to_merge[partner_root] == merge_id
                            )
                        else:
                            is_selfloop = False
                        attrs = {attr: e[attr] for attr in edge_attrs}
                        captured.append(
                            (merge_id, partner_root, outgoing, attrs, is_selfloop)
                        )

            if not captured:
                logger.warning(
                    "[MergeExperimentRunner] No incident edges captured; "
                    "analyses will run on baseline graph."
                )
                return None, None

            # ── Phase 2: add merged vertices, then delete absorbed roots ──
            # Merged vertices are appended BEFORE deletion so that the
            # deletion renumbering is resolved through the rebuilt
            # root -> index map in Phase 3 (indices are never assumed).
            first_new = temp.vcount()
            temp.add_vertices(len(pairs))
            for i, (merge_id, a, b) in enumerate(pairs):
                idx = first_new + i
                rep = baseline_id_to_idx.get(a, baseline_id_to_idx.get(b))
                temp.vs[idx]["root_id"] = merge_id
                if rep is not None:
                    for attr in vertex_attrs:
                        if attr != "root_id":
                            temp.vs[idx][attr] = temp.vs[rep][attr]

            if vertices_to_delete:
                temp.delete_vertices(vertices_to_delete)

            # ── Phase 3: resolve endpoints via the rebuilt root->index map ─
            root_to_idx: Dict[Any, int] = {
                v["root_id"]: v.index for v in temp.vs
            }

            weight_attr = (
                "syn_count" if "syn_count" in edge_attrs
                else ("weight" if "weight" in edge_attrs else None)
            )

            # final_edges: {(src_root, dst_root): attrs} — parallel pairs
            # collapse into one entry with summed weight.
            final_edges: Dict[Tuple[Any, Any], Dict[str, Any]] = {}
            self_loops_dropped = 0
            internal_synapses_dropped = 0
            captured_reattached = 0

            for merge_id, partner_root, outgoing, attrs, is_selfloop in captured:
                if is_selfloop:
                    self_loops_dropped += 1
                    if weight_attr is not None:
                        w = attrs.get(weight_attr)
                        if w is not None:
                            internal_synapses_dropped += int(w)
                    continue
                # The partner endpoint: absorbed roots map to their merge_id.
                end_root = absorbed_to_merge.get(partner_root, partner_root)
                if outgoing:
                    src_root, dst_root = merge_id, end_root
                else:
                    src_root, dst_root = end_root, merge_id
                if src_root == dst_root:
                    # Defensive: a merged self-loop (cannot normally occur
                    # after the same-pair drop above).
                    self_loops_dropped += 1
                    continue
                captured_reattached += 1
                key = (src_root, dst_root)
                if key in final_edges:
                    # Parallel collapse: sum the weight; keep the first edge's
                    # other attributes.
                    existing = final_edges[key]
                    if weight_attr is not None:
                        ew = existing.get(weight_attr)
                        w = attrs.get(weight_attr)
                        if ew is not None and w is not None:
                            existing[weight_attr] = int(ew) + int(w)
                else:
                    final_edges[key] = dict(attrs)

            # ── Phase 4: add the re-attached edges with their attributes ──
            if final_edges:
                indices = [
                    (root_to_idx[s], root_to_idx[d]) for s, d in final_edges
                ]
                temp.add_edges(indices)
                base_count = temp.ecount() - len(indices)
                for i, key in enumerate(final_edges):
                    e_idx = base_count + i
                    for attr, value in final_edges[key].items():
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

            # ── Wrap in a PreparedGraph (features disabled, as upstream) ──
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

            # ── Record exact accounting into the error-model metadata ────
            # The runner is the source of truth for the actual graph mutation.
            # ``self_loops_dropped`` / ``internal_synapses_dropped`` match the
            # plan's edge-exact per-pair values, but the global parallel-
            # collapse total can only be computed here: an edge between two
            # DIFFERENT merged pairs is seen by both pairs' per-pair views, so
            # only the runner knows the deduplicated collapse count.  Writing
            # the exact totals here keeps every downstream consumer (exports,
            # verification) consistent on datasets with parallel edges.
            if error_result is not None and error_result.perturbation_metadata:
                meta = error_result.perturbation_metadata
                meta["self_loops_dropped"] = self_loops_dropped
                meta["internal_synapses_dropped"] = internal_synapses_dropped
                meta["parallel_pairs_collapsed"] = (
                    captured_reattached - len(final_edges)
                )

            # ── Consistency QC: dropped self-loops match the plan ────────
            # Regression guard.  The plan's ``_merge_stats`` counts the same
            # physical same-pair edges (edge-exact), so any mismatch now
            # signals a genuine regression, not parallel-edge noise.
            planned_dropped = sum(
                plan.get("self_loops_dropped", 0) for plan in merge_plan.values()
            )
            if self_loops_dropped != planned_dropped:
                logger.warning(
                    "[MergeExperimentRunner] Self-loop bookkeeping mismatch: "
                    "runner dropped %d, plan recorded %d.",
                    self_loops_dropped, planned_dropped,
                )

            logger.info(
                "[MergeExperimentRunner] Temp merged graph built: "
                "nodes=%d edges=%d (baseline %d/%d) | %d self-loops dropped, "
                "%d synapses dropped.",
                temp.vcount(), temp.ecount(),
                baseline.vcount(), baseline.ecount(),
                self_loops_dropped, internal_synapses_dropped,
            )
            return temp, temp_prepared

        except Exception as exc:  # noqa: BLE001
            msg = (
                f"Failed to build temporary merged graph: {exc}. "
                "Analyses will run on baseline graph."
            )
            logger.warning("[MergeExperimentRunner] %s", msg)
            result.warnings.append(msg)
            return None, None

    # ------------------------------------------------------------------ #
    # Repr                                                                 #
    # ------------------------------------------------------------------ #

    def __repr__(self) -> str:
        return (
            f"MergeExperimentRunner("
            f"analyses={self._analysis_registry.list_names()}, "
            f"error_models={self._error_registry.list_names()})"
        )
