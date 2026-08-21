#!/usr/bin/env python3
"""
Organize Hypothesis Testing Outputs
===================================
Extracts and organizes the unorganized hypothesis testing outputs from:
    /home/surjit/Desktop/flywire/v1/hypothesis_ouput_unorganised/
into the canonical FlyWire structure under:
    /home/surjit/Desktop/flywire/v1/hypothesis_output_organised/BANC/

Handles:
  1. Extraction and normalization of trial directories for 5 error models
  2. False synapse candidate cache archiving
  3. Replicate-level null observations consolidation (CSV + Parquet)
  4. Generation of reports, trend analyses, and interactive HTML dashboards
  5. Top-level dataset documentation (README.md)
"""

from __future__ import annotations

import csv
import io
import json
import logging
import os
import re
import shutil
import sys
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
import polars as pl

# Ensure project modules are importable
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from modules.statistical_evaluation.evaluator import (
    StatisticalEvaluationResult,
    MetricEvaluation,
    _safe_cohens_d,
)
from modules.statistical_evaluation.vector_comparison import VectorComparisonRegistry
from modules.reporting.trend_analysis import TrendAnalysis
from modules.reporting.sensitivity_analysis import SensitivityAnalysis
from presentation.dataset_exporter import DatasetExporter
from presentation.comparison_exporter import ComparisonExporter
from presentation.root_index_exporter import RootIndexExporter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("organize_hypothesis_data")

SRC_DIR = PROJECT_ROOT / "hypothesis_ouput_unorganised"
DST_ROOT = PROJECT_ROOT / "hypothesis_output_organised"
DST_BANC = DST_ROOT / "BANC"

EM_ZIP_MAP = {
    "error1.zip": "missed_synapses",
    "error2.zip": "false_synapses",
    "error3.zip": "synapse_count_measurement",
    "error4.zip": "split_errors",
    "error5.zip": "merge_errors",
}

EM_DISPLAY_MAP = {
    "missed_synapses": "Missed Synapses",
    "false_synapses": "False Synapses",
    "synapse_count_measurement": "Synapse Count Measurement",
    "split_errors": "Split Errors",
    "merge_errors": "Merge Errors",
}


def rate_float_to_folder_name(rate: float) -> str:
    """Convert float error rate (e.g. 0.005) to folder name (e.g. '0_5_percent')."""
    pct = round(rate * 100.0, 4)
    if pct == int(pct):
        return f"{int(pct)}_percent"
    s = f"{pct}".rstrip("0").rstrip(".")
    return f"{s.replace('.', '_')}_percent"


def folder_name_to_rate_float(folder_name: str) -> float:
    """Convert folder name (e.g. '0_5_percent') to float error rate (0.005)."""
    num_str = folder_name.replace("_percent", "").replace("percent", "")
    # Handle numbers with underscores like '7_5' -> '7.5' or '0_5' -> '0.5'
    num_str = num_str.replace("_", ".")
    return float(num_str) / 100.0


