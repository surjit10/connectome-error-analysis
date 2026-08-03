"""
presentation/preservation_config.py
=====================================
Configuration and helper functions for the Biological Preservation Assessment
reporting layer.

All thresholds and metric lists are defined here in a single location so they
can be easily modified without hunting through the codebase.
"""

from __future__ import annotations

import math
from typing import Dict, List, Tuple

# ---------------------------------------------------------------------------
# Metric type classification
# ---------------------------------------------------------------------------
# "preservation" — metrics where preserving the biological quantity matters
# "change"       — metrics that describe structural reorganisation (no preservation)
# "similarity"   — (future) metrics with their own similarity measure, never %
#
# Key format: "analysis_name.metric_name"

METRIC_TYPES: Dict[str, str] = {
    "basic_structure.node_count":        "preservation",
    "basic_structure.edge_count":        "preservation",
    "basic_structure.total_synapses":    "preservation",
    "basic_structure.density":           "preservation",
    "connected_components.wcc_max_size": "preservation",
    "connected_components.scc_max_size": "preservation",
    "reciprocity.reciprocity":           "preservation",
    "connected_components.wcc_count":    "change",
    "connected_components.scc_count":    "change",
}


def get_metric_type(key: str) -> str:
    """Return the metric type: \"preservation\", \"change\", or \"similarity\".

    Falls back to \"preservation\" for unknown metrics (conservative default).
    """
    return METRIC_TYPES.get(key, "similarity")


def is_preservation_metric(key: str) -> bool:
    return get_metric_type(key) == "preservation"


def is_change_metric(key: str) -> bool:
    return get_metric_type(key) == "change"


# ---------------------------------------------------------------------------
# Biological Status thresholds  (preservation metrics only)
# ---------------------------------------------------------------------------

# Each entry: (min_preservation_inclusive, max_preservation_exclusive, label, emoji)
PRESERVATION_THRESHOLDS: List[Tuple[float, float, str, str]] = [
    (99.0, 100.01, "Preserved",              "\U0001f7e2"),  # 🟢  99–100%
    (95.0, 99.0,   "Minor Impact",           "\U0001f7e1"),  # 🟡  95–99%
    (90.0, 95.0,   "Moderate Impact",        "\U0001f7e0"),  # 🟠  90–95%
    (0.0,  90.0,   "Significant Disruption", "\U0001f534"),  # 🔴   0–90%
]

# ---------------------------------------------------------------------------
# Change interpretation thresholds  (change metrics only)
# ---------------------------------------------------------------------------
# Thresholds for interpreting the magnitude of observed change.
# (abs_delta_pct_min_inclusive, abs_delta_pct_max_exclusive, label)

CHANGE_INTERPRETATION_THRESHOLDS: List[Tuple[float, float, str]] = [
    (0.0,  1.0,  "Slight"),
    (1.0,  5.0,  "Minor"),
    (5.0,  10.0, "Moderate"),
    (10.0, 1e9,  "Significant"),
]

# Metric-specific change interpretation templates.
# {metric_key: {direction_prefix: template}}
# Available placeholders: {delta_pct}, {direction_word}

CHANGE_INTERPRETATION_TEMPLATES: Dict[str, Dict[str, str]] = {
    "connected_components.wcc_count": {
        "increase": "{direction_word} increase in disconnected components ({delta_pct})",
        "decrease": "{direction_word} improvement in overall connectivity ({delta_pct})",
    },
    "connected_components.scc_count": {
        "increase": "{direction_word} increase in network fragmentation ({delta_pct})",
        "decrease": "{direction_word} reduction in network fragmentation ({delta_pct})",
    },
}

# Default template when no metric-specific one exists
_DEFAULT_CHANGE_TEMPLATE = "{direction_word} observed change ({delta_pct})"


# ---------------------------------------------------------------------------
# Overall integrity score — key biological metrics averaged
# ---------------------------------------------------------------------------

KEY_INTEGRITY_METRICS: List[str] = [
    "basic_structure.node_count",
    "basic_structure.edge_count",
    "basic_structure.density",
    "connected_components.scc_max_size",
    "reciprocity.reciprocity",
]

