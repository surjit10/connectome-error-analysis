# FlyWire Error Analysis Research Framework: Simplified Architecture

This document specifies the architectural design for a 2-month computational neuroscience research project investigating reconstruction errors in 5 FlyWire connectomes. 

The architecture is deliberately simplified. It avoids enterprise-scale overengineering while preserving configuration-driven reproducibility, Kaggle compatibility, and dataset-level execution. The principle guiding this framework is: **Build the simplest architecture that fully supports the research without sacrificing GitHub cleanliness or reproducibility.**

## 1. Repository Tree

```text
flywire-error-analysis/
├── .github/                        # CI/CD workflows, issue templates
├── configs/                        # Configuration hierarchy (YAML)
│   ├── datasets/                   # (5 configs for the connectomes)
│   ├── error_models/               # (6 configs for the models)
│   ├── analyses/                   # Analysis settings
│   │   ├── structural.yaml
│   │   ├── centrality.yaml
│   │   ├── community.yaml
│   │   ├── biological.yaml
│   │   ├── matching.yaml
│   │   └── conserved_circuits.yaml
│   ├── experiments/                # Concrete experiment definitions (30 total)
│   │   ├── false_negatives/
│   │   │   ├── structural/
│   │   │   ├── centrality/
│   │   │   ├── community/
│   │   │   ├── biological/
│   │   │   ├── matching/
│   │   │   └── conserved_circuits/
│   │   ├── false_positives/
│   │   │   ├── structural/
│   │   │   ├── centrality/
│   │   │   ├── community/
│   │   │   ├── biological/
│   │   │   ├── matching/
│   │   │   └── conserved_circuits/
│   │   ├── merge_errors/
│   │   │   ├── structural/
│   │   │   ├── centrality/
│   │   │   ├── community/
│   │   │   ├── biological/
│   │   │   ├── matching/
│   │   │   └── conserved_circuits/
│   │   ├── split_errors/
│   │   │   ├── structural/
│   │   │   ├── centrality/
│   │   │   ├── community/
│   │   │   ├── biological/
│   │   │   ├── matching/
│   │   │   └── conserved_circuits/
│   │   ├── localized_errors/
│   │   │   ├── structural/
│   │   │   ├── centrality/
│   │   │   ├── community/
│   │   │   ├── biological/
│   │   │   ├── matching/
│   │   │   └── conserved_circuits/
│   │   └── weight_noise/
│   │       ├── structural/
│   │       ├── centrality/
│   │       ├── community/
│   │       ├── biological/
│   │       ├── matching/
│   │       └── conserved_circuits/
│   ├── schemas/                    # YAML validation schemas
│   │   ├── dataset_schema.yaml
│   │   ├── error_model_schema.yaml
│   │   └── experiment_schema.yaml
│   └── defaults.yaml               # Global configuration defaults
├── modules/                        # Pure scientific logic (reusable)
│   ├── preprocessing/              # Graph cleaning and normalization
│   ├── error_models/               # Perturbation logic
│   ├── graph_analyses/             # Graph algorithms
│   └── downstream_tasks/           # Downstream biology simulations
├── core/                           # Reusable core execution and management framework (Flat)
│   ├── __init__.py
│   ├── experiment_runner.py        # Central Orchestrator
│   ├── config_manager.py           # Configuration loading
│   ├── runtime_monitor.py          # Kaggle-aware timeout protection
│   ├── checkpoint_manager.py       # Recovery from Kaggle timeouts
│   ├── statistics_engine.py        # Trial/dataset summary aggregation
│   ├── export_manager.py           # Kaggle download package builder
│   ├── metadata_manager.py         # Standardized metadata tracking
│   └── data_loader.py              # Connectome ingestion
├── notebooks/                      # High-level control and cross-experiment visualization
│   ├── 01_run_experiment.ipynb     # Triggers a Kaggle run
│   ├── 02_compare_datasets.ipynb   # Combines summary stats across datasets
│   └── 03_generate_paper.ipynb     # Plots final multi-dataset figures
├── docs/                           # Project documentation
│   ├── architecture/               # Architecture documents and reports
│   │   ├── flywire_architecture.md
│   │   ├── architecture_compliance_audit.md
│   │   └── repository_migration_report.md
│   ├── notes/                      # Chronological research notes
│   │   ├── Week01.md
│   │   ├── Week02.md
│   │   └── Week03.md
│   ├── Methodology.md              # Scientific approach
│   ├── Execution_Guide.md          # How to run the framework
│   └── experiment_tracker.csv      # Lightweight manual experiment tracking
├── results/                        # Tracked by Git (Small Summaries Only)
│   ├── summaries/                  # High-level dataset summary CSVs and metrics
│   ├── cross_dataset/              # Cross-dataset comparative results
│   └── paper/                      # Final paper-ready SVG/PDF figures and tables
├── research_data/                  # Untracked by Git (Excluded via .gitignore)
│   ├── raw/                        # Original connectomes
│   ├── cache/                      # Preprocessed graphs and intermediate artifacts
│   ├── checkpoints/                # Kaggle timeout recovery states
│   ├── logs/                       # Runtime logs
│   └── experiments/                # Downloaded Experiment Packages (e.g., MissedSynapses_MANC)
├── tests/                          # Unit tests
├── .gitignore                      # Strict untracked file rules (Excludes research_data/)
├── requirements.txt                # Dependency specifications
└── README.md                       
```

