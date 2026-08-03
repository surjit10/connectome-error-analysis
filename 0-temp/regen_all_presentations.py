"""Regenerate the presentation layer for EM1/EM2/EM3 from fresh trial data.

Reads per-trial aggregated summary.csv files under results/BANC/<error_model>/,
rebuilds StatisticalEvaluationResult per error rate (baseline from 0_percent),
computes TrendAnalysis + SensitivityAnalysis, and runs DatasetExporter so the
presentation lands directly in:

    results/BANC/<error_model>/
        summary.html
        error_0/ ... error_20/
        trend_analysis/

Also reconstructs **vector-derived** metrics (pagerank_scores_pearson /
_spearman / _topk_overlap) from the raw pagerank vectors stored in each
per-trial trial_results.csv — the scalar-only summary.csv path drops them.
Uses the framework's own compare_pagerank strategy so values match the
original Kaggle presentation.
"""
import ast
import csv
import math
import sys
from pathlib import Path

import numpy as np

csv.field_size_limit(sys.maxsize)  # trial_results.csv embeds huge pagerank lists

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from modules.statistical_evaluation.evaluator import (
    StatisticalEvaluationResult, MetricEvaluation, _safe_cohens_d,
)
from modules.statistical_evaluation.vector_comparison import (
    VectorComparisonRegistry,
)
from modules.reporting.trend_analysis import TrendAnalysis
from modules.reporting.sensitivity_analysis import SensitivityAnalysis
from presentation.dataset_exporter import DatasetExporter
from presentation.comparison_exporter import ComparisonExporter

RESULTS = Path("/home/surjit/Desktop/flywire/v1/results")
BANC = RESULTS / "BANC"

MODELS = {
    "missed_synapses":           "Missed Synapses",
    "false_synapses":            "False Synapses",
    "synapse_count_measurement": "Synapse Count Measurement",
}


def parse_rate(folder_name: str) -> float:
    num = folder_name.replace("_percent", "").replace("_", ".")
    return float(num) / 100.0


