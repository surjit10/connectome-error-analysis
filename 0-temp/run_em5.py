"""
EM5 — Merge Errors: CLI runner script (mirrors 0-temp/run_em1_banc.py role).

Runs the merge-errors error model across a set of error rates on a dataset
using the EM5 dedicated runner (MergeExperimentRunner), aggregates the
results with StatisticsEngine, and exports a result package.

Usage:
    .venv/bin/python 0-temp/run_em5.py [dataset_name] [error_rate_0 error_rate_1 ...]

Defaults:
    dataset : BANC (from research_data/raw)
    rates   : 0.00 0.01 0.05 0.10
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.export_manager import ExportManager
from core.experiment_runner import ExperimentConfig
from core.merge_experiment_runner import MergeExperimentRunner
from core.metadata_manager import MetadataManager
from core.statistics_engine import StatisticsEngine
from modules.error_models import registry as error_registry
from modules.graph_analyses.analysis_registry import registry as analysis_registry

DATASET_NAME = sys.argv[1] if len(sys.argv) > 1 else "BANC"
DATASET_ROOT = "research_data/raw"
CONFIGS_ROOT = "configs"

if len(sys.argv) > 2:
    RATES = [float(r) for r in sys.argv[2:]]
else:
    RATES = [0.00, 0.01, 0.05, 0.10]

SEEDS = [1, 2, 3]

ERROR_MODEL_CONFIG = {
    # Stage 1 hard anatomical constraints (same keys EM2 consumes).
    "region_constraint": True,
    "soma_side_constraint": True,
    # Quality floor ONLY (not scientific eligibility).
    "degree_threshold": 10,
    # Stage 2 graph-based ranking calibration values.
    "min_shared_partners": 3,
    "jaccard_min": 0.001,
    # Implementation bounds.
    "top_k_per_neuron": 50,
    "max_retries": 20,
}

ANALYSES = [
    "basic_structure",
    "degree_distribution",
    "pagerank",
    "assortativity",
    "connected_components",
    "reciprocity",
]

OUTPUT_ROOT = Path("results") / DATASET_NAME / "merge_errors"


def main() -> None:
    print(f"[run_em5] Dataset={DATASET_NAME} rates={RATES} seeds={SEEDS}")

    runner = MergeExperimentRunner(analysis_registry, error_registry)
    results = []

    for rate in RATES:
        rate_str = f"{int(round(rate * 100))}_percent"
        for trial, seed in enumerate(SEEDS, 1):
            trial_out = OUTPUT_ROOT / rate_str / f"trial_{trial:03d}"
            config = ExperimentConfig(
                dataset_name=DATASET_NAME,
                dataset_root=DATASET_ROOT,
                configs_root=CONFIGS_ROOT,
                error_model_name="merge_errors",
                error_model_config={"error_rate": rate, **ERROR_MODEL_CONFIG},
                analysis_names=ANALYSES,
                # Baseline pagerank required for EM5 merge-aware alignment.
                baseline_analysis_names=["pagerank"],
                preprocessing_config={
                    "features": {"degree": True, "synapse_counts": True}
                },
                seed=seed,
                output_root=str(trial_out),
                create_zip=False,
                extra={
                    "metadata": {
                        "experiment_name": f"MergeErrors_{DATASET_NAME}",
                        "author": "FlyWire Researcher",
                        "description": (
                            "CLI run of the EM5 merge-errors model "
                            "(0-temp/run_em5.py)."
                        ),
                    }
                },
            )
            res = runner.run(config)
            results.append(res)
            meta = res.error_result.perturbation_metadata if res.error_result else {}
            print(
                f"  rate={rate:5.2f} seed={seed}: "
                f"{'OK' if res.succeeded else 'FAIL'} "
                f"merged={meta.get('pairs_merged', 0)} "
                f"absorbed={meta.get('neurons_absorbed', 0)} "
                f"rejected={meta.get('pairs_rejected', 0)} "
                f"({res.runtime_seconds:.2f}s)"
            )

    stats = StatisticsEngine().aggregate(results)
    print(f"[run_em5] Aggregated: {stats.n_succeeded}/{len(results)} succeeded.")

    metadata = MetadataManager().collect(results[0])
    package = ExportManager().export(
        result=results[0],
        metadata=metadata,
        stats=stats,
        output_root=OUTPUT_ROOT,
        create_zip=False,
    )
    print(f"[run_em5] Exported to {package.output_dir}")


if __name__ == "__main__":
    main()
