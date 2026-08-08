"""
Builds the EM5 (merge errors) notebooks as valid .ipynb JSON.

Mirrors the exact cell structure of the EM4 notebooks
(notebooks/error-4-split-errors.ipynb and
notebooks/test_notebook/error-4-test-split-errors.ipynb) with the EM5
dedicated runner (MergeExperimentRunner) and EM5 metadata keys
(pairs_merged / neurons_absorbed / pairs_rejected).
"""

import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

NOTEBOOK_META = {
    "kernelspec": {
        "display_name": "Python 3",
        "language": "python",
        "name": "python3",
    },
    "language_info": {
        "name": "python",
        "version": "3.10.0",
    },
}


def md(source: str) -> dict:
    return {"cell_type": "markdown", "metadata": {}, "source": source.splitlines(keepends=True)}


def code(source: str) -> dict:
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": source.splitlines(keepends=True),
    }


def build_notebook(cells) -> dict:
    return {
        "cells": cells,
        "metadata": NOTEBOOK_META,
        "nbformat": 4,
        "nbformat_minor": 5,
    }


# ---------------------------------------------------------------------------
# Main notebook — mirrors error-4-split-errors.ipynb
# ---------------------------------------------------------------------------

MAIN_CELLS = []

MAIN_CELLS.append(md(
    """# FlyWire Error Analysis: Merge Errors (EM5) — Segmentation Over-Merging Experiment

**One Kaggle Run = One Dataset + One Error Model + One Analysis Profile**

---

### How to run on Kaggle
1. Attach both datasets to this notebook:
   - `flywire-codebase` (uploaded from `flywire_codebase.zip`)
   - `flywire-all-datasets` (uploaded from `flywire_all_datasets.zip`)
2. In **Cell 3**, set `DATASET_NAME` to whichever connectome you want to run.
3. Click **Run All**.

### Kaggle Dataset Paths (fixed, no changes needed)
- Codebase : `/kaggle/input/datasets/jeet7771/flywire-codebase`
- Data      : `/kaggle/input/datasets/jeet7771/flywire-all-datasets`

### What EM5 simulates
A segmentation *merge error* (under-segmentation): two distinct biological
neurons are reconstructed as one (A + B → M).  Only **neuron identity**
changes — every synapse stays attributed: incident edges re-attach to the
merged vertex, parallel edges collapse with summed `syn_count`, and A↔B
edges (which would become self-loops) are dropped and counted explicitly.

- Candidate pairs must pass Stage 1 hard anatomical constraints (same
  `top_region`, soma-side compatible), then are ranked by Jaccard overlap of
  connectivity profiles (Stage 2 graph-based ranking — not a biological
  probability).
- `error_rate` = fraction of **eligible** neurons participating in a merge;
  `k = round(0.5 × rate × n_eligible)` pairs are merged.
- The baseline `PreparedGraph` is **immutable**; the perturbation exists only
  for the lifetime of each trial via `MergeExperimentRunner`.

Scientific methodology: `docs/error model/em5/method plan.md`
Implementation roadmap : `docs/error model/em5/implementation roadmap.md`
"""
))

MAIN_CELLS.append(code(
    """# Cell 1: Environment Setup & sys.path
# This MUST run before any framework imports.
# ============================================================
import os
import sys
from pathlib import Path

IS_KAGGLE = os.path.exists('/kaggle/input')

# Exact Kaggle dataset mount paths for user jeet7771
KAGGLE_CODEBASE_PATH = Path('/kaggle/input/datasets/jeet7771/flywire-codebase')
KAGGLE_DATA_PATH     = Path('/kaggle/input/datasets/jeet7771/flywire-all-datasets')

if IS_KAGGLE:
    # --- Verify and add codebase to sys.path ---
    if not KAGGLE_CODEBASE_PATH.exists():
        raise FileNotFoundError(
            f'Codebase dataset not found at {KAGGLE_CODEBASE_PATH}\\n'
            'Attach the "flywire-codebase" dataset to this notebook.'
        )
    sys.path.insert(0, str(KAGGLE_CODEBASE_PATH))
    print(f'[OK] Codebase path  : {KAGGLE_CODEBASE_PATH}')

    # --- Verify data dataset ---
    if not KAGGLE_DATA_PATH.exists():
        raise FileNotFoundError(
            f'Data dataset not found at {KAGGLE_DATA_PATH}\\n'
            'Attach the "flywire-all-datasets" dataset to this notebook.'
        )
    print(f'[OK] Data path      : {KAGGLE_DATA_PATH}')
    print(f'[OK] Datasets found : {[d.name for d in KAGGLE_DATA_PATH.iterdir() if d.is_dir()]}')

else:
    # Local: codebase is the current working directory
    REPO_ROOT = Path(os.getcwd())
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    print(f'[OK] Running locally. Repo root: {REPO_ROOT}')

print(f'Environment: {"KAGGLE" if IS_KAGGLE else "LOCAL"}')
"""
))

