"""
Phase TBD – False Synapses / Candidate Generator
===================================================
One-time preprocessing step that builds a ranked candidate edge table for the
False Synapse error model using an **inverted successor index**.

Algorithm (per region):
  1. Retrieve neurons belonging to the region via
     ``prepared.lookup.node_attr_index["top_region"]``.
  2. Build an inverted index: for each postsynaptic target neuron in the
     region, collect all presynaptic neurons that connect to it.
  3. For every target with ≥2 presynaptic partners, generate all unordered
     *(pre_a, pre_b)* pairs — these are neurons that share at least one
     common postsynaptic target.
  4. Discard pairs that are already an existing edge in the baseline graph.
  5. Compute ``jaccard_out`` and ``jaccard_in`` separately (never combined).
  6. Keep Top-*K* candidates per region sorted by ``jaccard_out`` descending.
  7. Merge all per-region Parquet files into a single cached table.

The resulting ``candidates.parquet`` file is consumed by
:class:`~modules.error_models.false_synapses.model.FalseSynapseModel`
during every trial — candidate generation is **never** repeated.

Scientific justification for the inverted-index approach:
  Restricting candidate pairs to those sharing at least one common neighbour
  is a biologically motivated filter, not merely an algorithmic optimisation.
  In the fly connectome, neurons that share postsynaptic targets participate
  in overlapping circuits and are statistically more likely to form synapses.
  This is consistent with the "guilt by association" principle in link
  prediction for biological networks (Liben-Nowell & Kleinberg 2007).
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, Optional

import numpy as np
import polars as pl

from modules.preprocessing.common.prepared_graph import PreparedGraph
from modules.preprocessing.common.lookup import GraphLookup
from modules.preprocessing.false_synapses.similarity import jaccard_out, jaccard_in
from modules.preprocessing.false_synapses.config import (
    FALSE_SYNAPSE_CONFIG,
    CACHE_DIR,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# CandidateGenerator
# ---------------------------------------------------------------------------

class CandidateGenerator:
    """One-time generator of ranked false-synapse candidate edges.

    Builds candidate pairs from the immutable baseline
    :class:`~modules.preprocessing.common.prepared_graph.PreparedGraph`
    and caches them to a Parquet file for reuse across all trials.

    Args:
        prepared:
            The preprocessed baseline graph.  Only the
            :class:`~modules.preprocessing.common.lookup.GraphLookup`
            (successors, predecessors, edge_weight, node_attr_index) is
            used — the underlying igraph graph is never touched.
    """

    def __init__(
        self,
        prepared: PreparedGraph,
        config: Optional[dict] = None,
    ) -> None:
        """
        Args:
            prepared:
                The preprocessed baseline graph.
            config:
                Optional overrides for
                :data:`~modules.preprocessing.false_synapses.config.FALSE_SYNAPSE_CONFIG`.
                Merged on top of the defaults.
        """
        self._prepared = prepared
        self._lookup: GraphLookup = prepared.lookup
        self._cfg: dict = {**FALSE_SYNAPSE_CONFIG, **(config or {})}
        logger.info(
            "[CandidateGenerator] Initialised for dataset '%s' "
            "(%d neurons, %d edges).",
            prepared.dataset_name,
            prepared.metadata.node_count,
            prepared.metadata.edge_count,
        )

    # ------------------------------------------------------------------
    # Public entry-point
    # ------------------------------------------------------------------

    def generate(
        self,
        cache_path: Optional[Path] = None,
    ) -> Path:
        """Run candidate generation and write the ranked table to disk.

        Args:
            cache_path:
                Path for the output ``candidates.parquet`` file.  If
                ``None``, defaults to ``{CACHE_DIR}/candidates.parquet``.

        Returns:
            The path to the written Parquet file.
        """
        if cache_path is None:
            cache_dir = Path(CACHE_DIR)
            cache_dir.mkdir(parents=True, exist_ok=True)
            cache_path = cache_dir / "candidates.parquet"

        t_start = time.perf_counter()

        # Retrieve region → [neurons] mapping from the lookup index.
        region_index = self._lookup.node_attr_index.get("top_region", {})
        if not region_index:
            logger.error(
                "[CandidateGenerator] No 'top_region' index available — "
                "ensure index_node_attrs includes 'top_region' during preprocessing."
            )
            raise ValueError(
                "GraphLookup has no 'top_region' attribute index. "
                "Cannot run candidate generation without region metadata."
            )

        logger.info(
            "[CandidateGenerator] Processing %d regions.",
            len(region_index),
        )

        all_fragments: list[pl.DataFrame] = []
        total_candidates = 0

        for region, neurons in sorted(
            region_index.items(), key=lambda x: -len(x[1])
        ):
            fragment = self._process_region(region, set(neurons))
            if fragment is not None:
                n = len(fragment)
                if n > 0:
                    all_fragments.append(fragment)
                    total_candidates += n
                    logger.info(
                        "[CandidateGenerator] Region %-25s → %8d candidates "
                        "(out of %d neurons).",
                        region, n, len(neurons),
                    )

        if not all_fragments:
            logger.warning(
                "[CandidateGenerator] No candidates generated for any region."
            )
            # Write empty table with correct schema.
            empty = pl.DataFrame(
                schema={
                    "pre_root_id": pl.Int64,
                    "post_root_id": pl.Int64,
                    "jaccard_out": pl.Float64,
                    "jaccard_in": pl.Float64,
                    "region": pl.Utf8,
                },
            )
            empty.write_parquet(str(cache_path))
            return cache_path

        # Merge all per-region fragments.
        logger.info(
            "[CandidateGenerator] Merging %d region fragments "
            "(%s total candidates) ...",
            len(all_fragments), f"{total_candidates:,}",
        )
        merged = pl.concat(all_fragments)

        # Sort globally by jaccard_out descending.
        merged = merged.sort("jaccard_out", descending=True)

        # Write to Parquet.
        merged.write_parquet(str(cache_path))
        elapsed = time.perf_counter() - t_start

        logger.info(
            "[CandidateGenerator] Done. %s candidates written to %s "
            "in %.1f s.",
            f"{len(merged):,}", cache_path, elapsed,
        )
        return cache_path

    # ------------------------------------------------------------------
    # Per-region processing
    # ------------------------------------------------------------------

    def _process_region(
        self,
        region: str,
        neuron_ids: set[int],
    ) -> Optional[pl.DataFrame]:
        """Generate candidate pairs for a single anatomical *region*.

        Steps (all within the region):
          1. Build in-region successor map (edges where both ends ∈ region).
          2. Build inverted successor index: target → [presynaptic neurons].
          3. For each target with ≥2 presynaptic partners:
             a. Generate all unordered pairs (pre_a, pre_b) via combinations.
             b. Skip if (pre_a, pre_b) is an existing edge.
             c. Compute jaccard_out and jaccard_in.
             d. Keep if jaccard_out ≥ jaccard_min.
          4. Sort by jaccard_out descending, keep Top-K per region.

        Args:
            region:     Region name.
            neuron_ids: Set of neuron root IDs belonging to this region.

        Returns:
            A Polars DataFrame with columns
            ``(pre_root_id, post_root_id, jaccard_out, jaccard_in, region)``
            or ``None`` if the region is too small or produces no candidates.
        """
        cfg = self._cfg
        min_size = cfg["min_region_size"]
        min_shared = cfg["min_shared_neighbors"]
        jaccard_min = cfg["jaccard_min"]
        top_k = max(1, cfg["top_k_multiplier"] * len(neuron_ids))

        if len(neuron_ids) < min_size:
            return None

        successors = self._lookup.successors
        predecessors = self._lookup.predecessors
        edge_weight = self._lookup.edge_weight

        # --- 1. Build in-region successor map ---
        # Only consider edges where both pre and post are in this region.
        reg_succ: dict[int, set[int]] = {}
        for nid in neuron_ids:
            raw = successors.get(nid, [])
            in_region = [s for s in raw if s in neuron_ids]
            if in_region:
                reg_succ[nid] = set(in_region)

        if not reg_succ:
            return None

        # --- 2. Inverted successor index ---
        inv_idx: dict[int, set[int]] = {}
        for pre, succ_set in reg_succ.items():
            for post in succ_set:
                if post not in inv_idx:
                    inv_idx[post] = set()
                inv_idx[post].add(pre)

        # --- 3. Generate candidate pairs ---
        import itertools

        candidates_pre: list[int] = []
        candidates_post: list[int] = []
        candidates_j_out: list[float] = []
        candidates_j_in: list[float] = []

        for target, preds in inv_idx.items():
            if len(preds) < max(2, min_shared):
                continue

            # All unordered pairs within this target's predecessors.
            for pre_a, pre_b in itertools.combinations(preds, 2):
                # Skip existing edges.
                if (pre_a, pre_b) in edge_weight:
                    continue
                if (pre_b, pre_a) in edge_weight and cfg.get("redundancy_filter", True):
                    # For redundant pairs, keep the direction with higher J_out.
                    pass

                j_out = jaccard_out(pre_a, pre_b, successors)
                if j_out < jaccard_min:
                    continue

                j_in = jaccard_in(pre_a, pre_b, predecessors)

                candidates_pre.append(pre_a)
                candidates_post.append(pre_b)
                candidates_j_out.append(j_out)
                candidates_j_in.append(j_in)

        if not candidates_pre:
            return None

        df = pl.DataFrame({
            "pre_root_id": candidates_pre,
            "post_root_id": candidates_post,
            "jaccard_out": candidates_j_out,
            "jaccard_in": candidates_j_in,
        })

        # --- 4. Sort and apply Top-K ---
        df = df.sort("jaccard_out", descending=True)
        if len(df) > top_k:
            df = df.head(top_k)

        df = df.with_columns(pl.lit(region).alias("region"))

        return df