# ---------------------------------------------------------------------------
# Invariant metrics — excluded from "Most Stable Metric" selection
# ---------------------------------------------------------------------------
# These metrics cannot change under any of the implemented error models
# (EM1/EM2/EM3 never add or remove neurons), so reporting them as the
# "most stable" metric is not scientifically informative.

INVARIANT_METRICS: List[str] = [
    "basic_structure.node_count",
]


def is_invariant_metric(key: str) -> bool:
    """Return True for metrics that can never change under any error model."""
    return key in INVARIANT_METRICS

# ---------------------------------------------------------------------------
# Integrity thresholds for the overall verdict
# ---------------------------------------------------------------------------

INTEGRITY_THRESHOLDS: List[Tuple[float, float, str, str]] = [
    (99.0, 100.01, "Biologically Preserved",           "\U0001f7e2"),  # 🟢
    (95.0, 99.0,   "Minor Biological Impact",           "\U0001f7e1"),  # 🟡
    (90.0, 95.0,   "Moderate Biological Disruption",    "\U0001f7e0"),  # 🟠
    (0.0,  90.0,   "Significant Biological Disruption", "\U0001f534"),  # 🔴
]

# ---------------------------------------------------------------------------
# Metrics where lower is better (perturbed < baseline is good)
# ---------------------------------------------------------------------------

LOWER_IS_BETTER_METRICS: List[str] = [
    # Example: "error_rates.mse",
    # Currently all preservation metrics are higher-is-better.
]


# ---------------------------------------------------------------------------
# Metric name display helpers
# ---------------------------------------------------------------------------

METRIC_DISPLAY_NAMES: Dict[str, str] = {
    "basic_structure.node_count":        "Node Count",
    "basic_structure.edge_count":        "Edge Count",
    "basic_structure.total_synapses":    "Total Synapses",
    "basic_structure.density":           "Density",
    "connected_components.wcc_count":    "WCC Count",
    "connected_components.wcc_max_size": "Largest WCC",
    "connected_components.scc_count":    "SCC Count",
    "connected_components.scc_max_size": "Largest SCC",
    "reciprocity.reciprocity":           "Reciprocity",
}


# ===================================================================
# Helper functions
# ===================================================================


# -- Basic helpers ----------------------------------------------------------

def higher_is_better(key: str) -> bool:
    """Return False if the metric key is in the lower-is-better list."""
    return key not in LOWER_IS_BETTER_METRICS


def _isfinite(x: float) -> bool:
    return math.isfinite(x)


def _label_to_css(label: str) -> str:
    """Convert a human-readable label to a lowercase CSS class name."""
    return label.lower().replace(" ", "-")


# -- Preservation calculation -----------------------------------------------

def calculate_preservation(
    baseline: float,
    perturbed: float,
    higher_is_better: bool = True,
) -> float:
    """Compute symmetric preservation percentage between baseline and perturbed.

    Deviation in **either** direction reduces preservation.  For metrics
    where **higher is better** (e.g. node count, edge count, SCC size):

        preservation = min(perturbed/baseline, baseline/perturbed) × 100

    A metric that increased by 20% (ratio 1.2) therefore reports
    ``1/1.2 ≈ 83.3%`` preserved instead of being clamped to 100%.  This is
    essential for **additive** error models (e.g. false synapses, which add
    edges): without it, every preservation metric moves *above* baseline and
    the old ``min(pct, 100.0)`` clamp reports a misleading green "100%".

    For metrics where **lower is better** (e.g. error rate, MSE) the good
    direction is reversed: an improvement (perturbed < baseline) stays at
    100%, while a worsening is penalised by the same ratio.

    Args:
        baseline:        Value at 0% error rate.
        perturbed:       Value at the perturbed error rate.
        higher_is_better:
            ``True`` (default) for metrics where larger values indicate
            better biological preservation.

    Returns:
        Preservation percentage in [0, 100].
    """
    if not _isfinite(baseline) or not _isfinite(perturbed):
        return 0.0

    if baseline == 0.0:
        return 100.0 if perturbed == 0.0 else 0.0

    if higher_is_better:
        ratio = perturbed / baseline
        # Symmetric: an increase is as much a deviation as a decrease.
        if ratio > 1.0:
            ratio = 1.0 / ratio
    else:
        ratio = baseline / perturbed
        # Lower-is-better: improvement → 100%, worsening → ratio (< 1).
        ratio = min(ratio, 1.0)

    return ratio * 100.0