MAIN_CELLS.append(code(
    """# Cell 2: Framework Imports
import warnings
import pandas as pd

warnings.filterwarnings('ignore')

from core.merge_experiment_runner import MergeExperimentRunner
from core.experiment_runner import ExperimentConfig
from modules.error_models import registry as error_registry
from modules.graph_analyses.analysis_registry import registry as analysis_registry
from modules.statistical_evaluation import StatisticalEvaluator
from core.export_manager import ExportManager

print('All framework imports successful.')
"""
))

MAIN_CELLS.append(code(
    """# ============================================================
# Cell 3: RUNTIME CONFIGURATION  <-- ONLY CELL YOU NEED TO EDIT
# ============================================================

# Which connectome to run.
# Options: "BANC" | "FAFB" | "MANC" | "MAOL" | "MCNS" | "TEST"
DATASET_NAME = "BANC"

# [LOCAL ONLY] Path to your raw dataset folder. Ignored on Kaggle.
LOCAL_DATASET_ROOT = "research_data/raw"

# NOTE: For this model, error_rate = FRACTION OF ELIGIBLE NEURONS that
# participate in a merge.  Eligible = candidate-pair members after Stage 1
# hard anatomical constraints (same top_region, soma-side compatible) and the
# degree quality floor.  k = round(0.5 * error_rate * n_eligible) pairs are
# merged.  E.g. error_rate=0.05 with 10,000 eligible neurons -> 250 merge
# pairs (500 neurons absorbed).

EXPERIMENT = {
    "metadata": {
        "experiment_name": f"MergeErrors_{DATASET_NAME}",
        "author": "FlyWire Researcher",
        "description": (
            "Impact of neuron-level segmentation merge errors on graph "
            "analyses.  Pairs of neurons are merged into one vertex after "
            "Stage 1 anatomical constraints + Stage 2 Jaccard ranking; "
            "incident edges re-attach, parallel edges collapse (summed "
            "syn_count), self-loop edges are dropped and counted."
        ),
    },
    "error": {
        "name": "merge_errors",
        # Fraction of eligible neurons participating in a merge.
        "rates": [
            0.000,    # 0%   — baseline (no merges)
            0.005,    # 0.5%
            0.010,    # 1%
            0.020,    # 2%
            0.030,    # 3%
            0.050,    # 5%
            0.075,    # 7.5%
            0.100,    # 10%
            0.150,    # 15%
            0.200,    # 20%
        ],
        "random_seeds": [1, 2, 3, 4, 5],
        "config": {
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
        },
    },
    "analysis": [
        "basic_structure",       # node_count/edge_count/total_synapses -> node_count DECREASES
        "degree_distribution",   # degree vectors -> SHOULD change (vertices absorbed)
        "pagerank",              # weighted centrality -> SHOULD change; EM5 aligns vectors
        "assortativity",         # topological -> SHOULD change (merged vertices alter mixing)
        "connected_components",  # -> SHOULD change (vertices removed)
        "reciprocity",           # topological -> expected to shift
    ],
    "export": {
        "create_zip": True,
        "save_statistics": True,
    },
}

OUTPUT_ROOT = Path("results") / DATASET_NAME / EXPERIMENT["error"]["name"]

print(f'Dataset Name     : {DATASET_NAME}')
print(f'Error Model      : {EXPERIMENT["error"]["name"]}')
print(f'Error Rates      : {EXPERIMENT["error"]["rates"]}   (fraction of eligible neurons merged)')
print(f'Trials per Rate  : {len(EXPERIMENT["error"]["random_seeds"])}')
print(f'Model Config     : {EXPERIMENT["error"]["config"]}')
print(f'Output Root      : {OUTPUT_ROOT}')
"""
))

