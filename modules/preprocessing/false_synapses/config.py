"""
Phase TBD – False Synapses / Configuration
=============================================
Centralised constants and defaults for the false-synapse candidate-generation
pipeline.

All thresholds are defined here in one place so they can be modified without
hunting through the codebase.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Candidate generation thresholds
# ---------------------------------------------------------------------------

FALSE_SYNAPSE_CONFIG: dict = {
    # Multiplier applied to the number of neurons in a region to determine
    # the maximum number of candidates to keep for that region.
    # E.g. ``top_k_multiplier × len(region_neurons)`` = candidates per region.
    # For the ME region: 50 × 42 323 ≈ 2.1M candidates.
    "top_k_multiplier": 50,
    # Regions with fewer neurons than this are skipped (too few pairs to
    # produce meaningful candidates).
    "min_region_size": 10,
    # Minimum number of shared common neighbours required to consider a
    # candidate pair.  Pairs sharing zero neighbours are never generated.
    "min_shared_neighbors": 1,
    # Minimum Jaccard_out score for a candidate to be kept in the ranked
    # table (filters out pairs with negligible overlap).
    "jaccard_min": 0.001,
    # Whether to deduplicate (a,b) and (b,a) pairs (only keep the
    # higher-scoring direction).
    "redundancy_filter": True,
}

# ---------------------------------------------------------------------------
# Weight assignment thresholds
# ---------------------------------------------------------------------------

# Maximum syn_count used when building the empirical weight distribution.
# False-positive reconstruction errors are modelled as weak connections,
# consistent with the observation that 71.5 % of BANC edges have ≤5
# synapses.
WEIGHT_THRESHOLD: int = 5

# ---------------------------------------------------------------------------
# Cache / persistence
# ---------------------------------------------------------------------------

# Directory (relative to project root) for the pre-computed candidate table.
CACHE_DIR: str = "research_data/cache/false_synapses"

# ---------------------------------------------------------------------------
# Biological status thresholds
# (Matching the conventions in presentation/preservation_config.py)
# ---------------------------------------------------------------------------

INTEGRITY_THRESHOLDS: dict = {
    "preserved": 99.0,        # ≥99 % → green
    "minor_impact": 95.0,     # 95–99 % → yellow
    "moderate_impact": 90.0,  # 90–95 % → orange
    # <90 % → red (significant disruption)
}
