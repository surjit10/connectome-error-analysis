"""
generate_plots.py
=================
Scientific Reporting Pipeline — Orchestration Layer

Reads raw trial output CSVs and drives the complete reporting pipeline:

    Phase 1: Load all error-rate data
    Phase 2: Run scientific analysis (trend, sensitivity)
    Phase 3: Export per-rate, trend, and summary HTML reports
    Phase 4: Generate root index

This script is a **pure orchestrator** — it performs NO statistical analysis,
NO plotting, and NO HTML generation itself.  All such work is delegated to
the appropriate modules.

Usage:
    source .venv/bin/activate
    python generate_plots.py \\
        --error-model missed_synapses \\
        --dataset BANC \\
        --input-dir MissedSynapses_BANC_results \\
        --output-dir results

    # Quick run with defaults (same as above):
    python generate_plots.py
"""

import argparse
import logging
import sys
from pathlib import Path

# ── Bootstrap path ────────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent))

from modules.reporting.data_loader import ReportingDataLoader
from modules.reporting.trend_analysis import TrendAnalysis
from modules.reporting.sensitivity_analysis import SensitivityAnalysis
from presentation.error_model_exporter import ErrorModelExporter
from presentation.root_index_exporter import RootIndexExporter
from presentation.preservation_config import calculate_preservation, get_biological_status, get_change_interpretation, higher_is_better, is_preservation_metric, is_change_metric

# ── Logging setup ─────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("generate_plots")

# ── Human-readable error model names ─────────────────────────────────────
_ERROR_MODEL_DISPLAY = {
    "missed_synapses":           "Missed Synapses",
    "false_positive_synapses":   "False Positive Synapses",
    "edge_weight_noise":         "Edge Weight Noise",
    "neurotransmitter_errors":   "Neurotransmitter Errors",
    "neuron_identity_errors":    "Neuron Identity Errors",
}

_ERROR_MODEL_DESCRIPTION = {
    "missed_synapses":           "Topological degradation from simulated missing synapses (false-negative edge removal).",
    "false_positive_synapses":   "Impact of spurious synapse insertion (false-positive edges).",
    "edge_weight_noise":         "Effect of Gaussian noise applied to synapse count weights.",
    "neurotransmitter_errors":   "Consequence of neurotransmitter type misclassification.",
    "neuron_identity_errors":    "Effect of neuron class / cell-type identity mis-assignment.",
}


# ── CLI ───────────────────────────────────────────────────────────────────

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="FlyWire Scientific Reporting Pipeline",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--error-model", "-e",
        default="missed_synapses",
        help="Slug of the error model (e.g. missed_synapses, edge_weight_noise).",
    )
    parser.add_argument(
        "--dataset", "-d",
        default="BANC",
        help="Dataset name (e.g. BANC, FAFB, MANC).",
    )
    parser.add_argument(
        "--input-dir", "-i",
        default=None,
        help="Root directory of raw simulation results.  Defaults to "
             "{ErrorModel}_{Dataset}_results (e.g. MissedSynapses_BANC_results).",
    )
    parser.add_argument(
        "--output-dir", "-o",
        default="results",
        help="Root output directory where reports will be written.",
    )
    return parser.parse_args()


# ── Main pipeline ─────────────────────────────────────────────────────────