# -- Status / verdict helpers -----------------------------------------------

def get_biological_status(preservation: float) -> Tuple[str, str, str]:
    """Return (emoji, label, css_class) for a preservation percentage."""
    for lo, hi, label, emoji in PRESERVATION_THRESHOLDS:
        if lo <= preservation < hi:
            css = _label_to_css(label)
            return emoji, label, css
    return "\U0001f534", "Significant Disruption", "disruption"


def get_integrity_verdict(integrity_score: float) -> Tuple[str, str, str]:
    """Return (emoji, verdict_text, css_class) for an overall integrity score."""
    for lo, hi, label, emoji in INTEGRITY_THRESHOLDS:
        if lo <= integrity_score < hi:
            css = _label_to_css(label)
            return emoji, label, css
    return "\U0001f534", "Significant Biological Disruption", "disruption"


# -- Change interpretation --------------------------------------------------

def get_change_interpretation(
    metric_key: str,
    delta_pct: float,
    is_increase: bool,
) -> str:
    """Generate a human-readable interpretation for a change metric.

    Args:
        metric_key: Full metric key (e.g. ``\"connected_components.wcc_count\"``).
        delta_pct:  Raw percent change value (positive for increase).
        is_increase: ``True`` if the metric increased (perturbed > baseline).

    Returns:
        A short interpretation string (e.g. ``\"Minor increase in fragmentation\"``).
    """
    abs_delta = abs(delta_pct)

    # Determine magnitude label
    magnitude = "Observed"
    for lo, hi, label in CHANGE_INTERPRETATION_THRESHOLDS:
        if lo <= abs_delta < hi:
            magnitude = label
            break

    # Build direction word
    direction_word = "increase" if is_increase else "decrease"
    delta_str = format_change(delta_pct)

    # Look up metric-specific template
    metric_templates = CHANGE_INTERPRETATION_TEMPLATES.get(metric_key, {})
    direction_key = "increase" if is_increase else "decrease"
    template = metric_templates.get(direction_key, _DEFAULT_CHANGE_TEMPLATE)

    return template.format(
        delta_pct=delta_str,
        direction_word=magnitude,
    )


# -- Biological assessment --------------------------------------------------

def generate_biological_assessment(
    integrity_score: float,
    metrics_preservation: Dict[str, float],
) -> str:
    """Generate a short, data-consistent assessment paragraph.

    Every sentence is derived from the per-metric preservation values that
    are actually present in the report, so the narrative always agrees with
    the tables shown below it.  The ``integrity_score`` argument is retained
    only for backward compatibility and is not used to fabricate statements
    that contradict the metric-level data.

    Args:
        integrity_score:  Average preservation across key metrics (unused in
                          the text; kept for API compatibility).
        metrics_preservation:
            ``{full_metric_key: preservation_pct}`` for all available metrics.

    Returns:
        A natural-language string summarising the biological state.
    """
    if not metrics_preservation:
        return "Per-metric preservation scores are reported in the tables below."

    parts: List[str] = []

    def _avg(keys: Tuple[str, ...]) -> float:
        vals = [metrics_preservation[k] for k in keys if k in metrics_preservation]
        return sum(vals) / len(vals) if vals else 100.0

    # Category-level aggregation from the metric values actually reported
    topo = _avg(("basic_structure.node_count", "basic_structure.edge_count", "basic_structure.density"))
    syn  = _avg(("basic_structure.total_synapses", "basic_structure.weight_mean",
                 "basic_structure.weight_median", "basic_structure.weight_variance",
                 "basic_structure.weight_std", "basic_structure.weight_max",
                 "basic_structure.weight_min"))
    conn = _avg(("connected_components.scc_max_size", "connected_components.wcc_max_size"))
    org  = _avg(("reciprocity.reciprocity", "assortativity.degree_assortativity"))

    if topo >= 99.0:
        parts.append("Global network topology remains preserved.")
    elif topo < 95.0:
        parts.append("Global network topology shows measurable structural changes.")

    if syn >= 99.0:
        parts.append("Synapse-related properties remain preserved.")
    elif syn >= 95.0:
        parts.append("Synapse-related properties show minor changes.")
    elif syn < 90.0:
        parts.append("Synapse-related properties exhibit significant degradation.")
    else:
        parts.append("Synapse-related properties exhibit measurable degradation.")

    if conn >= 99.0:
        parts.append("Large-scale connectivity remains stable.")
    elif conn < 95.0:
        parts.append("Large-scale connectivity is measurably affected.")

    if org >= 99.0:
        parts.append("Network organisation is preserved.")
    elif org < 95.0:
        parts.append("Network organisation shows measurable changes.")

    if not parts:
        parts.append("Per-metric preservation scores are reported in the tables below.")

    return " ".join(parts)


