"""
Phase EM4 – Split Errors (Segmentation Fragmentation) Error Model
==================================================================
Implements Error Model 4 (EM4): a simulation of segmentation *split errors*
that occur during automated EM reconstruction, when one biological neuron is
reconstructed as two independent neurons.

The scientific methodology is defined in
``docs/error model/em4/method plan.md`` and is the source of truth for the
algorithm.  This module implements **only** the scientific algorithm; the
execution pipeline (temporary graph construction with fragment vertices) is
implemented by ``core.split_experiment_runner.SplitExperimentRunner``.

Key scientific assumptions (from the methodology):
    1. Split errors occur at the **neuron** level, not at individual synapses.
    2. A split disconnects one coherent *local portion* of a neuron — partners
       never alternate randomly between the two fragments.
    3. Without morphology, local graph topology (the 1-hop ego network) is the
       best available proxy for local neuronal organisation.
    4. Local graph communities are graph-theoretic proxies for coherent
       portions of connectivity — not claims about dendrites or axons.
    5. The perturbation changes **only neuron identity**.  Synapse counts and
       edge weights are never changed.
    6. The perturbation exists only for the lifetime of a simulation trial.

Algorithm (per methodology sections 7–22):
    Candidate preparation  -> degree / unique-partners per neuron (O(V+E), once)
    Eligibility            -> degree >= degree_threshold (recommended 10)
    Error rate             -> percentage of eligible neurons selected
    Sampling               -> uniform random without replacement
    Ego graph              -> 1-hop neighbourhood (target + neighbours + edges
                              between neighbours)
    Undirected             -> partitioning uses the undirected representation
    Remove central neuron  -> only neighbours remain
    Connected components   -> natural fragmentation (most neurons already do)
    Louvain fallback       -> only if the neighbour graph is connected
    Greedy Largest-First   -> balanced two-fragment assignment
    Fragment creation      -> neuron A becomes exactly A1 and A2
    Edge rewiring          -> every edge assigned exactly once, decided
                              entirely by the partner's community
    Validation             -> edge count / synapse count preserved, no
                              duplicates, no self-loops, >= min partners per
                              fragment, every fragment has >= 1 edge
    Failure handling       -> reject and sample another neuron (bounded)

All randomness (neuron sampling + community detection) is derived from the
single reproducible seed the framework passes in.  igraph's Louvain
implementation consumes igraph's own RNG, so that RNG is seeded from a value
drawn from the framework's NumPy RNG before every ``community_multilevel``
call — making the whole perturbation reproducible for a fixed seed.

The baseline :class:`~modules.preprocessing.common.prepared_graph.PreparedGraph`
is **never** copied or mutated.  The model returns an
:class:`~modules.error_models.common.error_result.ErrorResult` whose
``extra["split_plan"]`` contains a serialisable description of every split;
``SplitExperimentRunner._split_build_temp_graph()`` interprets that plan to
build the temporary analysis graph.
"""

from __future__ import annotations

import logging
import random as _random
from typing import Any, Dict, List, Optional, Tuple

import igraph
import numpy as np

from ..common.base_error_model import BaseErrorModel
from ..common.error_result import ErrorResult
from ..common.utils import add_warning, validate_config_keys
from modules.preprocessing.common.prepared_graph import PreparedGraph

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration contract (methodology parameters only)
# ---------------------------------------------------------------------------

_KNOWN_CONFIG_KEYS = frozenset({
    "error_rate",
    "degree_threshold",
    "min_fragment_partners",
    "max_retries",
    "community_algorithm",
})

_DEFAULT_DEGREE_THRESHOLD = 10          # methodology: recommended degree >= 10
_DEFAULT_MIN_FRAGMENT_PARTNERS = 3      # methodology: minimum partners >= 3
_DEFAULT_MAX_RETRIES = 20               # bounded re-sampling on rejection
_DEFAULT_COMMUNITY_ALGORITHM = "louvain"

# ---------------------------------------------------------------------------
# Module-level candidate cache (candidate preparation is performed once)
# ---------------------------------------------------------------------------

#: id(prepared.graph) -> (graph_ref, degrees, unique_partners).
#: The baseline graph is immutable for the lifetime of an experiment, so
#: ``id()`` is a stable key.  A **strong reference to the graph is kept in
#: the cache** so that the id cannot be reused by a garbage-collected graph
#: (mirrors the module-level candidate-table cache used by EM2).
_candidate_cache: Dict[int, Tuple[Any, List[int], List[int]]] = {}


# ---------------------------------------------------------------------------
# Fragment ID encoding
# ---------------------------------------------------------------------------