def main() -> None:
    args = _parse_args()

    error_model_slug    = args.error_model
    dataset_name        = args.dataset
    results_root        = Path(args.output_dir)
    error_model_display = _ERROR_MODEL_DISPLAY.get(
        error_model_slug,
        error_model_slug.replace("_", " ").title(),
    )
    error_model_desc    = _ERROR_MODEL_DESCRIPTION.get(
        error_model_slug,
        "Biological error model experiment.",
    )

    # Resolve input directory
    if args.input_dir:
        input_root = Path(args.input_dir)
    else:
        # Convention: {PascalCase(error_model)}_{dataset}_results
        pascal = "".join(w.capitalize() for w in error_model_slug.split("_"))
        input_root = Path(f"{pascal}_{dataset_name}_results")

    logger.info("=" * 60)
    logger.info("FlyWire Scientific Reporting Pipeline")
    logger.info("=" * 60)
    logger.info("Error model : %s (%s)", error_model_slug, error_model_display)
    logger.info("Dataset     : %s", dataset_name)
    logger.info("Input root  : %s", input_root)
    logger.info("Output root : %s", results_root)
    logger.info("=" * 60)

    # ── Phase 1: Load data ────────────────────────────────────────────
    logger.info("[Phase 1] Loading experiment data...")
    loader = ReportingDataLoader(
        results_root = input_root,
        dataset_name = dataset_name,
    )
    try:
        results_by_rate = loader.load()
    except FileNotFoundError as exc:
        logger.error("Cannot load data: %s", exc)
        sys.exit(1)

    if not results_by_rate:
        logger.error("No experiment results found in %s — aborting.", input_root)
        sys.exit(1)

    logger.info(
        "[Phase 1] Loaded %d error rate(s): %s",
        len(results_by_rate),
        [f"{r*100:.0f}%" for r in sorted(results_by_rate)],
    )

    # ── Phase 2: Scientific analysis ─────────────────────────────────
    logger.info("[Phase 2] Running trend analysis...")
    trend = TrendAnalysis(
        results_by_rate  = results_by_rate,
        dataset_name     = dataset_name,
        error_model_name = error_model_slug,
    ).compute()

    logger.info("[Phase 2] Running sensitivity analysis...")
    sensitivity = SensitivityAnalysis(trend).compute()

    logger.info(
        "[Phase 2] Analysis complete — %d metric(s).",
        len(sensitivity.summaries),
    )

    # ── Phase 3: Export reports ───────────────────────────────────────
    logger.info("[Phase 3] Exporting reports...")
    em_exporter = ErrorModelExporter(
        output_dir          = results_root / error_model_slug,
        error_model_slug    = error_model_slug,
        error_model_display = error_model_display,
        description         = error_model_desc,
        results_root        = results_root,
    )
    em_exporter.add_dataset(
        dataset_name    = dataset_name,
        results_by_rate = results_by_rate,
        trend           = trend,
        sensitivity     = sensitivity,
    )
    em_exporter.export()

    # ── Phase 4: Root index ───────────────────────────────────────────
    logger.info("[Phase 4] Generating root index...")
    RootIndexExporter(results_root).export()

    # ── Done ──────────────────────────────────────────────────────────
    logger.info("=" * 60)
    logger.info("✅  Pipeline complete!")
    logger.info("")
    logger.info("  Output root : %s", results_root)
    logger.info("  Landing page: %s/index.html", results_root)
    logger.info("  Error model : %s/%s/overview.html", results_root, error_model_slug)
    logger.info("  Dataset     : %s/%s/%s/summary.html", results_root, error_model_slug, dataset_name)
    logger.info("  Trend       : %s/%s/%s/trend_analysis/trend_report.html",
                results_root, error_model_slug, dataset_name)
    logger.info("=" * 60)

    # Print preservation summary to console
    print("\n🧬 STRUCTURAL PRESERVATION")
    print("-" * 70)
    print(f"{'Rank':<5} {'Metric':<40} {'Min Preservation':<17} {'Status'}")
    print("-" * 70)
    from collections import defaultdict
    pres_vals = defaultdict(list)
    for rate, res in results_by_rate.items():
        if rate > 0.0:
            for a_name, m_dict in res.metrics.items():
                for m_name, ev in m_dict.items():
                    key = f"{a_name}.{m_name}"
                    if not is_preservation_metric(key):
                        continue
                    pres = calculate_preservation(ev.baseline_mean, ev.mean, higher_is_better=higher_is_better(key))
                    pres_vals[key].append(pres)
    
    ranking = sorted([(k, min(v)) for k, v in pres_vals.items()], key=lambda x: x[1])
    for rank, (key, min_pres) in enumerate(ranking, start=1):
        _, bio_label, _ = get_biological_status(min_pres)
        print(f"{rank:<5} {key:<40} {min_pres:<10.2f}%    {bio_label}")
    print("-" * 70)
    print(f"Preservation metrics: {len(ranking)}")
    
    # Print change summary
    print("\n📊 STRUCTURAL CHANGE INDICATORS")
    print("-" * 70)
    print(f"{'Metric':<40} {'Baseline':<12} {'Perturbed':<12} {'Δ%':<10} {'Interpretation'}")
    print("-" * 70)
    for rate in sorted(results_by_rate.keys()):
        if rate > 0.0:
            res = results_by_rate[rate]
            for a_name, m_dict in res.metrics.items():
                for m_name, ev in m_dict.items():
                    key = f"{a_name}.{m_name}"
                    if not is_change_metric(key):
                        continue
                    baseline = ev.baseline_mean
                    perturbed = ev.mean
                    delta_pct = ((perturbed - baseline) / abs(baseline) * 100) if baseline != 0 else 0.0
                    is_inc = delta_pct > 0
                    interp = get_change_interpretation(key, delta_pct, is_inc)
                    print(f"{key:<40} {baseline:<12.2f} {perturbed:<12.2f} {delta_pct:<+9.2f}%  {interp}")
            break  # Show first perturbed rate only
    print("-" * 70)


if __name__ == "__main__":
    main()
