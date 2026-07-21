# Kaggle Execution Pipeline & Export Architecture Report

This report provides a comprehensive architectural analysis of the FlyWire framework's Kaggle execution pipeline, detailing exactly how the experimental framework (Phases 001–017) processes inputs, executes simulations, and exports artifacts. This document establishes the exact interface available for the future HCI, dashboard, and visualization layer.

---

## 1. Execution Pipeline

The execution is strictly orchestrated by the `experiments_missed_synapses.ipynb` notebook, serving as the master controller for batch experimental trials.

### Pipeline Flow:
1. **Initialization (Cells 2–6):** 
   - Imports framework components.
   - Defines the `EXPERIMENT` payload (dataset, error rates, seeds, configuration).
   - Extracts dataset ZIP.
   - Verifies registry implementations (Analysis & Error Models).
2. **Trial Instantiation (Cells 7–8):**
   - Instantiates `ExperimentRunner`.
   - Iterates through defined `error_rates` (e.g., 0%, 1%, 5%, 10%, 20%).
   - Iterates through `random_seeds` (e.g., 5 trials per rate).
3. **Core Framework Execution (`ExperimentRunner.run(config)`):**
   - Loads the dataset and builds the immutable baseline graph.
   - Preprocesses the graph (Phase 011 & 012).
   - Generates Vulnerability and Calibrated Probabilities (Phases 013 & 014).
   - Stochastically perturbs synapses via `MissedSynapsesModel` (Phase 015).
   - Builds a temporary perturbed graph.
   - Executes registered graph analyses (Phase 016).
   - Serializes Phase 012–016 checkpoints (Pickle).
   - Exports the trial's metrics, configuration, and summaries via `ExportManager`.
4. **Statistical Aggregation (Cell 9):**
   - Collects all successful trials (organized by error rate).
   - Invokes `StatisticalEvaluator.evaluate()` (Phase 017) to aggregate each non-zero error rate trial block and compares them strictly to the `0.0%` control (baseline) block.
   - Computes Means, Standard Deviations, 95% Confidence Intervals, and Cohen's *d* Effect Sizes.
   - Saves the Phase 017 artifact globally via `CheckpointManager`.
5. **Output (Cell 10–11):**
   - Prints metric DataFrames to stdout.
   - Signals completion.

---

## 2. Export Pipeline

The `ExportManager` is invoked individually for each completed trial. It creates a highly structured directory containing human-readable and machine-readable data.

For every single trial, the `ExportManager` produces:
- `metadata.json`: Comprehensive JSON tracking software, hardware, dataset versions, and parameters.
- `config_snapshot.yaml`: Complete YAML representation of the `ExperimentConfig`.
- `summary.csv`: Aggregated statistics representing only that specific trial.
- `trial_results.csv`: Highly flattened table of metrics generated during that specific trial.
- `runtime_report.txt`: A detailed text summary of pipeline timing, errors, warnings, and configurations.
- `README.md`: A markdown summary outlining the run parameters and components for quick orientation.
- `logs/` and `plots/`: Standardized empty placeholder directories.
- `[timestamp].zip` (Optional): A fully self-contained zipped archive of all the aforementioned trial files.

---

## 3. Checkpoint Pipeline

The `CheckpointManager` serializes intermediate execution variables natively via `pickle` into a local `checkpoints/` directory.

### Per-Trial Checkpoints (`trial_XX/checkpoints/`):
- **Phase 012**: Stores `biological_assumptions` and `edge_feature_table` (Polars DataFrame).
- **Phase 013**: Stores `edge_vulnerability_table`.
- **Phase 014**: Stores `target_error_rate` and `edge_probability_table`.
- **Phase 015**: Stores `simulation_statistics` (removed synapses, etc.) and `perturbed_graph_info` (node/edge counts).
- **Phase 016**: Stores `analysis_results` (raw output of centralities, structural checks, etc.).

### Global Batch Checkpoints (`results/checkpoints/`):
- **Phase 017**: Stores the cross-trial `evaluation_result` representing the total `StatisticalEvaluationResult` (Confidence Intervals, Effect Sizes).

*Note:* Graphs themselves are never checkpointed to prevent massive disk bloat.

---

## 4. Final Artifact Inventory

Upon successful execution of a full experiment (e.g., 5 error rates, 5 trials each), the filesystem looks like this:

```
results/
├── MANC/
│   └── missed_synapses/
│       ├── 0_percent/
│       │   ├── trial_001/
│       │   │   └── MANC_2026.../
│       │   │       ├── metadata.json
│       │   │       ├── config_snapshot.yaml
│       │   │       ├── summary.csv
│       │   │       ├── trial_results.csv
│       │   │       ├── runtime_report.txt
│       │   │       ├── README.md
│       │   │       ├── checkpoints/ (Phase 012-016 .pkl)
│       │   │       └── MANC_2026....zip
│       │   ├── trial_002/ ...
│       ├── 1_percent/ ...
│       ├── 5_percent/ ...
│       ├── 10_percent/ ...
│       └── 20_percent/ ...
└── checkpoints/
    ├── Missed Synapses Validation_0.0_phase_017.pkl
    ├── Missed Synapses Validation_0.01_phase_017.pkl
    └── ...
```

---

## 5. HCI Integration Boundary

The future Human-Computer Interaction (HCI) or dashboard layer is completely isolated from the computational framework. 

**Data Boundary Rules:**
1. **Required Inputs:** The HCI should ingest `metadata.json` (for dynamic filtering/indexing) and the global Phase 017 Pickles (`*_phase_017.pkl`) which contain all the aggregated visualization metrics (Means, CIs, Effect Sizes).
2. **Excluded Inputs:** The HCI does **not** need the raw graph structures or the individual Phase 012–016 checkpoints, as all necessary UI metrics have been extracted into the Phase 017 results.
3. **Stateless UI:** The UI operates natively on pre-computed exported summaries and can run asynchronously or offline from the framework runner.

---

## 6. Missing Information & Recommendations

**Analysis finding:** While the pipeline perfectly implements the methodology, there is a distinct gap regarding machine-readable Phase 017 outputs:

- **Missing Non-Python Outputs:** Phase 017 `StatisticalEvaluationResult` objects (containing the highly critical Cohen's *d* Effect Sizes, Confidence Intervals, and Means) are currently **only** saved as Python Pickle objects (`.pkl`) through the `CheckpointManager`. 
- **Impact on HCI:** If the dashboard layer is built in a non-Python language (e.g., a React/TypeScript frontend), or if users want to load the final tables into standard statistical tools (R, Excel), they will be unable to parse the `.pkl` files.
- **Recommendation:** The Phase 017 results should eventually be exported as globally consolidated `global_statistics.json` and `global_statistics.csv` files alongside the Pickles to ensure language-agnostic dashboard compatibility.

---

## 7. Evaluate Reproducibility

An experiment run is **100% reproducible**.
- The exact deterministic random seed is locked and saved inside `config_snapshot.yaml`.
- All biological assumptions, weightings, and rates are saved in `config_snapshot.yaml`.
- The dataset version and framework version (`_FRAMEWORK_VERSION = "1.0.0"`) are captured in `metadata.json`.
- The exact output metrics are tracked dynamically, guaranteeing that the dashboard can historically represent pipeline permutations accurately.
