# Connectome Error Analysis Framework

A modular Python research framework for quantifying and simulating annotation errors in the **FlyWire** *Drosophila* connectome. The framework applies stochastic error models to connectome graphs and measures downstream impact on graph-theoretic and biological metrics.

---

## Overview

Connectome reconstruction is inherently noisy. This project asks: **how much do annotation errors actually matter?** We simulate specific error types (e.g., missed synapses) on real connectome data, run graph analyses on the perturbed graphs, and statistically evaluate the metric shifts.

```
Raw Connectome Data
      │
      ▼
┌─────────────────────┐
│  Preprocessing      │  Normalise, validate, build feature vectors
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│  Error Model        │  Stochastic perturbation (missed synapses, …)
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│  Graph Analyses     │  Degree, PageRank, centrality, community …
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│  Statistical Eval   │  Compare baseline vs. perturbed distributions
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│  Export / Report    │  JSON + ZIP artefact bundle
└─────────────────────┘
```

---

## Repository Layout

```
v1/
├── core/                        # Infrastructure layer
│   ├── data_loader.py           # Polars-based CSV loader for connectome datasets
│   ├── dataset_registry.py      # YAML-driven dataset discovery & path resolution
│   ├── config_manager.py        # Frozen, immutable config objects
│   ├── graph_builder.py         # igraph graph construction from connections table
│   ├── experiment_runner.py     # Orchestrates the full experiment pipeline
│   ├── statistics_engine.py     # Metric aggregation & summary statistics
│   ├── metadata_manager.py      # Experiment provenance & metadata recording
│   ├── export_manager.py        # Artefact serialisation & ZIP packaging
│   ├── checkpoint_manager.py    # Mid-run checkpointing for long experiments
│   └── runtime_monitor.py       # CPU / memory usage tracking
│
├── modules/
│   ├── error_models/            # Pluggable error simulation models
│   │   ├── base_error_model.py  # Abstract base; handles calibration & RNG seeding
│   │   ├── missed_synapses.py   # Experiment 1: stochastic edge-removal model
│   │   ├── calibration.py       # Calibrates removal probabilities to target rate
│   │   ├── biology.py           # Biological feature weighting utilities
│   │   ├── vulnerability.py     # Synapse vulnerability scoring
│   │   └── error_registry.py    # Global registry for error-model plugins
│   │
│   ├── graph_analyses/          # Pluggable graph analysis modules
│   │   ├── base_analysis.py     # Abstract analysis interface
│   │   ├── structural.py        # Basic structure (nodes, edges, density)
│   │   ├── centrality.py        # Betweenness / closeness centrality
│   │   ├── network_statistics.py # Reciprocity, clustering, path lengths
│   │   ├── biological.py        # Biologically-informed graph metrics
│   │   └── analysis_registry.py # Global registry for analysis plugins
│   │
│   ├── preprocessing/           # Data wrangling & feature engineering
│   │   ├── pipeline.py          # End-to-end preprocessing orchestrator
│   │   ├── prepared_graph.py    # Dataclass holding graph + feature tables
│   │   ├── lookup.py            # Fast neuron-attribute lookup tables
│   │   ├── validator.py         # Schema & biological-plausibility checks
│   │   └── metadata.py          # Dataset-level metadata extraction
│   │
│   └── statistical_evaluation/  # Baseline-vs-perturbed comparison engine
│
├── configs/                     # YAML configuration files
│   ├── defaults.yaml            # Global defaults (tolerances, random seeds …)
│   ├── datasets/                # Per-dataset schema & path specs
│   ├── error_models/            # Per-model hyper-parameter defaults
│   ├── analyses/                # Per-analysis output specifications
│   └── experiments/             # Named experiment configurations
│
├── notebooks/
│   └── experiments_missed_synapses.ipynb  # Kaggle-ready experiment notebook
│
├── tests/                       # pytest test suite
├── 0-demodata/                  # Synthetic TEST dataset for local smoke tests
├── run_demo.py                  # Local end-to-end demo script
└── requirements.txt
```

---

## Datasets

The framework supports three FlyWire connectome releases:

| Name     | Description                                  |
|----------|----------------------------------------------|
| `FAFB`   | Full Adult Female Brain (630k neurons)        |
| `MALE`   | Full Adult Male Brain                         |
| `TEST`   | Small synthetic dataset for local dev/testing |

Dataset paths are resolved via `configs/datasets/*.yaml`. Place raw data under a root directory and point `dataset_root` to it.

---

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Run the local demo

Runs a baseline (0 % error) and a perturbed (10 % error) experiment on the small
synthetic TEST dataset, then exports results to `results/`.

```bash
python run_demo.py
```

### 3. Run on Kaggle (full connectomes)

1. Upload `flywire_codebase.zip` → Kaggle dataset `flywire-codebase`  
2. Upload `flywire_all_datasets.zip` → Kaggle dataset `flywire-all-datasets`  
3. Open `notebooks/experiments_missed_synapses.ipynb` in Kaggle  
4. Set `DATASET_NAME` in Cell 3 (e.g. `"FAFB"`, `"MALE"`)  
5. Click **Run All**

---

## Experiment 1 — Missed Synapses

The first experiment models **missed synapses**: edges (synaptic connections) that
exist in the true connectome but were not detected by the annotation pipeline.

**Error model**: For each edge the calibrated removal probability is computed from
biological features (synapse count, pre/post-synaptic neuron degree). A binomial
trial is performed independently for every synapse on the edge; the edge is removed
if all its synapses are lost.

**Key analyses run**:
- Basic structure (node/edge counts, density)
- Degree distribution
- PageRank
- Centrality (betweenness, closeness)
- Connected components
- Reciprocity

---

## Running Tests

```bash
pytest tests/ -v
```

---

## Architecture Notes

- **Backend**: [Polars](https://pola.rs/) for all DataFrame operations (columnar, zero-copy, fast).
- **Graph library**: [igraph](https://igraph.org/python/) for graph construction and analysis.
- **Plugin system**: Error models and analyses are registered via a central `ErrorRegistry` / `AnalysisRegistry`. Adding a new model only requires subclassing `BaseErrorModel` and registering it.
- **Reproducibility**: All stochastic operations use a seeded `numpy.random.Generator`; seed is recorded in experiment metadata.
- **Biological ID integrity**: `root_id`, `pre_root_id`, `post_root_id` are always `Int64` and are never remapped or downcast.

---

## License

Research code. Contact the authors before reuse.