def extract_and_organize_trials() -> None:
    """Extract and organize trial files from zip archives."""
    logger.info("=" * 70)
    logger.info("Extracting and organizing trial directories...")
    logger.info("=" * 70)

    DST_BANC.mkdir(parents=True, exist_ok=True)
    all_null_records: List[pd.DataFrame] = []

    for zip_name, em_name in EM_ZIP_MAP.items():
        zip_path = SRC_DIR / zip_name
        if not zip_path.exists():
            logger.warning(f"Archive not found: {zip_path}")
            continue

        logger.info(f"Processing {zip_name} -> {em_name}...")
        em_dir = DST_BANC / em_name
        trials_root = em_dir / "trials"
        trials_root.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(zip_path, "r") as zf:
            namelist = zf.namelist()

            # 1. Discover all trial runs
            # Pattern: results/hypothesis_testing/BANC/null/rep_1/<em_name>/rate_<rate>_seed_<seed>/<run_id>/<file>
            trial_run_pattern = re.compile(
                r"^results/hypothesis_testing/BANC/null/rep_1/[^/]+/rate_([0-9.]+)_seed_(\d+)/([^/]+)/([^/]+)$"
            )

            trials_extracted = 0
            for name in namelist:
                m = trial_run_pattern.match(name)
                if m:
                    rate_float = float(m.group(1))
                    seed_int = int(m.group(2))
                    run_id = m.group(3)
                    filename = m.group(4)

                    rate_folder = rate_float_to_folder_name(rate_float)
                    seed_folder = f"trial_{seed_int:03d}"

                    target_trial_dir = trials_root / rate_folder / seed_folder
                    target_trial_dir.mkdir(parents=True, exist_ok=True)

                    target_file = target_trial_dir / filename
                    with zf.open(name) as src_f, open(target_file, "wb") as dst_f:
                        dst_f.write(src_f.read())
                    trials_extracted += 1

            logger.info(f"  Extracted {trials_extracted} files across trials for {em_name}.")

            # 2. Extract false synapses candidates cache if present
            if em_name == "false_synapses":
                candidates_dir = em_dir / "candidates"
                candidates_dir.mkdir(parents=True, exist_ok=True)
                for cand_file in [
                    "research_data/cache/false_synapses/candidates.parquet",
                    "research_data/cache/false_synapses/candidates_banc_null_rep1.parquet",
                ]:
                    if cand_file in namelist:
                        target_name = (
                            "false_synapse_candidates.parquet"
                            if "candidates.parquet" in cand_file and not cand_file.endswith("rep1.parquet")
                            else Path(cand_file).name
                        )
                        target_cand_file = candidates_dir / target_name
                        with zf.open(cand_file) as src_f, open(target_cand_file, "wb") as dst_f:
                            dst_f.write(src_f.read())
                        logger.info(f"  Extracted candidate cache: {target_cand_file.name}")

            # 3. Extract replicate-level effects
            rep_csv_name = "results/hypothesis_testing/BANC/null_observations/replicate_level_effects.csv"
            if rep_csv_name in namelist:
                with zf.open(rep_csv_name) as src_f:
                    df = pd.read_csv(src_f)
                    df["error_model"] = em_name
                    all_null_records.append(df)
                    logger.info(f"  Loaded replicate_level_effects: {len(df)} rows.")

    # 4. Consolidate null observations into unified replicate_level_effects
    if all_null_records:
        null_obs_dir = DST_BANC / "null_observations"
        null_obs_dir.mkdir(parents=True, exist_ok=True)

        comp_dir = DST_BANC / "comparisons"
        comp_dir.mkdir(parents=True, exist_ok=True)

        combined_null_df = pd.concat(all_null_records, ignore_index=True)
        # Ensure condition is set to 'null'
        combined_null_df["condition"] = "null"

        csv_out = null_obs_dir / "replicate_level_effects.csv"
        combined_null_df.to_csv(csv_out, index=False)
        logger.info(f"Wrote unified null observations CSV: {csv_out} ({len(combined_null_df)} rows).")

        # Also write parquet using polars directly from CSV
        parquet_out = null_obs_dir / "replicate_level_effects.parquet"
        pl_df = pl.read_csv(csv_out)
        pl_df.write_parquet(parquet_out)
        logger.info(f"Wrote unified null observations Parquet: {parquet_out}.")

        # Write secondary_effect_summary in comparisons/
        comp_csv = comp_dir / "secondary_effect_summary.csv"
        combined_null_df.to_csv(comp_csv, index=False)
        logger.info(f"Wrote comparisons secondary_effect_summary: {comp_csv}.")