## 2. Folder Responsibilities

- **`configs/`**: The declarative brain. Running a new experiment requires only modifying or creating a YAML file here (falling back on `defaults.yaml`).
- **`configs/analyses/`**: Stores reusable analysis profiles. These profiles define which analyses are executed during a Kaggle run. Each YAML defines the analysis profile name, enabled analyses, output configuration, and optional analysis parameters. The execution engine reads these profiles at runtime.
- **`configs/experiments/`**: Stores concrete experiment configurations organized first by Error Model and then by Analysis Profile. Each experiment configuration represents one scientific question executed on one dataset.
- **`configs/schemas/`**: Used by the configuration loader to validate YAML configuration files against schemas before execution.
- **`core/`**: The flat, functional engine. Handles Kaggle limits, data loading, checkpointing, and packaging without deep directory hierarchies.
- **`modules/`**: Reusable scientific logic. Prevents duplicate code when applying the same error model across multiple datasets.
- **`docs/`**: Simple documentation, chronological notes (`docs/notes/`), and a manual `experiment_tracker.csv` to track the 30 major experiments, eliminating the need for a complex database.
- **`results/`**: GitHub-tracked folders for publication-quality output. Holds the small, distilled scientific findings (CSVs, figures).
- **`research_data/`**: The massive, Git-ignored folder living inside the repo. It securely holds all raw datasets, checkpoints, and complete downloadable Kaggle packages without bloating GitHub.

## 3. Dataset-Level Kaggle Workflow

To mitigate Kaggle runtime limits and memory exhaustion:

**One Kaggle Run = One Dataset + One Error Model + One Analysis Profile**

This change improves runtime reliability, modularity, debugging, and reproducibility.

### Scientific Workflow

Research Question
↓
Dataset
↓
Error Model
↓
Analysis Profile
↓
Error Levels
↓
Trials
↓
Statistical Aggregation
↓
Results Package
↓
Cross-Dataset Comparison
↓
Paper Figures and Tables

Each execution produces one self-contained downloadable package. This keeps execution times predictable and downloads manageable.

## 4. The Experiment Runner & Execution Workflow

The **Experiment Runner** (`core/experiment_runner.py`) acts as a simple central orchestrator. It executes the entire pipeline sequentially.

### Execution Workflow

The Experiment Configuration determines the dataset, error model, and analysis profile.
The Analysis Profile determines which graph analyses are executed.

