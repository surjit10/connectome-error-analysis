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
        "[Phase 2] Analysis complete — %d metric(s), %d sensitive (|d|≥0.8).",
        len(sensitivity.summaries),
        len(sensitivity.sensitive_metrics),
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

    # Print sensitivity summary to console
    print("\n📊 SENSITIVITY SUMMARY")
    print("-" * 55)
    print(f"{'Rank':<5} {'Metric':<40} {'Max |d|':<10} {'Level'}")
    print("-" * 55)
    for s in sensitivity.summaries:
        indicator = " ⚠" if s.is_sensitive else ""
        print(f"{s.rank:<5} {s.metric_key:<40} {s.max_effect_size:<10.4f} {s.effect_label}{indicator}")
    print("-" * 55)
    print(f"Sensitive metrics: {len(sensitivity.sensitive_metrics)}/{len(sensitivity.summaries)}")


if __name__ == "__main__":
    main()
