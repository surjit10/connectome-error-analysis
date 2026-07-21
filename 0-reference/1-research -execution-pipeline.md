I would visualize it as a proper **research execution pipeline** rather than a simple flowchart. This makes it much easier to understand where everything happens (Local Machine, GitHub, Kaggle, and Results).

```
┌──────────────────────────────────────────────────────────────────────────────────────────────┐
│                            FLYWIRE RESEARCH EXECUTION PIPELINE                               │
└──────────────────────────────────────────────────────────────────────────────────────────────┘


                                     LOCAL MACHINE
══════════════════════════════════════════════════════════════════════════════════════════════════

           Download FlyWire Datasets
                    │
                    ▼
      research_data/raw/
      ├── BANC_v888/
      ├── FAFB_v783/
      ├── MANC_v1.2.1/
      ├── MAOL_v1.1/
      └── MCNS_v0.9/
                    │
                    │
                    │ (Upload Once)
                    ▼
           Kaggle Dataset
      (Compressed .csv.gz Files)

──────────────────────────────────────────────────────────────────────────────────────────────────

        Develop Framework
                    │
                    ▼
      GitHub Repository
      ├── core/
      ├── modules/
      ├── configs/
      ├── notebooks/
      └── docs/
                    │
                    │ Push
                    ▼
                 GitHub

══════════════════════════════════════════════════════════════════════════════════════════════════
                                     KAGGLE NOTEBOOK
══════════════════════════════════════════════════════════════════════════════════════════════════

              Open Notebook

       notebooks/01_run_experiment.ipynb

                    │
                    ▼

      ExperimentRunner.run(
          "configs/experiments/
           false_negatives/
           structural/
           manc.yaml"
      )

                    │
                    ▼
┌──────────────────────────────────────────────────────────────┐
│              CONFIGURATION RESOLUTION                        │
├──────────────────────────────────────────────────────────────┤
│ defaults.yaml                                                │
│        +                                                     │
│ datasets/manc.yaml                                           │
│        +                                                     │
│ error_models/false_negatives.yaml                            │
│        +                                                     │
│ analyses/structural.yaml                                     │
│        +                                                     │
│ experiments/false_negatives/structural/manc.yaml             │
└──────────────────────────────────────────────────────────────┘

                    │
                    ▼

        Final Experiment Configuration

══════════════════════════════════════════════════════════════════════════════════════════════════
                               DATA LOADING
══════════════════════════════════════════════════════════════════════════════════════════════════

         data_loader.py

                │

Reads directly from

/kaggle/input/flywire-datasets/

        ▼

MANC_v1.2.1/
    neurons.csv.gz
    connections_princeton.csv.gz

(No manual extraction)

                │
                ▼

      Build Graph
(NetworkX / igraph)

══════════════════════════════════════════════════════════════════════════════════════════════════
                           PREPROCESSING
══════════════════════════════════════════════════════════════════════════════════════════════════

Raw Graph
    │
    ▼
Validate Graph
    │
    ▼
Clean Graph
    │
    ▼
Compute Cached Statistics
    │
    ▼
Ready Graph

══════════════════════════════════════════════════════════════════════════════════════════════════
                           BASELINE ANALYSIS
══════════════════════════════════════════════════════════════════════════════════════════════════

Original Graph

        │

Run Structural Analysis

        │

Save Baseline Metrics

        │

Keep in Memory

══════════════════════════════════════════════════════════════════════════════════════════════════
                           EXPERIMENT LOOP
══════════════════════════════════════════════════════════════════════════════════════════════════

For Each Error Level

0.1%
 │
 ├── Trial 1
 ├── Trial 2
 ├── ...
 └── Trial 20

        │
        ▼

Aggregate Statistics

        │

Next Error Level

0.25%

        │

Repeat

        │

0.5%

        │

Repeat

        │

...

        │

30%

══════════════════════════════════════════════════════════════════════════════════════════════════
                           SINGLE TRIAL
══════════════════════════════════════════════════════════════════════════════════════════════════

Original Graph
        │
        ▼
Deep Copy
        │
        ▼
Apply Missed Synapse Error
        │
        ▼
Run Structural Analysis
        │
        ▼
Save Trial Metrics
        │
        ▼
Delete Graph From RAM

(Original Graph Never Changes)

══════════════════════════════════════════════════════════════════════════════════════════════════
                           POST PROCESSING
══════════════════════════════════════════════════════════════════════════════════════════════════

320 Trial Results

        │

statistics_engine.py

        │

Mean
Std
Variance
Confidence Intervals

        │

summary.csv

══════════════════════════════════════════════════════════════════════════════════════════════════
                           EXPORT PACKAGE
══════════════════════════════════════════════════════════════════════════════════════════════════

export_manager.py

        │

Creates

FalseNegatives_MANC.zip

        │

Contains

README.md
metadata.json
config_snapshot.yaml
summary.csv
trial_results.csv
plots/
runtime_report.txt

══════════════════════════════════════════════════════════════════════════════════════════════════
                                LOCAL MACHINE
══════════════════════════════════════════════════════════════════════════════════════════════════

Download ZIP

        │

Store

research_data/
└── experiments/
    └── false_negatives/
        └── structural/
            └── MANC/
                └── FalseNegatives_MANC.zip

        │

Review Results

        │

Copy Only

summary.csv
        │
        ▼
results/summaries/

Figures
        │
        ▼
results/paper/

══════════════════════════════════════════════════════════════════════════════════════════════════
                           RESEARCH OUTPUT
══════════════════════════════════════════════════════════════════════════════════════════════════

results/summaries/
        │
        ▼
02_compare_datasets.ipynb
        │
        ▼
results/cross_dataset/
        │
        ▼
03_generate_paper.ipynb
        │
        ▼
Paper Figures
        │
        ▼
Research Paper
```

I think this is a better visualization because it clearly separates:

* **Local machine responsibilities** (datasets, GitHub, downloaded results),
* **Kaggle responsibilities** (execution and computation),
* **Framework internals** (configuration, loading, preprocessing, perturbation, analysis, export),
* **Research workflow** (review → summaries → cross-dataset comparison → paper).

It also makes it obvious that **the notebook is only a launcher**, while all the actual logic lives in your reusable framework.