1. **Load Configuration**: Merge defaults, dataset, error, and experiment configs.
2. **Load Dataset**: Pull the connectome into memory.
3. **Load Analysis Profile**: Read the specified scientific analyses to be executed.
4. **Perturb Graph**: Deep copy the graph and apply the perturbation.
5. **Execute Selected Analyses**: Run only the analyses defined in the analysis profile.
6. **Aggregate Results**: Auto-generate dataset summaries via `statistics_engine.py`.
7. **Export Experiment Package**: Call `export_manager.py` to compress everything into a downloadable zip package.

## 5. Export and Local Integration

### Experiment Packages and Versioning
Every Kaggle run generates a complete archive (e.g., `MissedSynapses_MANC.zip`). 
Version management is handled simply via explicit folder naming (e.g., `MissedSynapses_MANC_Rerun/`). The package relies on `metadata.json`, `config_snapshot.yaml`, and a basic runtime report for reproducibility.

**Experiment Package README Requirement**:
Every exported experiment package will contain an automatically generated `README.md` for human readability, summarizing:
- Experiment name
- Dataset
- Error model
- Error levels
- Number of trials
- Runtime
- Generated outputs
- Important observations
- Folder structure

### Download Workflow
The researcher downloads the ZIP and extracts it into `research_data/experiments/`.

To publish a result to GitHub, the researcher explicitly reviews the dataset summaries contained in the package and moves them to `results/summaries/`. Later, the paper notebooks combine these into `results/paper/` figures.

## 6. Git Strategy

The `.gitignore` strictly separates code from data. 

**What is Committed:**
- Source Code (`core/`, `modules/`, `notebooks/`)
- Configs (`configs/`)
- Documentation (`docs/`)
- Aggregated Results (`results/`)

**What is Ignored:**
- **The entire `research_data/` directory.**
- Any generated `.graphml`, `.parquet`, `.zip`, `.checkpoint`, or `.log` file.

This ensures that the repository remains lightweight and clean over the entire 2-month span of the project.

## 7. Analysis Profiles

### Purpose
Analysis Profiles are reusable experiment configurations. Each profile specifies:
- which graph analyses are executed
- output configuration
- optional analysis-specific parameters

### Why Analysis Profiles?
Different graph analyses have different computational costs. Running all analyses together increases Kaggle runtime, increases failure risk, and makes reruns expensive.

Analysis Profiles allow:
- one notebook = one scientific question
- reusable perturbation pipeline
- reusable execution engine
- easier debugging
- direct mapping to paper sections

### Relationship to Error Models and Kaggle
By splitting analyses, Kaggle executions are shorter and less prone to timeouts. Analysis Profiles operate downstream of Error Models.

### Experiment Configuration
Every experiment configuration now references:
- Dataset
- Error Model
- Analysis Profile
- Error Levels
- Number of Trials

instead of executing every analysis. 
The new experiment configuration concept is:
Experiment ↓ Dataset ↓ Error Model ↓ Analysis Profile ↓ Error Levels ↓ Trials

### Examples
- **Structural Profile**: Runs Degree, Density, Components, Reciprocity, Clustering.
- **Centrality Profile**: Runs PageRank, Betweenness, Eigenvector.
- **Community Profile**: Runs Community Detection, Modularity, NMI, ARI.
- **Matching Profile**: Runs Neuron Matching.
- **Conserved Circuit Profile**: Runs Conserved Circuit Detection.

## 8. Mapping Experiments to Paper Structure

Every Analysis Profile corresponds to one major scientific result and directly to one scientific section of the paper. This makes experiments easier to reproduce and easier to write about.

- False Negatives ↓ Structural Profile ↓ Paper Section "Structural Robustness"
- False Negatives ↓ Centrality Profile ↓ Paper Section "Centrality Robustness"
- False Negatives ↓ Community Profile ↓ Paper Section "Community Robustness"
- False Negatives ↓ Matching Profile ↓ Paper Section "Neuron Matching Robustness"
- False Negatives ↓ Conserved Circuits Profile ↓ Paper Section "Conserved Circuit Robustness"
