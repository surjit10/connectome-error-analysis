"""
presentation/root_index_exporter.py
=====================================
Generates the root ``results/index.html`` landing page that links to every
error model.

Design constraints:
    - No statistical computation.
    - No figure generation.
    - Pure HTML rendering from pre-built data structures.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List

from presentation.base_exporter import BaseExporter

logger = logging.getLogger(__name__)

# Human-readable names and descriptions for known error models.
_ERROR_MODEL_META: Dict[str, Dict[str, str]] = {
    "missed_synapses": {
        "display_name": "Missed Synapses",
        "description":  "Simulates topological degradation from false-negative edge removal.",
    },
    "false_positive_synapses": {
        "display_name": "False Positive Synapses",
        "description":  "Simulates spurious edge insertion (false-positive connections).",
    },
    "edge_weight_noise": {
        "display_name": "Edge Weight Noise",
        "description":  "Applies Gaussian noise to synapse count weights.",
    },
    "neurotransmitter_errors": {
        "display_name": "Neurotransmitter Errors",
        "description":  "Simulates misclassification of neurotransmitter type labels.",
    },
    "neuron_identity_errors": {
        "display_name": "Neuron Identity Errors",
        "description":  "Simulates mis-assignment of neuron class / cell-type identities.",
    },
}


class RootIndexExporter(BaseExporter):
    """Generate results/index.html.

    Args:
        results_root: The ``results/`` directory.
    """

    def __init__(self, results_root: Path) -> None:
        super().__init__(results_root)
        self._root = results_root

    def export(self) -> None:
        """Scan ``results/`` for error model folders and render index.html."""
        self._ensure_dirs(self._root)

        error_models = self._discover_error_models()

        total_datasets  = sum(len(m["datasets"]) for m in error_models)
        total_expts     = sum(
            sum(ds["n_rates"] for ds in m["datasets"])
            for m in error_models
        )

        comparison_dir = self._root / "comparison"
        show_comparison = comparison_dir.exists()

        self._render_template(
            "root_index.html",
            {
                "error_models":      error_models,
                "total_datasets":    total_datasets,
                "total_experiments": total_expts,
                "show_comparison":   show_comparison,
                "root_path":         "",
            },
            self._root / "index.html",
        )
        logger.info("[RootIndexExporter] Rendered results/index.html")

    # ------------------------------------------------------------------ #
    # Discovery                                                            #
    # ------------------------------------------------------------------ #

    def _discover_error_models(self) -> List[Dict[str, Any]]:
        """Walk results/ to discover which error models have been generated."""
        models = []
        for item in sorted(self._root.iterdir()):
            if not item.is_dir():
                continue
            if item.name in ("comparison", ".git", "__pycache__") or item.name.endswith("_percent"):
                continue

            slug = item.name
            meta = _ERROR_MODEL_META.get(slug, {
                "display_name": slug.replace("_", " ").title(),
                "description":  "Biological error model experiment.",
            })

            datasets = []
            for ds_dir in sorted(item.iterdir()):
                if not ds_dir.is_dir():
                    continue
                if ds_dir.name in ("cross_dataset_analysis", "__pycache__"):
                    continue

                # Count error_x/ subdirs
                rate_dirs = [
                    d for d in ds_dir.iterdir()
                    if d.is_dir() and d.name.startswith("error_")
                ]
                # Count trials from summary.csv presence
                n_rates = len(rate_dirs)

                # Best-effort trial count from first rate dir
                n_trials = 0
                if rate_dirs:
                    meta_path = rate_dirs[0] / "data" / "metadata.json"
                    if meta_path.exists():
                        try:
                            import json
                            with open(meta_path, "r", encoding="utf-8") as f:
                                meta_data = json.load(f)
                                n_trials = meta_data.get("n_trials", 1)
                        except Exception:
                            n_trials = 1

                datasets.append({
                    "name":     ds_dir.name,
                    "n_rates":  n_rates,
                    "n_trials": n_trials,
                })

            if datasets:
                models.append({
                    "slug":         slug,
                    "display_name": meta["display_name"],
                    "description":  meta["description"],
                    "datasets":     datasets,
                })

        return models
