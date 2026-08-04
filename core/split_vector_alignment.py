"""
EM4 – Split Vector Alignment (EM4-only helper)
================================================
Rebuilds per-vertex analysis vectors produced on the EM4 *temporary* graph
back into the **baseline vertex ordering** so that the shared vector-comparison
pipeline (StatisticsEngine → VectorComparisonRegistry) compares aligned
vectors.

Why this is needed (verified against the codebase):
    - ``PageRankAnalysis`` returns ``g.pagerank(...)`` — a list indexed by the
      graph's vertex order.
    - ``SplitExperimentRunner._split_build_temp_graph`` copies the baseline,
      **deletes** split parent vertices and adds fragment vertices, so igraph
      renumbers vertex indices.  The temp-graph PageRank vector is therefore
      in a *different coordinate space* than the baseline vector.
    - The shared comparison strategies
      (``modules/statistical_evaluation/vector_comparison.py``) are purely
      positional: Pearson/Spearman are element-wise via ``zip`` and
      ``topk_overlap`` compares ``np.argsort`` *positions*.  Misaligned
      vectors of different lengths collapse these metrics toward zero.

    This module fixes the alignment **entirely inside EM4**: the shared
    framework keeps receiving a normal vector (now in baseline ordering), so
    ``StatisticsEngine`` and ``vector_comparison`` remain completely unaware
    of EM4's temporary vertex machinery.

Known limitation (documented, per specification):
    Only the ``pagerank_scores`` vector is re-aligned — the specification
    explicitly limits the fix to PageRank ("Replace only the PageRank vector
    inside the EM4 analysis results").  If other vector-valued analyses
    (e.g. ``centrality`` betweenness/closeness) are ever enabled for EM4,
    their vectors would remain in temp-graph ordering; this helper must be
    extended per-metric if that becomes necessary.

Why this module lives in ``core/`` (not ``modules/statistical_evaluation/``):
    ``modules/statistical_evaluation/`` is shared by EM1–EM3 and must stay
    frozen.  This helper is consumed exclusively by
    :class:`core.split_experiment_runner.SplitExperimentRunner`.

Fragment aggregation rule (documented decision):
    The methodology (``docs/error model/em4/method plan.md``) specifies that a
    split neuron A becomes exactly two fragments A1 and A2 and that only
    *neuron identity* changes — synapse counts and edge weights are never
    changed.  It does not define how a per-vertex centrality such as PageRank
    of the fragments relates to the parent, so the aggregation rule is a
    documented implementation decision:

        **sum aggregation (default)** — the aligned score of a baseline neuron
        is the sum of the scores of its fragments.

    Rationale:
        - PageRank is a stationary probability mass over the node set (both
          the baseline and the perturbed graph sum to 1).  Summing fragment
          scores conserves each neuron's total probability mass, so the
          aligned vector is a proper probability vector directly comparable
          with the baseline.
        - It reduces to the identity for neurons that were not split.
        - It matches the methodology's stance that a split is a change of
          representation, not a change of the underlying biological entity.
    ``mean`` aggregation is offered as an option but is NOT the default
    because it does not conserve total mass.

All functions are pure (no graph mutation, no I/O, no global state), which
keeps them trivially unit-testable and side-effect free.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Supported aggregation rules for fragment scores
# ---------------------------------------------------------------------------

_AGGREGATIONS = ("sum", "mean")


# ---------------------------------------------------------------------------
# Mapping builders (thin, explicit)
# ---------------------------------------------------------------------------

def build_baseline_order(
    id_map: Dict[int, Any], vcount: int
) -> List[Any]:
    """Return baseline root ids in baseline vertex-index order.

    ``prepared.lookup.id_map`` maps ``igraph_index → root_id`` and is dense
    over ``0 .. vcount-1`` (built by the Graph Builder).  This ordering is
    the coordinate space of the baseline analysis vectors.
    """
    return [id_map[i] for i in range(vcount)]


def build_temp_root_to_index(graph: Any) -> Dict[Any, int]:
    """Return ``{root_id: igraph_index}`` for the temporary graph.

    The temp graph's vertex order is the coordinate space of the EM4
    perturbed analysis vectors.
    """
    return {v["root_id"]: v.index for v in graph.vs}


def build_split_parents(split_plan: Dict[Any, Dict[str, Any]]) -> Dict[Any, List[Any]]:
    """Return ``{parent_root_id: [fragment_root_id, ...]}`` from the split plan.

    ``split_plan`` is EM4's transient ``ErrorResult.extra["split_plan"]``
    structure (``{parent_root: {"fragment_ids": [fid_1, fid_2], ...}}``).
    """
    return {
        root: list(plan.get("fragment_ids", []))
        for root, plan in split_plan.items()
    }


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

def _aggregate(values: List[float], aggregation: str) -> float:
    """Combine fragment scores into one parent score.

    Args:
        values:      The fragment scores (one per fragment of a parent).
        aggregation: ``"sum"`` (default) or ``"mean"``.

    Returns:
        The combined score; ``0.0`` for an empty list.
    """
    if not values:
        return 0.0
    if aggregation == "sum":
        return float(sum(values))
    if aggregation == "mean":
        return float(sum(values) / len(values))
    raise ValueError(
        f"[SplitVectorAlignment] Unsupported aggregation {aggregation!r}. "
        f"Supported: {_AGGREGATIONS}."
    )


# ---------------------------------------------------------------------------
# Core alignment
# ---------------------------------------------------------------------------

def align_vertex_vector(
    vector: List[float],
    baseline_order: List[Any],
    temp_root_to_index: Dict[Any, int],
    split_parents: Dict[Any, List[Any]],
    *,
    aggregation: str = "sum",
) -> List[float]:
    """Rebuild *vector* from temp-graph ordering into baseline ordering.

    Args:
        vector:
            A per-vertex vector produced on the EM4 temporary graph
            (indexed by temp vertex order), e.g. ``pagerank_scores``.
        baseline_order:
            Baseline root ids in baseline vertex-index order (see
            :func:`build_baseline_order`).
        temp_root_to_index:
            Temp-graph ``root_id → vertex index`` (see
            :func:`build_temp_root_to_index`).
        split_parents:
            ``{parent_root: [fragment_roots]}}`` (see :func:`build_split_parents`).
        aggregation:
            How to combine fragment scores: ``"sum"`` (default) or ``"mean"``.

    Returns:
        A new ``list[float]`` of length ``len(baseline_order)`` where position
        ``i`` corresponds to baseline vertex ``baseline_order[i]``.

        - Non-split neurons keep their own temp-graph score.
        - Split neurons receive the aggregated score of their fragments.
        - A neuron listed in the split plan whose fragments are absent from
          the temp graph (i.e. it was not actually split — the runner skips
          unresolved / edgeless roots) keeps its own temp-graph score.
        - Defensive ``0.0`` fallback only for roots genuinely absent from
          the temp graph (cannot normally happen: only split parents are
          removed).
    """
    aligned: List[float] = []
    for parent in baseline_order:
        fragments = split_parents.get(parent)
        if fragments:
            scores = [
                vector[temp_root_to_index[fragment]]
                for fragment in fragments
                if fragment in temp_root_to_index
            ]
            if scores:
                aligned.append(_aggregate(scores, aggregation))
            else:
                # The parent was listed in the split plan but no fragment
                # scores are present in the temp graph.  Two cases:
                #   1. The parent was NOT actually split (the runner's temp
                #      build skips roots it cannot resolve / has no edges
                #      for) — the parent vertex still exists in the temp
                #      graph, so its own score is the correct aligned value.
                #   2. Genuinely absent vertex — defensive 0.0.
                idx = temp_root_to_index.get(parent)
                aligned.append(vector[idx] if idx is not None else 0.0)
        else:
            idx = temp_root_to_index.get(parent)
            aligned.append(vector[idx] if idx is not None else 0.0)
    return aligned


def align_pagerank_vectors(
    vector: List[float],
    baseline_order: List[Any],
    temp_root_to_index: Dict[Any, int],
    split_parents: Dict[Any, List[Any]],
    *,
    aggregation: str = "sum",
) -> List[float]:
    """Rebuild a PageRank vector from temp-graph ordering into baseline
    ordering.

    Thin, domain-named wrapper over :func:`align_vertex_vector` so call sites
    read as intent: *"align the PageRank vector back to baseline ordering"*.

    Returns:
        ``List[float]`` — the aligned vector (never a dict, so the shared
        framework remains unaware that alignment occurred).
    """
    return align_vertex_vector(
        vector=vector,
        baseline_order=baseline_order,
        temp_root_to_index=temp_root_to_index,
        split_parents=split_parents,
        aggregation=aggregation,
    )