MAIN_CELLS.append(code(
    """# Cell 4: Resolve Dataset Root
if IS_KAGGLE:
    DATASET_ROOT = str(KAGGLE_DATA_PATH)
else:
    DATASET_ROOT = '0-demodata' if DATASET_NAME.upper() == 'TEST' else LOCAL_DATASET_ROOT

print(f'DATASET_ROOT = {DATASET_ROOT}')
"""
))

MAIN_CELLS.append(code(
    """# Cell 5: Verify Dataset Structure
from core.dataset_registry import DatasetRegistry, DatasetRegistryError

CONFIGS_ROOT = str(KAGGLE_CODEBASE_PATH / 'configs') if IS_KAGGLE else 'configs'

try:
    reg = DatasetRegistry(configs_root=CONFIGS_ROOT, dataset_root=DATASET_ROOT)
    resolved_dir = reg.resolve_dataset_dir(DATASET_NAME, DATASET_ROOT)
    print(f'[OK] Dataset "{DATASET_NAME}" verified.')
    print(f'     Resolved: {resolved_dir}')
except DatasetRegistryError as e:
    raise FileNotFoundError(
        f'Cannot resolve dataset "{DATASET_NAME}" in "{DATASET_ROOT}".\\n'
        f'Expected a subfolder named {DATASET_NAME}_<version>/ or {DATASET_NAME}/.\\n'
        f'Error: {e}'
    ) from e
"""
))

MAIN_CELLS.append(code(
    """# Cell 6: Verify Registries
err_model = EXPERIMENT['error']['name']
print(f'Registered Error Models : {error_registry.list_names()}')
print(f'Registered Analyses     : {analysis_registry.list_names()}')

assert err_model in error_registry.list_names(), \\
    f'Error model "{err_model}" not registered.'
missing = [a for a in EXPERIMENT['analysis'] if a not in analysis_registry.list_names()]
assert not missing, f'Analyses not registered: {missing}'

print('[OK] All required components registered. Ready to run.')
"""
))

MAIN_CELLS.append(code(
    """# Cell 7: Run Experiments (MergeExperimentRunner — EM5 dedicated runner)
runner = MergeExperimentRunner(analysis_registry, error_registry)
results_per_rate = {}

for err_rate in EXPERIMENT['error']['rates']:
    rate_str = f"{err_rate * 100:g}".replace('.', '_') + "_percent"
    results_per_rate[err_rate] = []

    for trial, seed in enumerate(EXPERIMENT['error']['random_seeds'], 1):
        print(f'\\n{"="*50}')
        print(f'  Dataset    : {DATASET_NAME}')
        print(f'  Error Rate : {err_rate * 100:g}%  (fraction of eligible neurons merged)')
        print(f'  Trial      : {trial} / {len(EXPERIMENT["error"]["random_seeds"])}')
        print(f'  Seed       : {seed}')
        print(f'{"="*50}')

        trial_out = OUTPUT_ROOT / rate_str / f'trial_{trial:03d}'

        config = ExperimentConfig(
            dataset_name=DATASET_NAME,
            dataset_root=str(DATASET_ROOT),
            configs_root=CONFIGS_ROOT,
            error_model_name=err_model,
            error_model_config={
                'error_rate': err_rate,
                **EXPERIMENT['error']['config'],
            },
            analysis_names=EXPERIMENT['analysis'],
            # Baseline pagerank is required for EM5 merge-aware vector alignment.
            # _align_pagerank_vectors() collapses this vector into the merged
            # coordinate space before computing per-trial Pearson/Spearman/Top-K,
            # so the comparison is neuron-ID-aware rather than positional.
            baseline_analysis_names=['pagerank'],
            preprocessing_config={'features': {'degree': True, 'synapse_counts': True}},
            seed=seed,
            output_root=str(trial_out) if EXPERIMENT['export']['save_statistics'] else None,
            create_zip=EXPERIMENT['export']['create_zip'],
            extra={'metadata': EXPERIMENT['metadata']},
        )

        res = runner.run(config)
        results_per_rate[err_rate].append(res)

        if res.succeeded:
            meta = res.error_result.perturbation_metadata if res.error_result else {}
            print(f'  --> Success! ({res.runtime_seconds:.2f}s) '
                  f'merged={meta.get("pairs_merged", 0)} '
                  f'absorbed={meta.get("neurons_absorbed", 0)} '
                  f'rejected={meta.get("pairs_rejected", 0)}')
        else:
            print(f'  --> FAILED!  Errors: {res.errors}')

print('\\nAll trials complete.')
"""
))

