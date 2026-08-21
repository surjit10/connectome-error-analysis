# FlyWire Hypothesis Testing — Organized Null Ensemble Results

Organized, validated results for the **BANC Null Ensemble** hypothesis testing experiments
(degree-preserving randomized connectome topology, Replicate 1).

Extracted and structured from `hypothesis_ouput_unorganised/` (August 2026).

---

## Directory Structure

```
hypothesis_output_organised/
├── README.md                                # This document
└── BANC/                                    # Dataset code (uppercase)
    ├── index.html                           # Dataset navigation dashboard
    ├── missed_synapses/                     # EM1 (Missed Synapses)
    │   ├── index.html                       # Model redirect
    │   ├── trials/                          # Raw per-trial experimental data (50 trials)
    │   │   ├── 0_percent/
    │   │   │   ├── trial_001/
    │   │   │   │   ├── README.md            # Trial overview
    │   │   │   │   ├── config_snapshot.yaml # Pipeline configuration snapshot
    │   │   │   │   ├── metadata.json        # Full runtime & perturbation metadata
    │   │   │   │   ├── runtime_report.txt   # Execution log & memory audit
    │   │   │   │   ├── summary.csv          # Scalar summary metrics
    │   │   │   │   └── trial_results.csv    # Full vector and scalar trial metrics
    │   │   │   ├── trial_002/ ... trial_005/
    │   │   ├── 0_5_percent/ ... 20_percent/
    │   └── reports/                         # Statistical reporting & visualization
    │       ├── 0_percent/ ... 20_percent/   # Per-rate report dashboards & plots
    │       ├── summary.html                 # Cross-rate metric dashboard
    │       └── trend_analysis/              # Multi-rate aggregated trends & figures
    │           ├── combined_results.csv
    │           ├── combined_statistics.csv
    │           ├── trend_report.html
    │           └── plots/
    ├── false_synapses/                      # EM2 (False Synapses)
    │   ├── candidates/
    │   │   └── false_synapse_candidates.parquet # Candidate synapse pairs
    │   ├── trials/ ...
    │   └── reports/ ...
    ├── synapse_count_measurement/           # EM3 (Synapse Count Measurement)
    │   ├── trials/ ...
    │   └── reports/ ...
    ├── split_errors/                        # EM4 (Split Errors)
    │   ├── trials/ ...
    │   └── reports/ ...
    ├── merge_errors/                        # EM5 (Merge Errors)
    │   ├── trials/ ...
    │   └── reports/ ...
    ├── null_observations/
    │   ├── replicate_level_effects.csv      # Unified 8,250 replicate records
    │   └── replicate_level_effects.parquet
    └── comparisons/
        ├── secondary_effect_summary.csv     # Combined secondary effects summary
        ├── hypothesis_test_results.csv      # Welch's t-test, Cohen's d & FDR corrections
        ├── corrected_significance_results.csv# Statistically significant emergent findings
        ├── comparative_metrics_summary.csv # Real vs Null comparative rate metrics
        ├── summary.md                       # Comprehensive narrative scientific report
        └── plots/                           # High-res Real vs Null comparison plots
```

---

## Experimental Design & Parameters

| Parameter | Specification |
|:---|:---|
| **Dataset** | BANC (`FlyWire Brain Area Network Connectome`) |
| **Null Model** | `degree_preserving` (Directed degree-preserving edge-swap rewiring) |
| **Null Replicate** | `rep_1` (Null Topology Seed 1) |
| **Error Models** | 5 models (`missed_synapses`, `false_synapses`, `synapse_count_measurement`, `split_errors`, `merge_errors`) |
| **Error Rates** | 10 rates: `0%`, `0.5%`, `1%`, `2%`, `3%`, `5%`, `7.5%`, `10%`, `15%`, `20%` |
| **Replication** | 5 independent stochastic seeds (`trial_001` .. `trial_005`) per rate |
| **Total Trials** | 250 experimental runs (5 models × 10 rates × 5 seeds) |
| **Analyses** | `basic_structure`, `degree_distribution`, `connected_components`, `reciprocity`, `pagerank` |

---

## Metric Categorization

1. **Primary Imposed Manipulations (`primary_imposed`)**:
   Metrics mathematically or algebraically determined by the error model operation (e.g., edge count and total synapses under missed/false synapses; mean weight under synapse count noise; node count under split/merge errors).

2. **Control Invariants (`control_invariant`)**:
   Topological properties preserved by design under the specific error model (e.g., node count under missed/false synapses).

3. **Secondary Emergent Structural Effects (`secondary_emergent`)**:
   Genuine network-level emergent phenomena (reciprocity, degree assortativity, largest connected component sizes, PageRank preservation). These metrics are subject to Benjamini-Hochberg FDR-corrected hypothesis testing against the real connectome.
