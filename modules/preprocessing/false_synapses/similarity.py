"""
Phase TBD – False Synapses / Similarity
==========================================
Pure set-based Jaccard similarity functions for ranking false-synapse
candidate edges.

All functions operate on Python ``set[int]`` objects (biological root_id
values) and return plain ``float`` scores in [0.0, 1.0].

The two scores are kept independent — they are **never** combined into a
weighted composite.  Callers choose which to use (or report both separately).

Scientific justification:
    **Jaccard_out (successor overlap)** — If two neurons A and B project to
    many of the same postsynaptic targets, they participate in overlapping
    downstream circuits.  False-positive reconstruction errors are more
    plausible between functionally related neurons.

    **Jaccard_in (predecessor overlap)** — If two neurons A and B receive
    input from many of the same presynaptic sources, they share upstream
    circuitry.  This provides complementary evidence.

    Reporting both scores separately (rather than combining them with
    arbitrary weights) allows the experimenter to evaluate each dimension
    independently or use one as a tiebreaker.
"""

from __future__ import annotations

from typing import AbstractSet


# ---------------------------------------------------------------------------
# Jaccard similarity
# ---------------------------------------------------------------------------

def jaccard(
    set_a: AbstractSet[int],
    set_b: AbstractSet[int],
) -> float:
    """Return the Jaccard similarity between *set_a* and *set_b*.

    Jaccard(A, B) = |A ∩ B| / |A ∪ B|

    Returns 0.0 when both sets are empty (edge case: no information about
    shared neighbours for isolated vertices).

    Args:
        set_a: First set of neighbour root_ids.
        set_b: Second set of neighbour root_ids.

    Returns:
        A float in [0.0, 1.0].
    """
    if not set_a and not set_b:
        return 0.0
    union_len = len(set_a | set_b)
    if union_len == 0:
        return 0.0
    return len(set_a & set_b) / union_len


# ---------------------------------------------------------------------------
# Directed Jaccard wrappers
# ---------------------------------------------------------------------------

def jaccard_out(
    pre_a: int,
    pre_b: int,
    successors: dict[int, list[int]],
) -> float:
    """Jaccard similarity of the **out-neighbour** (successor) sets of two
    presynaptic neurons.

    ``J_out(a, b) = Jaccard(succ(a), succ(b))``

    This measures **functional similarity**: how much the two neurons
    converge onto the same postsynaptic targets.

    Args:
        pre_a:       Root ID of the first presynaptic neuron.
        pre_b:       Root ID of the second presynaptic neuron.
        successors:  ``{root_id: [neighbour_root_id, ...]}`` from
                     :class:`~modules.preprocessing.common.lookup.GraphLookup.successors`.

    Returns:
        A float in [0.0, 1.0].
    """
    set_a = set(successors.get(pre_a, []))
    set_b = set(successors.get(pre_b, []))
    return jaccard(set_a, set_b)


def jaccard_in(
    post_a: int,
    post_b: int,
    predecessors: dict[int, list[int]],
) -> float:
    """Jaccard similarity of the **in-neighbour** (predecessor) sets of two
    postsynaptic neurons.

    ``J_in(a, b) = Jaccard(pred(a), pred(b))``

    This measures **input similarity**: how much the two neurons receive
    input from the same presynaptic sources.

    Args:
        post_a:       Root ID of the first postsynaptic neuron.
        post_b:       Root ID of the second postsynaptic neuron.
        predecessors: ``{root_id: [neighbour_root_id, ...]}`` from
                      :class:`~modules.preprocessing.common.lookup.GraphLookup.predecessors`.

    Returns:
        A float in [0.0, 1.0].
    """
    set_a = set(predecessors.get(post_a, []))
    set_b = set(predecessors.get(post_b, []))
    return jaccard(set_a, set_b)


def jaccard_both(
    pre_a: int,
    pre_b: int,
    successors: dict[int, list[int]],
    predecessors: dict[int, list[int]],
) -> tuple[float, float]:
    """Convenience wrapper that returns both ``(jaccard_out, jaccard_in)``
    for a candidate pair ``(pre_a, pre_b)``.

    The two scores are returned independently.  Neither is modified.

    Returns:
        ``(j_out, j_in)``.
    """
    return (
        jaccard_out(pre_a, pre_b, successors),
        jaccard_in(pre_a, pre_b, predecessors),
    )