MAIN_CELLS.append(code(
    """# Cell 8: Statistical Evaluation
evaluator = StatisticalEvaluator()
aggregated_stats_by_rate = {}

baseline_runs = [r for r in results_per_rate.get(0.00, []) if r.succeeded]
if not baseline_runs:
    raise RuntimeError('No successful baseline (0%) runs. Cannot evaluate.')

for err_rate, run_results in results_per_rate.items():
    successful = [r for r in run_results if r.succeeded]
    if successful:
        eval_result = evaluator.evaluate(baseline_runs, successful)
        aggregated_stats_by_rate[err_rate] = eval_result
        print(f'Evaluated {err_rate*100:g}%  -> {len(successful)} successful trials')
    else:
        print(f'Skipped   {err_rate*100:g}%  -> 0 successful trials')

print('\\nStatistical evaluation complete.')
"""
))

MAIN_CELLS.append(code(
    """# Cell 9: Export Presentation Layer
# Plots -> results/<DATASET>/merge_errors/presentation/plots/
ExportManager().export_presentation(
    results_by_rate=aggregated_stats_by_rate,
    output_root=OUTPUT_ROOT,
    metadata=EXPERIMENT['metadata'],
)
print(f'Presentation exported to : {OUTPUT_ROOT / "presentation"}')
print(f'Plots saved to           : {OUTPUT_ROOT / "presentation" / "plots"}')
"""
))

MAIN_CELLS.append(code(
    """# Cell 10: Quick Summary
print('=' * 50)
print(f'  {DATASET_NAME} - {err_model}')
print('=' * 50)
for err_rate in sorted(aggregated_stats_by_rate.keys()):
    ev = aggregated_stats_by_rate[err_rate]
    print(f'  Merge rate {err_rate*100:g}%')
    for a_name, metrics in ev.metrics.items():
        print(f'    {a_name}: {len(metrics)} metrics')
        for m_name, m_dict in list(metrics.items())[:3]:
            print(f'      {m_name}: mean={m_dict.mean:.4f} d={m_dict.effect_size:.4f}')
total_trials = sum(len(v) for v in results_per_rate.values())
print(f'  Trials: {total_trials} | Rates: {len(aggregated_stats_by_rate)}')
print(f'  Output: {OUTPUT_ROOT}')
print('=' * 50)
"""
))

# ---------------------------------------------------------------------------
# Test notebook — mirrors error-4-test-split-errors.ipynb
# ---------------------------------------------------------------------------

TEST_CELLS = []

TEST_CELLS.append(md(
    """# FlyWire Quick Test: Merge Errors (EM5) — Segmentation Over-Merging

**2 rates × 1 seed = 2 trials — fast validation run.**

For EM5, error_rate = fraction of **eligible** neurons participating in a
merge (`k = round(0.5 × rate × n_eligible)` pairs).  Candidate pairs pass
Stage 1 hard anatomical constraints (same `top_region`, soma-side
compatible), then are ranked by Jaccard overlap of connectivity profiles.
Merging re-attaches incident edges, collapses parallel edges (summed
`syn_count`), and drops A↔B self-loops (counted explicitly).  Synapse counts
are preserved except for the recorded self-loop drops — only neuron identity
changes.
"""
))

TEST_CELLS.append(code(
    """# Cell 1: Environment Setup
import os, sys, warnings
from pathlib import Path
warnings.filterwarnings('ignore')

IS_KAGGLE = os.path.exists('/kaggle/input')
KAGGLE_CODEBASE_PATH = Path('/kaggle/input/datasets/jeet7771/flywire-codebase')
KAGGLE_DATA_PATH     = Path('/kaggle/input/datasets/jeet7771/flywire-all-datasets')

if IS_KAGGLE:
    sys.path.insert(0, str(KAGGLE_CODEBASE_PATH))
    print(f'[OK] Codebase: {KAGGLE_CODEBASE_PATH}')
else:
    REPO = Path(os.getcwd())
    if str(REPO) not in sys.path:
        sys.path.insert(0, str(REPO))
    print(f'[OK] Local: {REPO}')
"""
))