def load_aggregated(folder: Path) -> dict:
    data = {}
    trial_dirs = sorted(folder.glob("trial_*"))
    all_trials = []
    for t in trial_dirs:
        csv_file = next(t.glob("*/summary.csv"), None)
        if not csv_file:
            continue
        trial = {}
        with open(csv_file, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                trial.setdefault(row["analysis"], {})[row["metric"]] = float(row["mean"])
        all_trials.append(trial)
    if not all_trials:
        return {}
    for a_name in all_trials[0]:
        data[a_name] = {}
        for m_name in all_trials[0][a_name]:
            vals = [t[a_name][m_name] for t in all_trials if a_name in t and m_name in t[a_name]]
            n = len(vals)
            mean = float(np.mean(vals))
            std = float(np.std(vals, ddof=1)) if n > 1 else 0.0
            margin = 1.96 * std / np.sqrt(n) if n > 0 else 0.0
            data[a_name][m_name] = {
                "mean": mean, "std": std, "n": n,
                "ci_lower": mean - margin, "ci_upper": mean + margin,
            }
    return data


# Vector metrics stored in trial_results.csv as literal-list strings, keyed by
# column name "metric_<metric_key>" (e.g. metric_pagerank_scores).
# Only (analysis_name, metric_key) pairs with a registered comparison strategy
# are restored — matches the original Kaggle pipeline exactly.
_VECTOR_STRATEGIES = VectorComparisonRegistry.list_registrations()
#: trial_results.csv column name for each metric key
_VECTOR_COLUMNS = {
    (a_name, m_key): f"metric_{m_key}"
    for a_name, m_key in _VECTOR_STRATEGIES
}


def load_vector_columns(folder: Path) -> dict:
    """Load all registered vector metrics from per-trial trial_results.csv.

    Returns ``{(analysis_name, metric_key): [vector_per_trial, ...]}``.
    """
    collected = {}
    for t in sorted(folder.glob("trial_*")):
        tr = next(t.glob("*/trial_results.csv"), None)
        if not tr:
            continue
        with open(tr, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                a_name = row.get("analysis_name", "")
                for (an, m_key), col in _VECTOR_COLUMNS.items():
                    if a_name != an:
                        continue
                    raw = row.get(col, "")
                    if not raw:
                        continue
                    try:
                        vec = ast.literal_eval(raw)
                        collected.setdefault((an, m_key), []).append(
                            [float(v) for v in vec]
                        )
                    except Exception:
                        continue
    return collected


def vector_derived_stats(folder: Path, avg_baselines: dict) -> dict:
    """Compute derived stats for every registered vector strategy at one rate.

    Mirrors StatisticsEngine.compute_vector_comparisons(): each perturbed
    trial's vector is compared against the average baseline vector using the
    registered comparison strategy.  Returns
    ``{analysis_name: {derived_key: stats_dict}}``.
    """
    vecs_by_key = load_vector_columns(folder)
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
                if v is not None and math.isfinite(v):
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
                "mean": mean, "std": std, "n": n,
                "ci_lower": mean - margin, "ci_upper": mean + margin,
            }
    return out


def build_results(em_dir: Path):
    baseline = load_aggregated(em_dir / "0_percent")

    # Average baseline vectors per registered strategy across 0% trials.
    avg_baselines = {}
    b_vecs_by_key = load_vector_columns(em_dir / "0_percent")
    for key, vectors in b_vecs_by_key.items():
        arr = np.array(vectors)
        avg_baselines[key] = arr.mean(axis=0).tolist()

    results_by_rate = {}
    for folder in sorted(em_dir.glob("*_percent")):
        rate = parse_rate(folder.name)
        rate_data = load_aggregated(folder)
        if not rate_data:
            continue

        # Inject vector-derived metrics (scalar summary.csv drops them).
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
                    bm = None  # vector-derived: null hypothesis (baseline = 0)
                else:
                    bm = baseline.get(a_name, {}).get(m_name)
                if bm:
                    d = _safe_cohens_d(pm["mean"], pm["std"], pm["n"], bm["mean"], bm["std"], bm["n"])
                    b_mean, b_std, b_n = bm["mean"], bm["std"], bm["n"]
                else:
                    d = _safe_cohens_d(pm["mean"], pm["std"], pm["n"], 0.0, 0.0, 1)
                    b_mean, b_std, b_n = 0.0, 0.0, 1
                metrics[a_name][m_name] = MetricEvaluation(
                    metric_name=m_name, baseline_mean=b_mean, baseline_std=b_std,
                    mean=pm["mean"], std=pm["std"], ci_lower=pm["ci_lower"],
                    ci_upper=pm["ci_upper"], effect_size=d,
                )
        n_trials = len(list(folder.glob("trial_*")))
        results_by_rate[rate] = StatisticalEvaluationResult(
            dataset_name="BANC", error_level=rate, n_trials=n_trials,
            runtime_seconds=0.0, metrics=metrics,
        )
    return results_by_rate


def write_dataset_index(dataset_root: Path, models: dict) -> None:
    """Write a minimal dataset-level index.html (results/BANC/index.html).

    The summary pages' breadcrumbs link to ``{root_path}index.html`` where
    ``root_path`` resolves to the *dataset* root, so this file must live at
    ``results/BANC/index.html`` and link to each model's summary plus the
    comparison page.
    """
    model_links = "\n".join(
        f'    <li><a href="{slug}/summary.html">{display}</a></li>'
        for slug, display in models.items()
    )
    html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"/>
<title>BANC — Dataset Index</title>
<style>
  body {{ font-family: sans-serif; background:#0d1117; color:#e6edf3; max-width:900px; margin:0 auto; padding:2rem; }}
  h1 {{ color:#58a6ff; }} a {{ color:#58a6ff; text-decoration:none; }} li {{ margin:0.4rem 0; }}
</style></head>
<body>
<h1>BANC — Dataset Index</h1>
<p>Select an error model to open its scientific report.</p>
<ul>
{model_links}
    <li><a href="comparison/index.html">Error Model Comparison</a></li>
</ul>
</body></html>
"""
    (dataset_root / "index.html").write_text(html, encoding="utf-8")
    print(f"dataset index -> {dataset_root / 'index.html'}")


def main():
    # First pass: full export (single-rate pages, trend analysis, summary).
    exporters = []  # (slug, display, DatasetExporter) — reused for re-render
    for slug, display in MODELS.items():
        em_dir = BANC / slug
        if not em_dir.exists():
            print(f"[{slug}] SKIP — {em_dir} not found")
            continue
        results_by_rate = build_results(em_dir)
        if not results_by_rate:
            print(f"[{slug}] SKIP — no trial data found")
            continue

        trend = TrendAnalysis(
            results_by_rate=results_by_rate,
            dataset_name="BANC",
            error_model_name=slug,
        ).compute()
        sensitivity = SensitivityAnalysis(trend).compute()

        exporter = DatasetExporter(
            output_dir=em_dir,
            results_by_rate=results_by_rate,
            trend=trend,
            sensitivity=sensitivity,
            error_model_slug=slug,
            error_model_display=display,
            dataset_name="BANC",
            results_root=BANC,
        )
        exporter.export()
        exporters.append((slug, display, exporter))
        print(f"[{slug}] exported {len(results_by_rate)} rates -> {em_dir}")

    # Cross-model comparison page (reads existing exported CSVs only).
    ComparisonExporter(
        output_dir=BANC / "comparison",
        dataset_name="BANC",
        results_root=BANC,
        model_slugs=list(MODELS.keys()),
    ).export()

    # Re-render the summaries from in-memory data so has_comparison is True
    # (comparison/index.html did not exist while the model loop ran above).
    for _, _, exporter in exporters:
        exporter.render_summary()

    # Dataset-level index for the summary-page breadcrumbs.
    write_dataset_index(BANC, MODELS)
    print("comparison + dataset index exported")


if __name__ == "__main__":
    main()
