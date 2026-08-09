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
│   ├── runtime_monitor.py       # CPU / memory usage tracking
│   ├── split_experiment_runner.py  # Runner for topology-changing models (split/merge)
│   └── merge_experiment_runner.py  # Merge-model pipeline (candidates, rewiring)
│
├── modules/
│   ├── error_models/            # Pluggable error simulation models
│   │   ├── common/              # BaseErrorModel, calibration, biology, registry
│   │   ├── missed_synapses/     # EM1: stochastic synapse / edge removal
│   │   ├── false_synapses/      # EM2: spurious-edge (false positive) injection
│   │   ├── synapse_count/       # EM3: synapse-count measurement noise
│   │   ├── split_errors/        # EM4: over-segmentation (one neuron -> two)
│   │   └── merge_errors/        # EM5: under-segmentation (two neurons -> one)
│   │
│   ├── graph_analyses/          # Pluggable graph analysis modules
│   │   ├── structural.py        # Basic structure (nodes, edges, density, weights)
│   │   ├── degree_distribution  # In/out/total degree stats + KS/Wasserstein
│   │   ├── pagerank.py          # PageRank score correlations & top-k overlap
│   │   ├── assortativity.py     # Degree assortativity
│   │   ├── connected_components.py  # WCC / SCC statistics
│   │   ├── reciprocity.py       # Edge reciprocity
│   │   ├── centrality.py        # Betweenness / closeness centrality
│   │   ├── biological.py        # Biologically-informed graph metrics
│   │   └── analysis_registry.py # Global registry for analysis plugins
│   │
│   ├── preprocessing/           # Data wrangling & feature engineering
│   │   ├── common/              # pipeline, prepared_graph, lookup, validator
│   │   ├── missed_synapses/     # vulnerability scoring, biological features
│   │   └── false_synapses/      # candidate generation, similarity ranking
│   │
│   ├── statistical_evaluation/  # Baseline-vs-perturbed comparison engine
│   │   ├── evaluator.py         # Metric-level means, CIs, effect sizes
│   │   └── vector_comparison.py # Distribution/vector comparisons (KS, Wasserstein)
│   │
│   └── reporting/               # Data loading, trend & sensitivity analysis
│
├── configs/                     # YAML configuration files
│   ├── defaults.yaml            # Global defaults (tolerances, random seeds …)
│   ├── datasets/                # Per-dataset schema & path specs
│   ├── error_models/            # Per-model hyper-parameter defaults
│   ├── analyses/                # Per-analysis output specifications
│   ├── experiments/             # Named experiment configurations
│   └── schemas/                 # Dataset / experiment validation schemas
│
├── presentation/                # Reporting pipeline (HTML reports, dashboards)
├── notebooks/
│   ├── error-1-...missed-synapses.ipynb   # EM1 Kaggle notebook
│   ├── error-2-false-synapse.ipynb        # EM2 Kaggle notebook
│   ├── error-3-synapse-count.ipynb        # EM3 Kaggle notebook
│   ├── error-4-split-errors.ipynb         # EM4 Kaggle notebook
│   └── error-5-merge-errors.ipynb         # EM5 Kaggle notebook
│
├── docs/                        # Methodology, architecture, dataset analysis
│   └── method/                  # Scientific design approach + mermaid diagrams
├── tests/                       # pytest test suite
└── requirements.txt
```

---

## Datasets

The framework supports five FlyWire connectome releases, configured in `configs/datasets/*.yaml`:

| Name   | Description                                   |
|--------|-----------------------------------------------|
| `BANC` | Brain And Nerve Cord connectome                |
| `FAFB` | Full Adult Female Brain (3-file join schema)   |
| `MANC` | Male Adult Nerve Cord (very dense graph)       |
| `MAOL` | Male Adult Optic Lobe                          |
| `MCNS` | Multi-cell type Nervous System (pre-release)   |
| `TEST` | Small synthetic dataset (local smoke tests)    |

Raw data lives under `research_data/` (git-ignored); dataset paths are resolved via `configs/datasets/*.yaml`. The FAFB schema additionally requires `classification.csv.gz` and `consolidated_cell_types.csv.gz` alongside `neurons.csv.gz` and `connections_princeton.csv.gz`.

---

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Run the test suite

```bash
pytest tests/ -q
```

### 3. Run an experiment on Kaggle (full connectomes)

1. Upload `flywire_codebase.zip` -> Kaggle dataset `flywire-codebase`
2. Upload the raw datasets -> Kaggle dataset `flywire-all-datasets`
3. Open one of the error-model notebooks in `notebooks/` (e.g. `error-5-merge-errors.ipynb`)
4. Set `DATASET_NAME` in the setup cell (e.g. `"BANC"`, `"FAFB"`, `"MANC"`)
5. Click **Run All**

Each notebook runs the full pipeline: preprocessing -> error perturbation -> graph analyses -> statistical evaluation -> HTML report export.

---

## Error Models

The framework implements five error models, each simulating a distinct reconstruction error type:

| Model            | Notebook              | Simulated error                                  | Graph-level effect                       |
|------------------|-----------------------|--------------------------------------------------|------------------------------------------|
| Missed synapses  | `error-1-...ipynb`    | True synapses missed by detection                | Synapse/edge loss (edge removed only when all synapses lost) |
| False synapses   | `error-2-...ipynb`    | Spurious (false-positive) synapse detection      | New edges injected (candidate-ranked by similarity) |
| Synapse count    | `error-3-...ipynb`    | Measurement uncertainty in synapse counts        | Edge weights perturbed, topology unchanged |
| Split errors     | `error-4-...ipynb`    | Over-segmentation (one neuron -> two)            | Vertex count increases, edges conserved    |
| Merge errors     | `error-5-...ipynb`    | Under-segmentation (two neurons -> one)          | Vertex count decreases, edges rewired      |

All models share the same scientific scaffold: a biologically motivated perturbation, probability calibration to hit the target error rate, seeded stochastic sampling, and multiple trials across an error-rate sweep. See `docs/method/` for the full scientific methodology with diagrams.

**Key analyses run per experiment**:
- Basic structure (node/edge counts, density, weight statistics)
- Degree distribution (in/out/total, KS & Wasserstein comparisons)
- PageRank (Pearson / Spearman correlation, top-k overlap)
- Assortativity, connected components (WCC/SCC), reciprocity
- Statistical evaluation: means, 95% CIs, Cohen's d, preservation %

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