TEST_CELLS.append(code(
    """# Cell 2: Imports
from core.merge_experiment_runner import MergeExperimentRunner
from core.experiment_runner import ExperimentConfig
from modules.error_models import registry as error_registry
from modules.graph_analyses.analysis_registry import registry as analysis_registry
from modules.statistical_evaluation import StatisticalEvaluator
from core.export_manager import ExportManager
print('Imports OK')
"""
))

TEST_CELLS.append(code(
    """# ============================================================
# Cell 3: MINIMAL TEST CONFIG  (2 rates, 1 seed)
# ============================================================
DATASET_NAME = "BANC"
LOCAL_DATASET_ROOT = "research_data/raw"

EXPERIMENT = {
    "metadata": {
        "experiment_name": f"BANC_MergeErrors_{DATASET_NAME}",
        "author": "FlyWire Researcher",
        "description": "QUICK TEST — neuron-level merge errors on BANC (2 rates, 1 seed).",
    },
    "error": {
        "name": "merge_errors",
        "rates": [
            0.00,    # baseline (required)
            0.05,    # 5% — one perturbed rate
        ],
        "random_seeds": [1],
        "config": {
            "region_constraint": True,
            "soma_side_constraint": True,
            "degree_threshold": 10,      # quality floor (not eligibility)
            "min_shared_partners": 3,    # Stage 2 calibration
            "jaccard_min": 0.001,        # ranking floor
            "top_k_per_neuron": 50,      # implementation bound
            "max_retries": 20,           # bounded rejection re-sampling
        },
    },
    "analysis": [
        "basic_structure",
        "degree_distribution",
        "pagerank",
        "assortativity",
        "connected_components",
        "reciprocity",
    ],
    "export": {
        "create_zip": True,
        "save_statistics": True,
    },
}

OUTPUT_ROOT = Path("results") / DATASET_NAME / EXPERIMENT["error"]["name"]
print(f'Config: {DATASET_NAME} | rates={len(EXPERIMENT["error"]["rates"])} | seeds={len(EXPERIMENT["error"]["random_seeds"])}')
"""
))

TEST_CELLS.append(code(
    """# Cell 4: Dataset Root
if IS_KAGGLE:
    DATASET_ROOT = str(KAGGLE_DATA_PATH)
else:
    DATASET_ROOT = '0-demodata' if DATASET_NAME.upper() == 'TEST' else LOCAL_DATASET_ROOT
CONFIGS_ROOT = str(KAGGLE_CODEBASE_PATH / 'configs') if IS_KAGGLE else 'configs'
print(f'DATASET_ROOT = {DATASET_ROOT}')
"""
))

TEST_CELLS.append(code(
    """# Cell 5: Verify Dataset
from core.dataset_registry import DatasetRegistry
reg = DatasetRegistry(configs_root=CONFIGS_ROOT, dataset_root=DATASET_ROOT)
_ = reg.resolve_dataset_dir(DATASET_NAME, DATASET_ROOT)
print(f'[OK] Dataset "{DATASET_NAME}" resolved.')
"""
))

TEST_CELLS.append(code(
    """# Cell 6: Verify Registries
err_model = EXPERIMENT['error']['name']
print(f'Models: {error_registry.list_names()}')
print(f'Analyses: {analysis_registry.list_names()}')
assert err_model in error_registry.list_names(), f'{err_model} not registered!'
print('[OK] Ready.')
"""
))

