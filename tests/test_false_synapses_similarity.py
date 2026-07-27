"""
Tests for :mod:`modules.preprocessing.false_synapses.similarity`.
"""

from modules.preprocessing.false_synapses.similarity import (
    jaccard,
    jaccard_out,
    jaccard_in,
    jaccard_both,
)


# ---------------------------------------------------------------------------
# jaccard (pure set-based helper)
# ---------------------------------------------------------------------------

def test_jaccard_identical_sets() -> None:
    assert jaccard({1, 2, 3}, {1, 2, 3}) == 1.0


def test_jaccard_disjoint_sets() -> None:
    assert jaccard({1, 2, 3}, {4, 5, 6}) == 0.0


def test_jaccard_partial_overlap() -> None:
    result = jaccard({1, 2, 3}, {2, 3, 4})
    # |intersection| = 2, |union| = 4 → 0.5
    assert abs(result - 0.5) < 1e-12


def test_jaccard_empty_sets() -> None:
    assert jaccard(set(), set()) == 0.0


def test_jaccard_one_empty() -> None:
    """Jaccard with one empty set: |intersection| = 0, |union| = size of non-empty."""
    result = jaccard({1, 2, 3}, set())
    assert result == 0.0


def test_jaccard_singleton_same() -> None:
    assert jaccard({42}, {42}) == 1.0


# ---------------------------------------------------------------------------
# jaccard_out
# ---------------------------------------------------------------------------

def test_jaccard_out_basic() -> None:
    succ = {
        1: [10, 20, 30],
        2: [20, 30, 40],
        3: [50, 60],
    }
    # Jaccard({10,20,30}, {20,30,40}) = 2 / 4 = 0.5
    result = jaccard_out(1, 2, succ)
    assert abs(result - 0.5) < 1e-12


def test_jaccard_out_disjoint() -> None:
    succ = {1: [10, 20], 2: [30, 40]}
    assert jaccard_out(1, 2, succ) == 0.0


def test_jaccard_out_missing_key() -> None:
    succ = {1: [10, 20]}
    result = jaccard_out(1, 999, succ)
    assert result == 0.0


# ---------------------------------------------------------------------------
# jaccard_in
# ---------------------------------------------------------------------------

def test_jaccard_in_basic() -> None:
    pred = {
        1: [100, 200],
        2: [200, 300],
    }
    # Jaccard({100,200}, {200,300}) = 1 / 3 ≈ 0.333...
    result = jaccard_in(1, 2, pred)
    assert abs(result - (1.0 / 3.0)) < 1e-12


def test_jaccard_in_missing_key() -> None:
    pred = {1: [100, 200]}
    assert jaccard_in(1, 999, pred) == 0.0


# ---------------------------------------------------------------------------
# jaccard_both
# ---------------------------------------------------------------------------

def test_jaccard_both_returns_tuple() -> None:
    succ = {1: [10, 20, 30], 2: [20, 30, 40]}
    pred = {1: [100, 200], 2: [200, 300]}
    j_out, j_in = jaccard_both(1, 2, succ, pred)
    assert isinstance(j_out, float)
    assert isinstance(j_in, float)
    assert j_out > 0.0
    assert j_in > 0.0


def test_jaccard_both_identical() -> None:
    succ = {1: [10, 20], 2: [10, 20]}
    pred = {1: [100], 2: [100]}
    j_out, j_in = jaccard_both(1, 2, succ, pred)
    assert j_out == 1.0
    assert j_in == 1.0
