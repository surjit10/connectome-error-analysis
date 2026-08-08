"""
Phase EM5 – Merge Errors (Under-Segmentation) Error Model
==========================================================
Implements Error Model 5 (EM5): a simulation of segmentation *merge errors*
(under-segmentation) that occur during automated EM reconstruction, when two
distinct biological neurons are reconstructed as a single neuron.

The scientific methodology is defined in
``docs/error model/em5/method plan.md`` and is the source of truth for the
algorithm.  This module implements **only** the scientific algorithm; the
execution pipeline (temporary merged-graph construction with re-attached
edges, parallel-edge collapse, self-loop removal) is implemented by
``core.merge_experiment_runner.MergeExperimentRunner``.

Key scientific assumptions (from the methodology):
    1. Merge errors occur at the neuron-pair level (two neurons -> one).
    2. A single neuron is spatially contiguous with one soma: candidate pairs
       must be soma-side compatible (a genuine necessary condition) and
       region-compatible (``top_region`` equality — a conservative proxy for
       the unavailable voxel-level spatial information).
    3. Shared connectivity is **not** a biological requirement for merges;
       it is the strongest graph-derived evidence available for *ranking*
       plausible candidate pairs when morphology is unavailable.
    4. Jaccard similarity over partner sets is used solely as a ranking
       function, not as a biological merge probability.
    5. The perturbation changes only neuron identity.  Every synapse stays
       attributed: incident edges are re-attached to the merged vertex,
       parallel edges collapse with summed ``syn_count``, and A<->B edges
       (which would become self-loops) are dropped and counted explicitly.
    6. The perturbation exists only for the lifetime of a simulation trial.

Algorithm (per methodology sections 6–15):
    Stage 1  -> hard anatomical constraints (region, soma side)
    Neighbourhood extraction -> partner sets (once)
    Stage 2  -> graph-based candidate ranking (shared partners, Jaccard)
    Error rate -> k = round(0.5 * error_rate * n_eligible) pairs
    Sampling -> weighted by Jaccard, without replacement, disjoint
    Merge    -> A + B -> M  (executed by MergeExperimentRunner)
    Validation -> integrity + quality + achieved-vs-target QC (in runner)

The baseline :class:`~modules.preprocessing.common.prepared_graph.PreparedGraph`
is **never** copied or mutated.  The model returns an
:class:`~modules.error_models.common.error_result.ErrorResult` whose
``extra["merge_plan"]`` contains a serialisable description of every merge:

.. code-block:: python

    {
      <merge_id>: {
        "source_ids": [root_a, root_b],
        "edges_reattached": int,          # incident edges moved to M
        "parallel_pairs_collapsed": int,  # pairs collapsed into one edge (sum)
        "self_loops_dropped": int,        # A->B / B->A edges removed
        "internal_synapses_dropped": int, # syn_count lost to self-loop removal
      },
      ...
    }

``MergeExperimentRunner._merge_build_temp_graph()`` consumes this plan to
construct the temporary analysis graph (merged vertex + re-attached edges),
after which the plan is destroyed.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from ..common.base_error_model import BaseErrorModel
from ..common.error_result import ErrorResult
from ..common.utils import add_warning, validate_config_keys
from modules.preprocessing.common.prepared_graph import PreparedGraph

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration contract (methodology parameters + quality floors)
# ---------------------------------------------------------------------------

_KNOWN_CONFIG_KEYS = frozenset({
    "error_rate",
    "degree_threshold",
    "min_shared_partners",
    "jaccard_min",
    "top_k_per_neuron",
    "max_retries",
    "region_constraint",
    "soma_side_constraint",
})

_DEFAULT_ERROR_RATE = 0.05
_DEFAULT_DEGREE_THRESHOLD = 10          # QUALITY FLOOR only (not eligibility)
_DEFAULT_MIN_SHARED_PARTNERS = 3        # Stage 2 ranking-pool calibration
_DEFAULT_JACCARD_MIN = 0.001            # ranking floor (calibration)
_DEFAULT_TOP_K_PER_NEURON = 50          # candidate-enumeration bound
_DEFAULT_MAX_RETRIES = 20               # bounded rejection re-sampling
_DEFAULT_REGION_CONSTRAINT = True
_DEFAULT_SOMA_SIDE_CONSTRAINT = True


# ---------------------------------------------------------------------------
# Helpers (private to the model — no shared util pollution)
# ---------------------------------------------------------------------------

def _merge_id(root_a: int, root_b: int) -> int:
    """Return a synthetic, collision-free root ID for a merged vertex.

    Uses the **Szudzik (elegant) pairing function** — a mathematically
    proven bijection N x N -> N — applied to the *sorted* pair, so the
    result is deterministic, injective (collision-free), and
    order-independent: (A, B) and (B, A) produce the same merged ID.

    Encoding: ``x = min(|a|, |b|)``, ``y = max(|a|, |b|)`` then
    ``pair(x, y) = y^2 + x`` if ``x < y`` else ``y^2 + 2y`` (the Szudzik
    value for ``x == y``); the merged ID is ``-pair(x, y)`` — always
    negative, so it can never collide with real positive biological root
    IDs.  A trial runs exactly one error model, so overlap with EM4's
    fragment-ID namespace is impossible in practice (documented, not
    enforced).
    """
    x = min(abs(int(root_a)), abs(int(root_b)))
    y = max(abs(int(root_a)), abs(int(root_b)))
    if x < y:
        return -(y * y + x)
    return -(y * y + 2 * y)


def _jaccard(set_a: frozenset, set_b: frozenset) -> float:
    """Jaccard similarity ``|A ∩ B| / |A ∪ B|``; 0.0 for two empty sets."""
    if not set_a and not set_b:
        return 0.0
    union_len = len(set_a | set_b)
    if union_len == 0:
        return 0.0
    return len(set_a & set_b) / union_len


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------

class MergeErrorsModel(BaseErrorModel):
    """Simulates neuron-level segmentation merge errors.

    The model never touches the baseline graph.  It applies the Stage 1 hard
    anatomical constraints (region, soma side), ranks surviving pairs by
    Jaccard similarity over their full partner sets (Stage 2), samples
    ``k = round(0.5 * error_rate * n_eligible)`` disjoint pairs weighted by
    similarity, and records a serialisable ``merge_plan`` in
    ``ErrorResult.extra["merge_plan"]``.
    """

    NAME = "merge_errors"

    # ------------------------------------------------------------------ #
    # Perturbation (scientific algorithm — method plan sections 6–15)      #
    # ------------------------------------------------------------------ #

    def _perturb(
        self,
        prepared: PreparedGraph,
        config: Dict[str, Any],
        result: ErrorResult,
        rng: np.random.Generator,
    ) -> None:
        """Execute the merge-error perturbation.

        Args:
            prepared: The immutable baseline
                :class:`~modules.preprocessing.common.prepared_graph.PreparedGraph`.
            config:   Configuration dict (see ``_KNOWN_CONFIG_KEYS``).
            result:   Pre-initialised
                :class:`~modules.error_models.common.error_result.ErrorResult`.
            rng:      NumPy random generator (seeded by the framework).

        Raises:
            ValueError: If ``error_rate`` is outside [0, 1].
        """
        validate_config_keys(config, _KNOWN_CONFIG_KEYS, self.NAME, result)

        # ── Parse configuration ──────────────────────────────────────────
        error_rate = float(config.get("error_rate", _DEFAULT_ERROR_RATE))
        if not 0.0 <= error_rate <= 1.0:
            raise ValueError(
                f"[MergeErrors] error_rate must be in [0.0, 1.0], got "
                f"{error_rate}. It is the fraction of eligible neurons that "
                f"participate in a merge."
            )
        degree_threshold = int(
            config.get("degree_threshold", _DEFAULT_DEGREE_THRESHOLD)
        )
        min_shared_partners = int(
            config.get("min_shared_partners", _DEFAULT_MIN_SHARED_PARTNERS)
        )
        jaccard_min = float(config.get("jaccard_min", _DEFAULT_JACCARD_MIN))
        top_k = int(config.get("top_k_per_neuron", _DEFAULT_TOP_K_PER_NEURON))
        max_retries = int(config.get("max_retries", _DEFAULT_MAX_RETRIES))
        region_constraint = bool(
            config.get("region_constraint", _DEFAULT_REGION_CONSTRAINT)
        )
        soma_side_constraint = bool(
            config.get("soma_side_constraint", _DEFAULT_SOMA_SIDE_CONSTRAINT)
        )

        lookup = prepared.lookup

        # ── Stage 1: hard anatomical constraints (group level) ──────────
        region_groups = self._region_groups(lookup, region_constraint, result)

        # ── Neighbourhood extraction + Stage 2 ranking ───────────────────
        candidates = self._build_candidates(
            lookup=lookup,
            region_groups=region_groups,
            soma_side_constraint=soma_side_constraint,
            degree_threshold=degree_threshold,
            min_shared_partners=min_shared_partners,
            jaccard_min=jaccard_min,
            top_k=top_k,
        )
        n_candidates = len(candidates)

        # ── Error rate: fraction of eligible neurons participating ───────
        unique = {root for pair in candidates for root in pair[:2]}
        n_eligible = len(unique)
        target_k = round(0.5 * error_rate * n_eligible)
        max_pairs = n_eligible // 2
        if target_k > max_pairs:
            logger.info(
                "[MergeErrors] Requested %d pairs exceeds the maximum %d "
                "disjoint pairs; capping.",
                target_k, max_pairs,
            )
            target_k = max_pairs

        if target_k == 0 or n_candidates == 0:
            logger.info(
                "[MergeErrors] error_rate=%.4f / no candidates -> no merges "
                "(eligible=%d, candidates=%d).",
                error_rate, n_eligible, n_candidates,
            )
            result.extra["merge_plan"] = {}
            result.perturbation_metadata = {
                "error_rate": error_rate,
                "target_pairs": target_k,
                "eligible_neurons": n_eligible,
                "candidate_pairs": n_candidates,
                "pairs_merged": 0,
                "neurons_absorbed": 0,
                "pairs_rejected": 0,
                "retries_used": 0,
                "achieved_error_rate": 0.0,
            }
            return

        # ── Sampling: weighted by Jaccard, without replacement, disjoint ─
        selected, rejected, retries_used = self._sample_pairs(
            candidates=candidates,
            target_k=target_k,
            lookup=lookup,
            max_retries=max_retries,
            rng=rng,
        )

        # ── Merge plan (descriptive; the runner recomputes edges) ────────
        # Collision-free synthetic IDs are guaranteed by the Szudzik pairing
        # function (injective by construction); this gate is a hard check that
        # every generated merge ID is unique within the plan.  A duplicate
        # would silently merge unrelated neuron pairs (a dict-key overwrite),
        # violating the binary-merge assumption — so abort and report.
        merge_plan: Dict[int, Dict[str, Any]] = {}
        total_parallel = 0
        total_self_loops = 0
        total_internal_synapses = 0
        for a, b, _jac in selected:
            stats = self._merge_stats(prepared, a, b)
            mid = stats["merge_id"]
            if mid in merge_plan:
                raise ValueError(
                    f"[MergeErrors] Duplicate synthetic merge ID {mid} "
                    f"generated for pairs {merge_plan[mid]['source_ids']} and "
                    f"{stats['source_ids']}; aborting merge-plan construction. "
                    "This violates the binary-merge assumption (each merge "
                    "must be an independent binary event)."
                )
            merge_plan[mid] = stats
            total_parallel += stats["parallel_pairs_collapsed"]
            total_self_loops += stats["self_loops_dropped"]
            total_internal_synapses += stats["internal_synapses_dropped"]

        neurons_absorbed = 2 * len(selected)
        achieved = (neurons_absorbed / n_eligible) if n_eligible > 0 else 0.0

        result.extra["merge_plan"] = merge_plan
        result.perturbation_metadata = {
            "error_rate": error_rate,
            "target_pairs": target_k,
            "eligible_neurons": n_eligible,
            "candidate_pairs": n_candidates,
            "pairs_merged": len(selected),
            "neurons_absorbed": neurons_absorbed,
            "pairs_rejected": rejected,
            "retries_used": retries_used,
            "achieved_error_rate": achieved,
            "parallel_pairs_collapsed": total_parallel,
            "self_loops_dropped": total_self_loops,
            "internal_synapses_dropped": total_internal_synapses,
        }

        # ── Quality control: achieved vs target (transparency, no silent) ─
        if len(selected) < target_k:
            add_warning(
                result,
                f"Merge shortfall: achieved {len(selected)} of {target_k} "
                "target pairs (disjointness / rejection). "
                "The shortfall is reported, never silently absorbed.",
            )

        logger.info(
            "[MergeErrors] error_rate=%.4f | eligible=%d | candidates=%d | "
            "merged=%d | rejected=%d | parallel_collapsed=%d | "
            "self_loops_dropped=%d | synapses_dropped=%d",
            error_rate, n_eligible, n_candidates, len(selected), rejected,
            total_parallel, total_self_loops, total_internal_synapses,
        )

    # ------------------------------------------------------------------ #
    # Stage 1 — hard anatomical constraints                                #
    # ------------------------------------------------------------------ #

    def _region_groups(
        self,
        lookup: Any,
        region_constraint: bool,
        result: ErrorResult,
    ) -> List[List[int]]:
        """Return candidate-neuron groups after the region constraint.

        When ``region_constraint`` is enabled, neurons are grouped by
        ``top_region`` (a conservative proxy for the missing spatial
        information).  When the attribute index is unavailable, a warning is
        emitted and the constraint is skipped (all neurons form one group) —
        matching the framework's tolerant preprocessing contract.
        """
        index = lookup.node_attr_index.get("top_region", {})
        if not index:
            if region_constraint:
                add_warning(
                    result,
                    "No 'top_region' index available; the region constraint "
                    "(Stage 1) is skipped for this graph.",
                )
            return [sorted(lookup.node_set)]
        if not region_constraint:
            return [sorted(lookup.node_set)]
        return [sorted(ns) for ns in index.values() if len(ns) >= 2]

    @staticmethod
    def _soma_compatible(node_attrs: Dict[Any, Dict[str, Any]], a: int, b: int) -> bool:
        """Soma-side compatibility: equal sides, or either side bilateral.

        ``None`` values (attribute absent) never block a pair.
        """
        sa = (node_attrs.get(a) or {}).get("soma_side")
        sb = (node_attrs.get(b) or {}).get("soma_side")
        if sa is None or sb is None:
            return True
        if sa == sb:
            return True
        return "bilateral" in str(sa) or "bilateral" in str(sb)

    # ------------------------------------------------------------------ #
    # Neighbourhood extraction + Stage 2 — graph-based candidate ranking   #
    # ------------------------------------------------------------------ #

    def _build_candidates(
        self,
        lookup: Any,
        region_groups: List[List[int]],
        soma_side_constraint: bool,
        degree_threshold: int,
        min_shared_partners: int,
        jaccard_min: float,
        top_k: int,
    ) -> List[Tuple[int, int, float]]:
        """Rank candidate pairs (Stage 2).

        For every region group:
          1. Apply the degree quality floor (implementation rule, not
             scientific eligibility).
          2. Build an inverted partner index (partner -> neurons) from the
             full partner sets (successors ∪ predecessors).
          3. Every pair co-occurring in a bucket shares >= 1 partner by
             construction; apply the soma-side pair filter, the shared-partner
             floor, the Jaccard floor, and dedup.
        Finally keep the top-K pairs per neuron, and return all kept pairs
        sorted by Jaccard descending.

        Returns:
            ``[(root_a, root_b, jaccard), ...]`` with ``root_a < root_b``.
        """
        successors = lookup.successors
        predecessors = lookup.predecessors
        node_attrs = lookup.node_attrs

        # Partner sets + degree (computed once, O(V + E)).
        partner_sets: Dict[int, frozenset] = {}
        degrees: Dict[int, int] = {}
        for root in lookup.node_set:
            succ = successors.get(root, [])
            pred = predecessors.get(root, [])
            partner_sets[root] = frozenset(set(succ) | set(pred))
            degrees[root] = len(succ) + len(pred)

        pair_scores: Dict[Tuple[int, int], float] = {}

        for group in region_groups:
            eligible = [
                r for r in group if degrees.get(r, 0) >= degree_threshold
            ]
            if len(eligible) < 2:
                continue

            # Inverted partner index (only eligible neurons of this group).
            inv: Dict[Any, List[int]] = {}
            for root in eligible:
                for partner in partner_sets.get(root, ()):
                    inv.setdefault(partner, []).append(root)

            for bucket in inv.values():
                if len(bucket) < 2:
                    continue
                arr = sorted(set(bucket))
                if len(arr) < 2:
                    continue
                for i in range(len(arr)):
                    for j in range(i + 1, len(arr)):
                        a, b = arr[i], arr[j]
                        if (
                            soma_side_constraint
                            and not self._soma_compatible(node_attrs, a, b)
                        ):
                            continue
                        key = (a, b)
                        if key in pair_scores:
                            continue  # already ranked (dedup)
                        shared = partner_sets[a] & partner_sets[b]
                        if len(shared) < min_shared_partners:
                            continue
                        jac = _jaccard(partner_sets[a], partner_sets[b])
                        if jac < jaccard_min:
                            continue
                        pair_scores[key] = jac

        if not pair_scores:
            return []

        # ── Top-K per neuron (candidate-enumeration bound) ───────────────
        by_neuron: Dict[int, List[Tuple[int, float]]] = {}
        for (a, b), jac in pair_scores.items():
            by_neuron.setdefault(a, []).append((b, jac))
            by_neuron.setdefault(b, []).append((a, jac))

        keep: set = set()
        for _root, lst in by_neuron.items():
            lst.sort(key=lambda t: -t[1])
            for partner, _ in lst[:top_k]:
                keep.add((min(_root, partner), max(_root, partner)))

        candidates = [
            (a, b, pair_scores[(a, b)]) for (a, b) in sorted(keep)
        ]
        candidates.sort(key=lambda t: -t[2])
        return candidates

    # ------------------------------------------------------------------ #
    # Sampling (weighted, without replacement, disjoint)                   #
    # ------------------------------------------------------------------ #

    def _sample_pairs(
        self,
        candidates: List[Tuple[int, int, float]],
        target_k: int,
        lookup: Any,
        max_retries: int,
        rng: np.random.Generator,
    ) -> Tuple[List[Tuple[int, int, float]], int, int]:
        """Sample *target_k* disjoint pairs.

        - A weighted draw (probability proportional to Jaccard) without
          replacement over the candidate table.
        - A disjointness pass (a neuron participates in at most one merge);
          conflicting pairs are counted as rejected.
        - A bounded greedy fill of the shortfall from the remaining
          candidates (sorted by Jaccard), so the achieved count stays as
          close to the target as the candidate pool allows.
        - Pairs whose merge would produce an isolated vertex (zero
          re-attached edges) are rejected.

        Returns:
            ``(selected, rejected, retries_used)``.  Note that
            ``retries_used`` counts only the greedy-fill *attempts*
            (candidates skipped during the shortfall fill); rejections
            during the weighted draw are counted in ``rejected`` instead.
        """
        n = len(candidates)
        selected: List[Tuple[int, int, float]] = []
        used: set = set()
        rejected = 0

        if target_k >= n:
            draw_order = list(range(n))
        else:
            weights = np.array([c[2] for c in candidates], dtype=np.float64)
            wsum = float(weights.sum())
            probs = weights / wsum if wsum > 0 else None
            draw_order = rng.choice(
                n, size=target_k, replace=False, p=probs
            ).tolist()

        # ── Weighted draw + disjointness ─────────────────────────────────
        for i in draw_order:
            a, b, jac = candidates[i]
            if a in used or b in used:
                rejected += 1
                continue
            if self._merge_isolated(lookup, a, b):
                rejected += 1
                continue
            used.add(a)
            used.add(b)
            selected.append((a, b, jac))

        # ── Bounded greedy fill of the shortfall ─────────────────────────
        shortfall = target_k - len(selected)
        attempts = 0
        for a, b, jac in candidates:
            if shortfall <= 0:
                break
            if attempts >= max_retries * max(target_k, 1):
                break
            if a in used or b in used:
                attempts += 1
                continue
            if self._merge_isolated(lookup, a, b):
                attempts += 1
                continue
            used.add(a)
            used.add(b)
            selected.append((a, b, jac))
            shortfall -= 1

        return selected, rejected, attempts

    # ------------------------------------------------------------------ #
    # Per-pair merge statistics (descriptive plan entries)                 #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _merge_isolated(lookup: Any, a: int, b: int) -> bool:
        """True when merging (a, b) would leave the merged vertex isolated.

        ``incident`` counts every directed edge once per endpoint it touches.
        Each A<->B self-loop edge is therefore counted twice (once as a
        successor of one side, once as a predecessor of the other), and every
        such edge is dropped after the merge — so it must be subtracted twice
        before checking whether any re-attached edge remains.
        """
        succ_a = set(lookup.successors.get(a, []))
        pred_a = set(lookup.predecessors.get(a, []))
        succ_b = set(lookup.successors.get(b, []))
        pred_b = set(lookup.predecessors.get(b, []))
        self_loops = (1 if b in succ_a else 0) + (1 if a in succ_b else 0)
        incident = len(succ_a) + len(pred_a) + len(succ_b) + len(pred_b)
        return (incident - 2 * self_loops) <= 0

    def _merge_stats(
        self,
        prepared: PreparedGraph,
        a: int,
        b: int,
    ) -> Dict[str, Any]:
        """Per-pair merge statistics, computed edge-exactly from the igraph.

        This is the descriptive counterpart of the runner's re-attachment
        logic, so the two can never disagree.  Every **physical** edge is
        counted (the BANC-family datasets contain parallel edges: multiple
        connection rows for the same directed pair), so ``self_loops_dropped``
        is the exact number of edges the runner removes, not the number of
        distinct directions.

        Accounting contract (matches the runner exactly):

        - ``self_loops_dropped``: edges whose **both** endpoints lie inside
          ``{a, b}`` (A->B, B->A, and any baseline self-loops on a or b).
          Each physical edge counts once — parallel A->B edges count
          individually.
        - ``internal_synapses_dropped``: sum of the ``syn_count`` weights of
          exactly those dropped edges (per-edge, so parallel edges sum their
          weights instead of collapsing to one).
        - ``edges_reattached``: physical edges touching a or b with at least
          one endpoint outside the pair; each counted once.
        - ``parallel_pairs_collapsed``: ``edges_reattached`` minus the number
          of **distinct** remapped ``(src, dst)`` keys (a and b both remap to
          the merged vertex).  On a simple graph this reduces to the number
          of shared-partner directions ``|succ_a ∩ succ_b| + |pred_a ∩ pred_b|``
          (unchanged behaviour); on a graph with parallel edges it also
          counts multiplicity collapses.  Edges between two *different*
          merge pairs are seen by both pairs, so the per-pair value can
          double-count their multiplicity; the runner records the exact
          global collapse total into ``perturbation_metadata`` after
          construction, which is the authoritative number.
        """
        graph = prepared.graph
        lookup = prepared.lookup
        ia = lookup.id_to_idx.get(a)
        ib = lookup.id_to_idx.get(b)
        if ia is None or ib is None:
            # Cannot occur for pairs sampled from lookup.node_set, but mirror
            # the runner's defensive guard: return zeroed stats instead of
            # crashing on graph.incident(None).
            return {
                "merge_id": _merge_id(a, b),
                "source_ids": [a, b],
                "edges_reattached": 0,
                "parallel_pairs_collapsed": 0,
                "self_loops_dropped": 0,
                "internal_synapses_dropped": 0,
            }

        weight_attr = (
            "syn_count" if "syn_count" in graph.edge_attributes()
            else ("weight" if "weight" in graph.edge_attributes() else None)
        )

        # Every physical edge incident to either absorbed neuron (once).
        incident_idx: set = set(graph.incident(ia, mode="all"))
        incident_idx |= set(graph.incident(ib, mode="all"))

        self_loops = 0
        internal_synapses = 0
        edges_reattached = 0
        remapped_keys: set = set()
        for eidx in incident_idx:
            e = graph.es[eidx]
            s_root = graph.vs[e.source]["root_id"]
            t_root = graph.vs[e.target]["root_id"]
            in_pair = (e.source in (ia, ib)) and (e.target in (ia, ib))
            if in_pair:
                self_loops += 1
                if weight_attr is not None:
                    w = e[weight_attr]
                    internal_synapses += int(w) if w is not None else 0
            else:
                edges_reattached += 1
                ks = "M" if e.source in (ia, ib) else s_root
                kt = "M" if e.target in (ia, ib) else t_root
                remapped_keys.add((ks, kt))

        return {
            "merge_id": _merge_id(a, b),
            "source_ids": [a, b],
            "edges_reattached": edges_reattached,
            "parallel_pairs_collapsed": edges_reattached - len(remapped_keys),
            "self_loops_dropped": self_loops,
            "internal_synapses_dropped": internal_synapses,
        }


# ---------------------------------------------------------------------------
# Auto-registration (identical pattern to EM1–EM4)
# ---------------------------------------------------------------------------

from ..common.error_registry import registry  # noqa: E402

registry.register(MergeErrorsModel, overwrite=True)