TEST_CELLS.append(code(
    """# Cell 7: Run Experiments (2 rates x 1 seed = 2 trials)
import time
t_start = time.perf_counter()

runner = MergeExperimentRunner(analysis_registry, error_registry)
results_per_rate = {}

for err_rate in EXPERIMENT['error']['rates']:
    rate_str = f"{int(err_rate*100)}_percent"
    results_per_rate[err_rate] = []
    for trial, seed in enumerate(EXPERIMENT['error']['random_seeds'], 1):
        print(f'[{rate_str} | trial {trial}] seed={seed} ...', end=' ')
        trial_out = OUTPUT_ROOT / rate_str / f'trial_{trial:03d}'
        config = ExperimentConfig(
            dataset_name=DATASET_NAME,
            dataset_root=str(DATASET_ROOT),
            configs_root=CONFIGS_ROOT,
            error_model_name=err_model,
            error_model_config={'error_rate': err_rate, **EXPERIMENT['error']['config']},
            analysis_names=EXPERIMENT['analysis'],
            # Baseline pagerank required for EM5 merge-aware vector alignment.
            baseline_analysis_names=['pagerank'],
            preprocessing_config={'features': {'degree': True, 'synapse_counts': True}},
            seed=seed,
            output_root=str(trial_out) if EXPERIMENT['export']['save_statistics'] else None,
            create_zip=EXPERIMENT['export']['create_zip'],
            extra={'metadata': EXPERIMENT['metadata']},
        )
        res = runner.run(config)
        results_per_rate[err_rate].append(res)
        status = 'OK' if res.succeeded else 'FAIL'
        meta = res.error_result.perturbation_metadata if res.error_result else {}
        print(f'{status} ({res.runtime_seconds:.2f}s, merged={meta.get("pairs_merged", 0)}, '
              f'absorbed={meta.get("neurons_absorbed", 0)}, '
              f'rejected={meta.get("pairs_rejected", 0)})')

print(f'\\nAll trials done in {time.perf_counter()-t_start:.1f}s')
"""
))

TEST_CELLS.append(code(
    """# Cell 8: Statistical Evaluation
evaluator = StatisticalEvaluator()
aggregated_stats_by_rate = {}
baseline_runs = [r for r in results_per_rate.get(0.00, []) if r.succeeded]
print(f'Baseline runs: {len(baseline_runs)}')

for err_rate, run_results in results_per_rate.items():
    successful = [r for r in run_results if r.succeeded]
    if successful and err_rate > 0:
        eval_result = evaluator.evaluate(baseline_runs, successful)
        aggregated_stats_by_rate[err_rate] = eval_result
        print(f'  {err_rate*100:g}%: {len(successful)} trials evaluated')

print('Evaluation complete.')
"""
))

TEST_CELLS.append(code(
    """# Cell 9: Export Presentation
ExportManager().export_presentation(
    results_by_rate=aggregated_stats_by_rate,
    output_root=OUTPUT_ROOT,
    metadata=EXPERIMENT['metadata'],
)
print(f'Presentation -> {OUTPUT_ROOT / "presentation"}')
"""
))

TEST_CELLS.append(code(
    """# Cell 10: Quick Summary
print('=' * 50)
print('  BANC QUICK TEST - MERGE ERRORS (EM5)')
print('=' * 50)
for err_rate in sorted(aggregated_stats_by_rate.keys()):
    ev = aggregated_stats_by_rate[err_rate]
    print(f'  Merge rate {err_rate*100:g}%')
    for a_name, metrics in ev.metrics.items():
        print(f'    {a_name}: {len(metrics)} metrics')
        for m_name, m_dict in list(metrics.items())[:3]:
            print(f'      {m_name}: mean={m_dict.mean:.4f} d={m_dict.effect_size:.4f}')
total_trials = sum(len(v) for v in results_per_rate.values())
print(f'  Trials: {total_trials} | Rates: {len(aggregated_stats_by_rate)}')
print(f'  Output: {OUTPUT_ROOT}')
print('=' * 50)
"""
))


def main() -> None:
    main_path = REPO / "notebooks" / "error-5-merge-errors.ipynb"
    test_path = REPO / "notebooks" / "test_notebook" / "error-5-test-merge-errors.ipynb"

    main_path.write_text(
        json.dumps(build_notebook(MAIN_CELLS), indent=1), encoding="utf-8"
    )
    test_path.write_text(
        json.dumps(build_notebook(TEST_CELLS), indent=1), encoding="utf-8"
    )
    print(f"Wrote {main_path}")
    print(f"Wrote {test_path}")


if __name__ == "__main__":
    main()