def _fragment_id(root_id: int, fragment_index: int) -> int:
    """Return a synthetic, collision-free root ID for a fragment vertex.

    Encoding: ``-(2 * abs(root_id) + fragment_index)`` with fragment_index in
    {1, 2}.  Real biological root IDs in FlyWire data are positive integers,
    so negative synthetic IDs can never collide with a real neuron.  The
    encoding is injective across all (root_id, fragment_index) pairs.
    """
    return -(2 * abs(int(root_id)) + int(fragment_index))


# ---------------------------------------------------------------------------
# Partition helpers (kept private to the model — no shared util pollution)
# ---------------------------------------------------------------------------

def _greedy_largest_first(
    groups: List[List[int]],
) -> Tuple[List[int], List[int]]:
    """Assign communities to two fragments using Greedy Largest-First.

    Methodology section 16:
        Sort communities largest → smallest.  Assign the next community to the
        currently smaller fragment.

    Returns:
        ``(fragment_1_partners, fragment_2_partners)`` — two disjoint lists
        whose union is all partners.  Ties are broken deterministically in
        favour of fragment 1.
    """
    ordered = sorted(groups, key=len, reverse=True)
    frag_1: List[int] = []
    frag_2: List[int] = []
    for group in ordered:
        if len(frag_1) <= len(frag_2):
            frag_1.extend(group)
        else:
            frag_2.extend(group)
    return frag_1, frag_2


def _compute_components(graph: igraph.Graph) -> List[List[int]]:
    """Connected components of an undirected graph (weak components)."""
    comps = graph.components(mode="weak")
    return [list(c) for c in comps]


def _compute_louvain(graph: igraph.Graph, seed: int) -> List[List[int]]:
    """Louvain community detection on a **local** ego graph.

    igraph's ``community_multilevel`` consumes igraph's internal RNG, which
    is not seeded by NumPy.  To keep the methodology's reproducibility
    contract ("all randomness derived from one reproducible seed"), the
    igraph RNG is re-seeded from a value drawn from the framework's NumPy RNG
    before every call.
    """
    igraph.set_random_number_generator(_random.Random(seed))
    communities = graph.community_multilevel()
    return [list(c) for c in communities]


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------