# ===================================================================
# Render helpers  (return dicts ready for template consumption)
# ===================================================================


def render_preservation_metric(
    key: str,
    analysis: str,
    metric: str,
    baseline_mean: float,
    perturbed_mean: float,
    std: float,
    ci_lower: float,
    ci_upper: float,
) -> Dict:
    """Build a row dict for a **preservation** metric with progress bar + badge.

    Returns a dict ready for the HTML template, including preservation %,
    biological status, emoji, and CSS class.
    """
    display_name = METRIC_DISPLAY_NAMES.get(key, metric)

    # Compute percent change
    delta_pct, delta_sign = _pct_change(perturbed_mean, baseline_mean)

    # Compute preservation
    preservation = calculate_preservation(
        baseline_mean, perturbed_mean,
        higher_is_better=higher_is_better(key),
    )
    emoji, bio_label, bio_css = get_biological_status(preservation)

    return {
        "metric_type":       "preservation",
        "analysis":          analysis,
        "metric":            metric,
        "display_name":      display_name,
        "baseline_mean":     _fmt(baseline_mean),
        "mean":              _fmt(perturbed_mean),
        "std":               _fmt(std),
        "ci_lower":          _fmt(ci_lower),
        "ci_upper":          _fmt(ci_upper),
        "delta_pct":         delta_pct,
        "delta_sign":        delta_sign,
        "preservation":      format_percentage(preservation),
        "preservation_num":  round(preservation, 4),
        "pres_tier_str":     pres_tier(preservation),
        "bio_status":        bio_label,
        "bio_emoji":         emoji,
        "bio_css":           bio_css,
    }


def render_change_metric(
    key: str,
    analysis: str,
    metric: str,
    baseline_mean: float,
    perturbed_mean: float,
    std: float,
    ci_lower: float,
    ci_upper: float,
) -> Dict:
    """Build a row dict for a **change** metric with interpretation, no preservation.

    Returns a dict ready for the HTML template, with an ``interpretation`` field
    instead of preservation / bio_status / bio_emoji / bio_css.
    """
    display_name = METRIC_DISPLAY_NAMES.get(key, metric)

    delta_pct, delta_sign = _pct_change(perturbed_mean, baseline_mean)

    # Parse numeric delta for interpretation
    try:
        raw_delta = (perturbed_mean - baseline_mean) / abs(baseline_mean) * 100 \
            if baseline_mean != 0 and math.isfinite(baseline_mean) and math.isfinite(perturbed_mean) else 0.0
    except (ZeroDivisionError, ValueError):
        raw_delta = 0.0
    is_increase = raw_delta > 0

    interpretation = get_change_interpretation(key, raw_delta, is_increase)

    return {
        "metric_type":     "change",
        "analysis":        analysis,
        "metric":          metric,
        "display_name":    display_name,
        "baseline_mean":   _fmt(baseline_mean),
        "mean":            _fmt(perturbed_mean),
        "std":             _fmt(std),
        "ci_lower":        _fmt(ci_lower),
        "ci_upper":        _fmt(ci_upper),
        "delta_pct":       delta_pct,
        "delta_sign":      delta_sign,
        "interpretation":  interpretation,
        # Still pass preservation fields (will be ignored in template)
        "preservation":    "—",
        "bio_status":      "",
        "bio_emoji":       "",
        "bio_css":         "",
    }


