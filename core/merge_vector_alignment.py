"""
EM5 – Merge Vector Alignment (EM5-only helper)
================================================
Rebuilds per-vertex analysis vectors (e.g. PageRank) into a common
**merged coordinate space** so that the shared vector-comparison pipeline
(StatisticsEngine -> VectorComparisonRegistry) compares aligned vectors of
equal length.

Why this is needed (verified against the codebase):
    - ``PageRankAnalysis`` returns ``g.pagerank(...)`` — a list indexed by
      the graph's vertex order.
    - ``MergeExperimentRunner._merge_build_temp_graph`` copies the baseline,
      **deletes** the absorbed neurons of each merge and adds one synthetic
      merged vertex per pair, so igraph renumbers vertex indices.  The
      temp-graph vector therefore lives in a *different coordinate space*
      (and has a different length: ``vcount - k``) than the baseline vector.
    - The shared comparison strategies
      (``modules/statistical_evaluation/vector_comparison.py``) are purely
      positional: Pearson/Spearman are element-wise via ``zip`` and
      ``topk_overlap`` compares ``np.argsort`` *positions*.  Misaligned
      vectors of different lengths collapse these metrics toward zero.

    EM5 fixes this **entirely inside EM5**: the merged coordinate space has
    one slot per baseline neuron except that each merged pair collapses into
    a single slot.  Both the *baseline* vector (collapsed: ``a + b``) and the
    *temp* vector (re-indexed: the merged vertex's score) are expressed over
    this space, so the shared framework keeps comparing equal-length,
    positionally aligned vectors and never learns about EM5's temporary
    vertex machinery.

Collapse rule (documented decision, mirrors EM4's sum rule):
    The aligned score of the collapsed slot is the **sum** of the two source
    neurons' baseline scores (``a + b``) — the natural counterpart of EM4's
    sum aggregation of fragment scores.  The merged vertex's score is placed
    directly into that slot.

Known limitation (documented, per specification):
    Only the ``pagerank_scores`` vector is re-aligned, mirroring EM4's
    documented limitation.  If other vector-valued analyses are ever enabled
    for EM5, this helper must be extended per-metric.

Why this module lives in ``core/`` (not ``modules/statistical_evaluation/``):
    ``modules/statistical_evaluation/`` is shared by EM1–EM4 and must stay
    frozen.  This helper is consumed exclusively by
    :class:`core.merge_experiment_runner.MergeExperimentRunner`.

All functions are pure (no graph mutation, no I/O, no global state).
"""

from __future__ import annotations

from typing import Any, Dict, List


# ---------------------------------------------------------------------------
# Mapping builders (thin, explicit)
# ---------------------------------------------------------------------------

def build_merged_order(
    id_map: Dict[int, Any],
    vcount: int,
    merge_plan: Dict[Any, Dict[str, Any]],
) -> List[Any]:
    """Return baseline root ids in baseline vertex-index order, with each
    merged pair collapsed into a single slot at the first source's position.

    ``prepared.lookup.id_map`` maps ``igraph_index -> root_id`` and is dense
    over ``0 .. vcount-1``.  For every merge ``source_ids = [a, b]`` the
    second source ``b`` is absorbed into ``a``'s slot, so the returned list
    has length ``vcount - len(merge_plan)``.
    """
    baseline_order = [id_map[i] for i in range(vcount)]
    second_members = {
        plan["source_ids"][1] for plan in merge_plan.values()
    }
    return [r for r in baseline_order if r not in second_members]


def build_temp_root_to_index(graph: Any) -> Dict[Any, int]:
    """Return ``{root_id: igraph_index}`` for the temporary graph.

    The temp graph's vertex order is the coordinate space of the EM5
    perturbed analysis vectors.
    """
    return {v["root_id"]: v.index for v in graph.vs}


def build_merge_slots(
    merge_plan: Dict[Any, Dict[str, Any]],
) -> Dict[Any, Any]:
    """Return ``{first_source_root: merge_id}`` for every merge.

    Maps a merged-order slot root to the synthetic merged vertex that
    occupies that slot in the temp graph.
    """
    return {
        plan["source_ids"][0]: merge_id
        for merge_id, plan in merge_plan.items()
    }


# ---------------------------------------------------------------------------
# Core alignment
# ---------------------------------------------------------------------------

def collapse_baseline_vector(
    vector: List[float],
    id_to_idx: Dict[Any, int],
    merge_plan: Dict[Any, Dict[str, Any]],
    merged_order: List[Any],
) -> List[float]:
    """Collapse a baseline per-vertex vector into the merged coordinate space.

    For every merged pair ``[a, b]`` the slot at ``a`` receives
    ``vector[idx(a)] + vector[idx(b)]`` (sum rule); every other slot keeps
    its own value.  ``id_to_idx`` is the **baseline** root -> index mapping
    (``prepared.lookup.id_to_idx``).
    """
    pair_slots: Dict[Any, List[int]] = {}
    for plan in merge_plan.values():
        a, b = plan["source_ids"]
        pair_slots[a] = [id_to_idx[a], id_to_idx[b]]

    collapsed: List[float] = []
    for root in merged_order:
        if root in pair_slots:
            ia, ib = pair_slots[root]
            collapsed.append(float(vector[ia]) + float(vector[ib]))
        else:
            collapsed.append(float(vector[id_to_idx[root]]))
    return collapsed


def reindex_temp_vector(
    vector: List[float],
    temp_root_to_index: Dict[Any, int],
    merge_plan: Dict[Any, Dict[str, Any]],
    merged_order: List[Any],
) -> List[float]:
    """Re-index a temp-graph per-vertex vector into the merged coordinate
    space.

    A merged slot (whose baseline root is the pair's first source) reads the
    synthetic merged vertex's score; every other slot reads its own root's
    score.  Defensive ``0.0`` only for roots genuinely absent from the temp
    graph.
    """
    slot_roots = build_merge_slots(merge_plan)
    out: List[float] = []
    for root in merged_order:
        temp_root = slot_roots.get(root, root)
        idx = temp_root_to_index.get(temp_root)
        out.append(float(vector[idx]) if idx is not None else 0.0)
    return out


def align_pagerank_vectors(
    baseline_vector: List[float],
    temp_vector: List[float],
    id_to_idx: Dict[Any, int],
    temp_root_to_index: Dict[Any, int],
    merge_plan: Dict[Any, Dict[str, Any]],
    id_map: Dict[int, Any],
    vcount: int,
) -> tuple:
    """Return ``(collapsed_baseline, reindexed_temp)`` — both of length
    ``vcount - len(merge_plan)``, positionally aligned.

    Thin convenience wrapper combining :func:`build_merged_order`,
    :func:`collapse_baseline_vector`, and :func:`reindex_temp_vector`.
    """
    merged_order = build_merged_order(id_map, vcount, merge_plan)
    collapsed = collapse_baseline_vector(
        baseline_vector, id_to_idx, merge_plan, merged_order
    )
    reindexed = reindex_temp_vector(
        temp_vector, temp_root_to_index, merge_plan, merged_order
    )
    return collapsed, reindexed