def generate_presentation_layer() -> None:
    """Generate reporting dashboards, summary HTML, and trend analysis for all error models."""
    logger.info("=" * 70)
    logger.info("Building presentation and reporting layer for BANC Null dataset...")
    logger.info("=" * 70)

    # Allow large field size for vector deserialization
    csv.field_size_limit(sys.maxsize)

    _VECTOR_STRATEGIES = VectorComparisonRegistry.list_registrations()
    _VECTOR_COLUMNS = {
        (a_name, m_key): f"metric_{m_key}"
        for a_name, m_key in _VECTOR_STRATEGIES
    }

    def load_aggregated_trials(folder: Path) -> dict:
        trial_dirs = sorted(folder.glob("trial_*"))
        all_trials = []
        for t in trial_dirs:
            summary_csv = t / "summary.csv"
            if not summary_csv.exists():
                continue
            trial = {}
            with open(summary_csv, newline="", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    try:
                        trial.setdefault(row["analysis"], {})[row["metric"]] = float(row["mean"])
                    except (ValueError, KeyError):
                        pass
            all_trials.append(trial)
        if not all_trials:
            return {}

        data = {}
        for a_name in all_trials[0]:
            data[a_name] = {}
            for m_name in all_trials[0][a_name]:
                vals = [
                    t[a_name][m_name]
                    for t in all_trials
                    if a_name in t and m_name in t[a_name]
                ]
                n = len(vals)
                mean = float(np.mean(vals)) if n > 0 else 0.0
                std = float(np.std(vals, ddof=1)) if n > 1 else 0.0
                margin = 1.96 * std / np.sqrt(n) if n > 0 else 0.0
                data[a_name][m_name] = {
                    "mean": mean,
                    "std": std,
                    "n": n,
                    "ci_lower": mean - margin,
                    "ci_upper": mean + margin,
                }
        return data

    def load_vector_cols(folder: Path) -> dict:
        collected = {}
        for t in sorted(folder.glob("trial_*")):
            tr = t / "trial_results.csv"
            if not tr.exists():
                continue
            try:
                with open(tr, newline="", encoding="utf-8") as f:
                    for row in csv.DictReader(f):
                        a_name = row.get("analysis_name", "")
                        for (an, m_key), col in _VECTOR_COLUMNS.items():
                            if a_name != an:
                                continue
                            raw = row.get(col, "")
                            if not raw:
                                continue
                            import ast
                            try:
                                vec = ast.literal_eval(raw)
                                collected.setdefault((an, m_key), []).append(
                                    [float(v) for v in vec]
                                )
                            except Exception:
                                continue
            except Exception as e:
                logger.debug(f"Error reading vector columns from {tr}: {e}")
        return collected

    def vector_derived_stats(folder: Path, avg_baselines: dict) -> dict:
        vecs_by_key = load_vector_cols(folder)
        out = {}
        for a_name, m_key in _VECTOR_STRATEGIES:
            strategy = VectorComparisonRegistry.get(a_name, m_key)
            if strategy is None:
                continue
            avg_baseline = avg_baselines.get((a_name, m_key))
            if avg_baseline is None:
                continue
            vectors = vecs_by_key.get((a_name, m_key))
            if not vectors:
                continue
            derived = {}
            for pv in vectors:
                try:
                    comp = strategy(avg_baseline, pv, {"top_k_overlap": 100})
                except Exception:
                    continue
                for k, v in comp.items():
                    if v is not None and np.isfinite(v):
                        derived.setdefault(k, []).append(v)
            if not derived:
                continue
            out.setdefault(a_name, {})
            for k, vals in derived.items():
                n = len(vals)
                mean = float(np.mean(vals))
                std = float(np.std(vals, ddof=1)) if n > 1 else 0.0
                margin = 1.96 * std / np.sqrt(n) if n > 0 else 0.0
                out[a_name][f"{m_key}_{k}"] = {
                    "mean": mean,
                    "std": std,
                    "n": n,
                    "ci_lower": mean - margin,
                    "ci_upper": mean + margin,
                }
        return out

    def build_model_results(em_dir: Path) -> Dict[float, StatisticalEvaluationResult]:
        trials_dir = em_dir / "trials"
        baseline = load_aggregated_trials(trials_dir / "0_percent")

        avg_baselines = {}
        b_vecs_by_key = load_vector_cols(trials_dir / "0_percent")
        for key, vectors in b_vecs_by_key.items():
            arr = np.array(vectors)
            avg_baselines[key] = arr.mean(axis=0).tolist()

        results_by_rate = {}
        for folder in sorted(trials_dir.glob("*_percent")):
            rate = folder_name_to_rate_float(folder.name)
            rate_data = load_aggregated_trials(folder)
            if not rate_data:
                continue

            vector_derived = vector_derived_stats(folder, avg_baselines)
            derived_keys = set()
            for a_name, m_dict in vector_derived.items():
                rate_data.setdefault(a_name, {})
                for m_name, stats in m_dict.items():
                    rate_data[a_name][m_name] = stats
                    derived_keys.add((a_name, m_name))

            metrics = {}
            for a_name, m_dict in rate_data.items():
                metrics[a_name] = {}
                for m_name, pm in m_dict.items():
                    if (a_name, m_name) in derived_keys:
                        if m_name.endswith("pearson") or m_name.endswith("spearman") or m_name.endswith("top_k_overlap"):
                            b_val = 1.0
                        else:
                            b_val = 0.0
                        d = _safe_cohens_d(pm["mean"], pm["std"], pm["n"], b_val, 0.0, 1)
                        b_mean, b_std, b_n = b_val, 0.0, 1
                    else:
                        bm = baseline.get(a_name, {}).get(m_name)
                        if bm:
                            d = _safe_cohens_d(pm["mean"], pm["std"], pm["n"], bm["mean"], bm["std"], bm["n"])
                            b_mean, b_std, b_n = bm["mean"], bm["std"], bm["n"]
                        else:
                            d = _safe_cohens_d(pm["mean"], pm["std"], pm["n"], 0.0, 0.0, 1)
                            b_mean, b_std, b_n = 0.0, 0.0, 1

                    metrics[a_name][m_name] = MetricEvaluation(
                        metric_name=m_name,
                        baseline_mean=b_mean,
                        baseline_std=b_std,
                        mean=pm["mean"],
                        std=pm["std"],
                        ci_lower=pm["ci_lower"],
                        ci_upper=pm["ci_upper"],
                        effect_size=d,
                    )
            n_trials = len(list(folder.glob("trial_*")))
            results_by_rate[rate] = StatisticalEvaluationResult(
                dataset_name="BANC",
                error_level=rate,
                n_trials=n_trials,
                runtime_seconds=0.0,
                metrics=metrics,
            )
        return results_by_rate

    # Generate presentations per model
    exporters = []
    for slug, display in EM_DISPLAY_MAP.items():
        em_dir = DST_BANC / slug
        if not (em_dir / "trials").exists():
            continue

        results_by_rate = build_model_results(em_dir)
        if not results_by_rate:
            logger.warning(f"[{slug}] No results built.")
            continue

        reports_dir = em_dir / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)

        trend = TrendAnalysis(
            results_by_rate=results_by_rate,
            dataset_name="BANC",
            error_model_name=slug,
        ).compute()
        sensitivity = SensitivityAnalysis(trend).compute()

        exporter = DatasetExporter(
            output_dir=reports_dir,
            results_by_rate=results_by_rate,
            trend=trend,
            sensitivity=sensitivity,
            error_model_slug=slug,
            error_model_display=display,
            dataset_name="BANC",
            results_root=DST_BANC,
        )
        exporter.export()
        exporters.append((slug, display, exporter))

        # Create model index.html redirecting to reports/summary.html
        model_index = em_dir / "index.html"
        model_index.write_text(
            f'<!DOCTYPE html><html><head><meta http-equiv="refresh" content="0; url=reports/summary.html">'
            f'<title>{display} - BANC</title></head><body><p>Redirecting to <a href="reports/summary.html">summary</a>...</p></body></html>',
            encoding="utf-8",
        )
        logger.info(f"[{slug}] Exported reporting layer ({len(results_by_rate)} rates).")

    # Write dataset index.html
    dataset_index = DST_BANC / "index.html"
    model_links = "\n".join(
        f'    <li><a href="{slug}/reports/summary.html">{display}</a></li>'
        for slug, display in EM_DISPLAY_MAP.items()
    )
    dataset_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>BANC — Hypothesis Testing Null Ensemble</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background: #0d1117; color: #e6edf3; max-width: 900px; margin: 0 auto; padding: 2.5rem; }}
    h1 {{ color: #58a6ff; font-size: 2rem; margin-bottom: 0.5rem; }}
    p.lead {{ color: #8b949e; font-size: 1.1rem; margin-bottom: 2rem; }}
    ul {{ list-style-type: none; padding: 0; }}
    li {{ margin: 0.75rem 0; }}
    a {{ color: #58a6ff; text-decoration: none; font-size: 1.1rem; font-weight: 500; padding: 0.5rem 1rem; background: #161b22; border: 1px solid #30363d; border-radius: 6px; display: inline-block; transition: all 0.2s ease; }}
    a:hover {{ background: #1f6feb; color: #ffffff; border-color: #58a6ff; }}
    .card {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 1.5rem; margin-top: 2rem; }}
    .badge {{ background: #238636; color: white; padding: 0.2rem 0.5rem; border-radius: 4px; font-size: 0.85rem; font-weight: 600; }}
  </style>
</head>
<body>
  <h1>BANC — Hypothesis Testing Null Ensemble</h1>
  <p class="lead">Degree-preserving randomized ensemble results across 5 synapse error models (10 rates × 5 seeds = 250 trials).</p>
  
  <h2>Error Models</h2>
  <ul>
{model_links}
  </ul>

  <div class="card">
    <h3>Dataset Summary</h3>
    <p><strong>Null Model:</strong> <code>degree_preserving</code> (directed in/out degree-sequence matched random graph)</p>
    <p><strong>Total Trials:</strong> 250 (5 error models × 10 error rates × 5 seeds)</p>
    <p><strong>Analyses Performed:</strong> Basic Structure, Degree Distribution, Connected Components, Reciprocity, PageRank</p>
  </div>
</body>
</html>
"""
    dataset_index.write_text(dataset_html, encoding="utf-8")
    logger.info(f"Wrote dataset index: {dataset_index}")


def write_readme() -> None:
    """Create comprehensive README.md in hypothesis_output_organised/."""
    readme_path = DST_ROOT / "README.md"
    content = """# FlyWire Hypothesis Testing — Organized Null Ensemble Results

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
"""
    readme_path.write_text(content, encoding="utf-8")
    logger.info(f"Wrote top-level README: {readme_path}")


def main() -> None:
    extract_and_organize_trials()
    generate_presentation_layer()
    write_readme()
    logger.info("=" * 70)
    logger.info("Hypothesis output organization COMPLETE!")
    logger.info("=" * 70)


if __name__ == "__main__":
    main()