# ---------------------------------------------------------------------------
# Internal helpers used by render_* functions
# ---------------------------------------------------------------------------


def format_percentage(value: float, decimals: int = 4) -> str:
    """Format a preservation percentage with the given number of decimal places.

    Metric-level percentages default to **4 decimal places** to avoid hiding
    very small structural changes after rounding.

    The overall Network Integrity Score uses ``format_integrity()`` (2 decimals)
    instead.
    """
    return f"{value:.{decimals}f}"


def format_change(delta_pct: float, decimals: int = 4) -> str:
    """Format a percent-change value (Δ%) with sign and the given precision.

    Metric-level changes default to **4 decimal places** so that tiny but real
    changes (e.g. ``-0.0032%%``) are never hidden by rounding to ``-0.00%%``.
    """
    if not math.isfinite(delta_pct):
        return "\u2014"
    sign = "+" if delta_pct >= 0 else ""
    return f"{sign}{delta_pct:.{decimals}f}%"


def format_integrity(value: float) -> str:
    """Format the overall Biological Preservation Score (always 2 decimal places).

    This summary value is kept concise for quick readability.
    """
    return f"{value:.2f}"


def _pct_change(mean: float, baseline: float, decimals: int = 4) -> Tuple[str, str]:
    """Return (formatted_pct_string, sign_char) with the given precision."""
    if baseline == 0 or not math.isfinite(baseline) or not math.isfinite(mean):
        return "\u2014", "="
    delta = (mean - baseline) / abs(baseline) * 100
    sign  = "+" if delta >= 0 else ""
    return format_change(delta, decimals), ("+" if delta >= 0 else "-")


def _fmt(value: float) -> str:
    """Format a float for display, keeping reasonable precision."""
    if not math.isfinite(value):
        return "\u2014"
    return f"{value:.6g}"


# ===================================================================
# Display-only colour tier helper (used in templates, not in CSS/gen)
# ===================================================================

# ===================================================================
# Scientific-report display groupings  (presentation only)
# -------------------------------------------------------------------
# These maps reorganise how existing metrics are *displayed* on the
# scientific report pages.  They do NOT affect METRIC_TYPES, the CSV/JSON
# exports, or any statistical computation.
# ===================================================================

# ---------------------------------------------------------------------------
# Structural metric categories — used to group the Structural Preservation
# Analysis table into biologically meaningful families.
# ---------------------------------------------------------------------------

METRIC_CATEGORIES: Dict[str, List[str]] = {
    "Topology": [
        "basic_structure.node_count",
        "basic_structure.edge_count",
        "basic_structure.density",
    ],
    "Synaptic Properties": [
        "basic_structure.total_synapses",
        "basic_structure.weight_mean",
        "basic_structure.weight_median",
        "basic_structure.weight_variance",
        "basic_structure.weight_std",
        "basic_structure.weight_max",
        "basic_structure.weight_min",
    ],
    "Connectivity": [
        "connected_components.wcc_max_size",
        "connected_components.scc_max_size",
        "connected_components.wcc_count",
        "connected_components.scc_count",
    ],
    "Network Organization": [
        "reciprocity.reciprocity",
        "assortativity.degree_assortativity",
    ],
}

# ---------------------------------------------------------------------------
# Network similarity metrics (derived from vector comparisons)
# ---------------------------------------------------------------------------
# These are the *derived* scalar summaries of vector comparisons — the raw
# per-node vectors are never displayed.  Keys are ``analysis.metric``.