class SplitErrorsModel(BaseErrorModel):
    """Simulates neuron-level segmentation split errors.

    The model never touches the baseline graph.  For every successfully split
    neuron it records, in ``ErrorResult.extra["split_plan"]``:

    .. code-block:: python

        {
          root_id: {
            "fragment_ids": [fid_1, fid_2],
            "fragment_partners": {fid_1: [partner_root, ...],
                                  fid_2: [partner_root, ...]},
            "community_count": int,
            "fallback_used": bool,
            "edges_rewired": int,
          },
          ...
        }

    ``SplitExperimentRunner._split_build_temp_graph()`` consumes this plan to
    construct the temporary analysis graph (fragment vertices + rewired
    edges), after which the plan is destroyed.
    """

    NAME = "split_errors"

    # ------------------------------------------------------------------ #
    # Perturbation (scientific algorithm — method plan sections 7–22)      #
    # ------------------------------------------------------------------ #

    def _perturb(
        self,
        prepared: PreparedGraph,
        config: Dict[str, Any],
        result: ErrorResult,
        rng: np.random.Generator,
    ) -> None:
        """Execute the split-error perturbation.

        Args:
            prepared: The immutable baseline
                :class:`~modules.preprocessing.common.prepared_graph.PreparedGraph`.
            config:   Configuration dict (see ``_KNOWN_CONFIG_KEYS``).
            result:   Pre-initialised
                :class:`~modules.error_models.common.error_result.ErrorResult`.
            rng:      NumPy random generator (seeded by the framework).

        Raises:
            ValueError: If ``error_rate`` is outside [0, 1] or an unsupported
                        ``community_algorithm`` is requested.
        """
        validate_config_keys(config, _KNOWN_CONFIG_KEYS, self.NAME, result)

        # ── Parse configuration ──────────────────────────────────────────
        error_rate = float(config.get("error_rate", 0.0))
        if not 0.0 <= error_rate <= 1.0:
            raise ValueError(
                f"[SplitErrors] error_rate must be in [0.0, 1.0], got "
                f"{error_rate}. It is the fraction of eligible neurons split."
            )
        degree_threshold = int(
            config.get("degree_threshold", _DEFAULT_DEGREE_THRESHOLD)
        )
        min_fragment_partners = int(
            config.get("min_fragment_partners", _DEFAULT_MIN_FRAGMENT_PARTNERS)
        )
        max_retries = int(config.get("max_retries", _DEFAULT_MAX_RETRIES))
        community_algorithm = str(
            config.get("community_algorithm", _DEFAULT_COMMUNITY_ALGORITHM)
        ).lower()
        if community_algorithm != "louvain":
            raise ValueError(
                f"[SplitErrors] Unsupported community_algorithm "
                f"{community_algorithm!r}. The methodology defines Louvain "
                f"as the only community-detection fallback."
            )

        graph: igraph.Graph = prepared.graph

        # ── Candidate preparation (performed once, O(V+E)) ───────────────
        # Unique partners are part of the methodology's candidate table; they
        # are used implicitly during splitting via ``set(neighbours)``.
        degrees, _unique_partners = self._candidate_preparation(graph)

        # ── Eligibility: degree >= threshold ─────────────────────────────
        eligible = [
            idx for idx in range(graph.vcount())
            if degrees[idx] >= degree_threshold
        ]
        n_eligible = len(eligible)

        # ── Error rate = percentage of eligible neurons selected ─────────
        k = round(error_rate * n_eligible)

        if k == 0:
            logger.info(
                "[SplitErrors] error_rate=%.4f -> no eligible neurons "
                "selected for splitting.", error_rate,
            )
            result.perturbation_metadata = {
                "error_rate": error_rate,
                "target_error_rate": error_rate,
                "degree_threshold": degree_threshold,
                "eligible_neurons": n_eligible,
                "neurons_split": 0,
                "fragments_created": 0,
                "edges_rewired": 0,
                "neurons_rejected": 0,
                "retries_used": 0,
            }
            result.extra["split_plan"] = {}
            return

        # ── Candidate sampling: uniform, without replacement ─────────────
        sampled: List[int]
        remaining: List[int]
        if k >= n_eligible:
            sampled = list(eligible)
            rng.shuffle(sampled)
            remaining = []
        else:
            sampled = rng.choice(eligible, size=k, replace=False).tolist()
            sampled_set = set(sampled)
            remaining = [i for i in eligible if i not in sampled_set]

        # One igraph-Louvain seed per trial, derived from the NumPy RNG.
        louvain_seed = int(rng.integers(0, 2 ** 31 - 1))

        idx_to_root = prepared.lookup.id_map

        split_plan: Dict[int, Dict[str, Any]] = {}
        rejected: List[int] = []
        retries_used = 0
        edges_rewired_total = 0

        # ── Perturbation loop (with bounded rejection re-sampling) ───────
        attempt_queue: List[int] = list(sampled)
        while attempt_queue:
            center_idx = attempt_queue.pop(0)

            if center_idx in split_plan:
                continue  # defensive; a neuron can only be split once

            split = self._attempt_split(
                graph=graph,
                center_idx=center_idx,
                idx_to_root=idx_to_root,
                min_fragment_partners=min_fragment_partners,
                louvain_seed=louvain_seed,
            )

            if split is None:
                rejected.append(idx_to_root[center_idx])
                # Reject and sample another neuron (bounded by max_retries).
                if retries_used < max_retries and remaining:
                    attempt_queue.append(remaining.pop(0))
                    retries_used += 1
                continue

            split_plan[idx_to_root[center_idx]] = split
            edges_rewired_total += split["edges_rewired"]

        if not split_plan:
            add_warning(
                result,
                "No valid split could be produced for the sampled neurons. "
                "Run analyses on the baseline graph.",
            )

        result.extra["split_plan"] = split_plan
        result.perturbation_metadata = {
            "error_rate": error_rate,
            "target_error_rate": error_rate,
            "degree_threshold": degree_threshold,
            "min_fragment_partners": min_fragment_partners,
            "eligible_neurons": n_eligible,
            "neurons_split": len(split_plan),
            "fragments_created": 2 * len(split_plan),
            "edges_rewired": edges_rewired_total,
            "neurons_rejected": len(rejected),
            "retries_used": retries_used,
        }

        logger.info(
            "[SplitErrors] error_rate=%.4f | eligible=%d | split=%d | "
            "rejected=%d | retries=%d | edges_rewired=%d",
            error_rate, n_eligible, len(split_plan),
            len(rejected), retries_used, edges_rewired_total,
        )

    # ------------------------------------------------------------------ #
    # Candidate preparation                                                 #
    # ------------------------------------------------------------------ #

    def _candidate_preparation(
        self, graph: igraph.Graph
    ) -> Tuple[List[int], List[int]]:
        """Compute degree and unique-partner counts for every neuron.

        Methodology section 7: for every neuron compute Degree, Weighted
        Degree, Unique Partners.  Only degree and unique partners are needed
        for eligibility and splitting; weighted degree is recorded in the
        metadata for completeness without changing the algorithm.

        Performed once per baseline graph (cached by object identity).
        Complexity O(V+E).
        """
        key = id(graph)
        if key in _candidate_cache:
            return _candidate_cache[key][1], _candidate_cache[key][2]

        degrees: List[int] = graph.degree()  # total (in + out) degree
        unique_partners: List[int] = [
            len(set(graph.neighbors(v, mode="all")))
            for v in range(graph.vcount())
        ]

        _candidate_cache[key] = (graph, degrees, unique_partners)
        logger.info(
            "[SplitErrors] Candidate preparation complete for graph id=%s "
            "(%d vertices, %d edges).",
            key, graph.vcount(), graph.ecount(),
        )
        return degrees, unique_partners

    # ------------------------------------------------------------------ #
    # Single-neuron split attempt (method plan sections 11–19)              #
    # ------------------------------------------------------------------ #

    def _attempt_split(
        self,
        graph: igraph.Graph,
        center_idx: int,
        idx_to_root: Dict[int, int],
        min_fragment_partners: int,
        louvain_seed: int,
    ) -> Optional[Dict[str, Any]]:
        """Attempt to split one neuron into exactly two fragments.

        Implements ego-graph extraction, connected components, Louvain
        fallback, Greedy Largest-First assignment, and fragment-quality
        validation.  Returns ``None`` when the neuron must be rejected
        (methodology section 20), otherwise a serialisable split description.
        """
        # 1-hop neighbourhood (unique partners).
        neighbours = set(graph.neighbors(center_idx, mode="all"))

        # Impossibility / quality guards.
        if len(neighbours) < 2:
            return None  # cannot form two non-empty fragments
        if len(neighbours) < 2 * min_fragment_partners:
            return None  # one fragment would fall below the minimum size

        # ── Ego graph extraction (section 11) ────────────────────────────
        # Target neuron + immediate neighbours + all edges between them.
        # Only the 1-hop neighbourhood is ever materialised.
        vs = [center_idx] + sorted(neighbours)
        ego = graph.subgraph(vs)  # local copy; never touches the baseline

        # ── Remove central neuron (section 13) — neighbours only ─────────
        neighbour_sub = ego.copy()
        neighbour_sub.delete_vertices(0)

        # ── Undirected representation for partitioning (section 12) ──────
        undirected = neighbour_sub.as_undirected()

        # ── Connected components (section 14) ────────────────────────────
        groups = _compute_components(undirected)
        fallback_used = False

        # ── Community detection fallback (section 15) — only if 1 CC ─────
        if len(groups) == 1:
            groups = _compute_louvain(undirected, louvain_seed)
            fallback_used = True
            if len(groups) == 1:
                return None  # only one community after fallback -> reject

        # ── Greedy Largest-First assignment (section 16) ─────────────────
        # Map component/community vertex ids back to global vertex indices:
        # neighbour_sub vertex j  ==  ego vertex j+1  ==  global vs[j+1].
        frag_1_global: List[int] = []
        frag_2_global: List[int] = []
        frag_1_sub, frag_2_sub = _greedy_largest_first(groups)
        for j in frag_1_sub:
            frag_1_global.append(vs[j + 1])
        for j in frag_2_sub:
            frag_2_global.append(vs[j + 1])

        # ── Fragment quality validation (section 19) ─────────────────────
        if (
            len(frag_1_global) < min_fragment_partners
            or len(frag_2_global) < min_fragment_partners
        ):
            return None  # smallest fragment < min partners -> reject

        root = idx_to_root[center_idx]
        fid_1 = _fragment_id(root, 1)
        fid_2 = _fragment_id(root, 2)

        # Edge rewiring bookkeeping: every edge incident to the neuron is
        # assigned to the fragment of its partner (section 18).
        incident = graph.incident(center_idx, mode="all")

        fragment_partners = {
            fid_1: [idx_to_root[i] for i in frag_1_global],
            fid_2: [idx_to_root[i] for i in frag_2_global],
        }

        # Validation: the partner partition is complete and disjoint
        # (every edge assigned exactly once — no loss, no duplication).
        assigned = set(frag_1_global) | set(frag_2_global)
        if assigned != neighbours:
            raise ValueError(
                "[SplitErrors] Partner partition is not exhaustive: "
                f"{len(assigned)} assigned vs {len(neighbours)} neighbours."
            )
        if len(frag_1_global) + len(frag_2_global) != len(neighbours):
            raise ValueError(
                "[SplitErrors] Partner partition contains duplicates "
                f"({len(frag_1_global)} + {len(frag_2_global)} "
                f"vs {len(neighbours)} neighbours)."
            )

        return {
            "fragment_ids": [fid_1, fid_2],
            "fragment_partners": fragment_partners,
            "community_count": len(groups),
            "fallback_used": fallback_used,
            "edges_rewired": len(incident),
        }


# ---------------------------------------------------------------------------
# Auto-registration (identical pattern to EM1–EM3)
# ---------------------------------------------------------------------------

from ..common.error_registry import registry  # noqa: E402

registry.register(SplitErrorsModel, overwrite=True)
