"""
Phase TBD – Synapse Count Measurement Error Model
====================================================
Simulates measurement uncertainty in synaptic weight estimation without
altering graph topology.  Every edge receives Gaussian noise proportional
to its original weight, rounded to the nearest integer, and clamped to ≥ 1.

Error rates are interpreted as **relative measurement uncertainty**, not
fraction of edges modified.  E.g. 5 % means σ = 0.05 × original_weight.

Scientific assumptions (stated in methodology):
  1. The connection is correctly detected — only its strength is uncertain.
  2. Measurement uncertainty ≈ zero-mean Gaussian (Central Limit Theorem
     on many small independent error sources).
  3. Uncertainty scales with connection strength: σ = error_rate × syn_count.
  4. Synapse counts are discrete — weights are rounded to integers.
  5. A minimum weight of 1 prevents overlap with Error Model 1
     (missed synapses).
"""

from __future__ import annotations

import logging
from typing import Any, Dict

import numpy as np

from ..common.base_error_model import BaseErrorModel
from ..common.error_result import ErrorResult
from modules.preprocessing.common.prepared_graph import PreparedGraph

logger = logging.getLogger(__name__)


class SynapseCountMeasurementError(BaseErrorModel):
    """Perturbs edge weights with zero-mean Gaussian measurement noise.

    The model operates on **every** edge in the graph::

        σ = error_rate × original_weight
        new_weight = round(clamp(original_weight + N(0, σ²), min=1))

    Graph topology (nodes, edges, connectivity) is **never** modified.
    Only the edge weight attribute (``syn_count`` or ``weight``) changes.
    """

    NAME = "synapse_count_measurement"

    def _perturb(
        self,
        prepared: PreparedGraph,
        config: Dict[str, Any],
        result: ErrorResult,
        rng: np.random.Generator,
    ) -> None:
        """Execute the synapse-count measurement perturbation.

        Args:
            prepared: The immutable baseline
                :class:`~modules.preprocessing.common.prepared_graph.PreparedGraph`.
            config:   Configuration dict containing ``error_rate``
                      (interpreted as relative measurement uncertainty).
            result:   Pre-initialised
                :class:`~modules.error_models.common.error_result.ErrorResult`
                to populate with ``weight_updates``.
            rng:      NumPy random generator (seeded by the framework).

        Raises:
            ValueError: If ``error_rate`` is outside [0.0, 1.0] or if the
                        graph has no weight attribute.
        """
        # ── Parse error rate (relative measurement uncertainty) ──────────
        error_rate = float(config.get("error_rate", 0.0))
        if not 0.0 <= error_rate <= 1.0:
            raise ValueError(
                f"[SynapseCount] error_rate must be in [0.0, 1.0], got {error_rate}. "
                "For this model, error_rate is the relative measurement "
                "uncertainty applied to every edge weight."
            )

        # ── Extract original weights ─────────────────────────────────────
        graph = prepared.graph

        if "syn_count" in graph.edge_attributes():
            original_weights = np.array(graph.es["syn_count"], dtype=np.float64)
        elif "weight" in graph.edge_attributes():
            original_weights = np.array(graph.es["weight"], dtype=np.float64)
        else:
            raise ValueError(
                "[SynapseCount] No 'syn_count' or 'weight' edge attribute "
                "found on the baseline graph."
            )

        n_edges = len(original_weights)

        # ── Perturbation ─────────────────────────────────────────────────
        # σ = error_rate × original_weight (proportional uncertainty model).
        sigma = error_rate * original_weights
        sigma = np.maximum(sigma, 1e-10)  # avoid zero-σ for weight == 0

        noise = rng.normal(loc=0.0, scale=sigma)
        new_weights = np.round(original_weights + noise).astype(np.int64)
        new_weights = np.maximum(new_weights, 1)  # Minimum weight = 1

        # ── Build weight_updates dict ────────────────────────────────────
        # Only record edges that actually changed.
        original_int = original_weights.astype(np.int64)
        changed_mask = new_weights != original_int
        changed_indices = np.nonzero(changed_mask)[0]

        weight_updates: Dict[int, float] = {}
        for idx in changed_indices:
            weight_updates[int(idx)] = int(new_weights[idx])

        # ── Quality-control statistics ───────────────────────────────────
        total_original = original_weights.sum()
        total_new = new_weights.sum()
        signed_error = (new_weights - original_weights).sum()
        abs_error = np.abs(new_weights - original_weights).sum()
        mse = np.mean((new_weights - original_weights) ** 2)
        rmse = float(np.sqrt(mse))
        pct_changed = float(len(changed_indices)) / n_edges * 100 if n_edges > 0 else 0.0

        # Validation checks
        if n_edges > 0:
            assert new_weights.min() >= 1, f"[SynapseCount] Minimum weight {new_weights.min()} < 1"
            assert (new_weights >= 0).all(), "[SynapseCount] Negative weight produced"

        # ── Populate result ──────────────────────────────────────────────
        result.weight_updates = weight_updates
        result.perturbation_metadata = {
            "error_rate": error_rate,
            "original_total_synapses": int(total_original),
            "perturbed_total_synapses": int(total_new),
            "relative_weight_change": float(
                (total_new - total_original) / total_original
            ) if total_original > 0 else 0.0,
            "mean_signed_error": float(signed_error / n_edges) if n_edges > 0 else 0.0,
            "mean_absolute_error": float(abs_error / n_edges) if n_edges > 0 else 0.0,
            "rmse": rmse,
            "pct_edges_changed": pct_changed,
            "edges_changed": int(len(changed_indices)),
            "edges_unchanged": n_edges - int(len(changed_indices)),
        }

        logger.info(
            "[SynapseCount] Perturbation complete. error_rate=%.4f "
            "total_synapses=%d→%d (%.2f%%) edges_changed=%d/%d",
            error_rate,
            int(total_original), int(total_new),
            (total_new - total_original) / total_original * 100
            if total_original > 0 else 0.0,
            int(len(changed_indices)), n_edges,
        )


# ---------------------------------------------------------------------------
# Auto-registration
# ---------------------------------------------------------------------------

from ..common.error_registry import registry
registry.register(SynapseCountMeasurementError, overwrite=True)