SIMILARITY_METRICS: Dict[str, str] = {
    "pagerank.pagerank_scores_pearson":       "PageRank Pearson Correlation",
    "pagerank.pagerank_scores_spearman":      "PageRank Spearman Correlation",
    "pagerank.pagerank_scores_topk_overlap":  "PageRank Top-K Overlap",
    "degree_distribution.in_degrees_ks":       "In-Degree KS Statistic",
    "degree_distribution.in_degrees_wasserstein": "In-Degree Wasserstein Distance",
    "degree_distribution.in_degrees_mean_baseline":  "In-Degree Mean (Baseline)",
    "degree_distribution.in_degrees_mean_perturbed": "In-Degree Mean (Perturbed)",
    "degree_distribution.in_degrees_var_baseline":   "In-Degree Variance (Baseline)",
    "degree_distribution.in_degrees_var_perturbed":  "In-Degree Variance (Perturbed)",
    "degree_distribution.out_degrees_ks":      "Out-Degree KS Statistic",
    "degree_distribution.out_degrees_wasserstein": "Out-Degree Wasserstein Distance",
    "degree_distribution.out_degrees_mean_baseline":  "Out-Degree Mean (Baseline)",
    "degree_distribution.out_degrees_mean_perturbed": "Out-Degree Mean (Perturbed)",
    "degree_distribution.out_degrees_var_baseline":   "Out-Degree Variance (Baseline)",
    "degree_distribution.out_degrees_var_perturbed":  "Out-Degree Variance (Perturbed)",
}


# ---------------------------------------------------------------------------
# Error model explanatory summaries  (presentation text only)
# ---------------------------------------------------------------------------

ERROR_MODEL_SUMMARIES: Dict[str, Dict[str, str]] = {
    "missed_synapses": {
        "display_name": "Missed Synapses",
        "biological_effect":
            "Removes existing synaptic connections (false negatives).",
        "expected_structural_effect":
            "Edge count ↓ · Total synapses ↓ · Connectivity largely preserved.",
        "expected_analysis_effect":
            "Weighted metrics (total synapses, PageRank) decline while purely "
            "topological metrics remain largely stable.",
    },
    "false_synapses": {
        "display_name": "False Synapses",
        "biological_effect":
            "Introduces artificial synaptic connections (false positives).",
        "expected_structural_effect":
            "Edge count ↑ · Density ↑ · Reciprocity changes.",
        "expected_analysis_effect":
            "Structural metrics move above baseline; the preservation score "
            "penalises deviation in either direction.",
    },
    "synapse_count_measurement": {
        "display_name": "Synapse Count Measurement",
        "biological_effect":
            "Perturbs synapse-count estimates only (Gaussian measurement noise).",
        "expected_structural_effect":
            "Topology unchanged.",
        "expected_analysis_effect":
            "Weighted metrics (total synapses, weighted PageRank) vary while "
            "topological metrics act as control variables.",
    },
}


def error_model_summary(slug: str) -> Dict[str, str]:
    """Return the explanatory summary dict for an error model slug."""
    return ERROR_MODEL_SUMMARIES.get(slug, {
        "display_name": slug.replace("_", " ").title(),
        "biological_effect": "Simulates a biological reconstruction error.",
        "expected_structural_effect": "See per-metric results.",
        "expected_analysis_effect": "See per-metric results.",
    })


def pres_tier(value: float) -> str:
    """Map a preservation percentage to a UI colour tier (display only).

    Finer visual granularity than the biological status classes so that
    e.g. 99.3%% vs 99.9%% are distinguishable.  Classification thresholds
    used for the biological status labels are untouched.

    Scale:  >=99 dark-green · 97–99 light-green · 95–97 yellow ·
            90–95 orange · <90 red

    This is a plain Python function (not a Jinja2 filter) so it works
    across ``extends``-based templates without version-dependent filter
    scoping issues.  Call it from Python context builders and pass the
    result as a template variable.
    """
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "dark-green"
    if v >= 99.0:
        return "dark-green"
    if v >= 97.0:
        return "light-green"
    if v >= 95.0:
        return "yellow"
    if v >= 90.0:
        return "orange"
    return "red"
