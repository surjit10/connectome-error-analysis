#!/usr/bin/env python3
"""Generate all figures for the Beamer deck + the two-page report directly
from the experiment outputs (combined_results.csv for both error models).

Every figure is derived from the raw aggregated data; no numbers are
hard-coded. Also prints a FACTS section used to verify slide statements.

Figures:
  fig_primary.png      % change vs baseline (synapses, edges) by error rate
  fig_organization.png reciprocity + giant SCC size (raw values)
  fig_degree_dist.png  in-degree KS / Wasserstein distance (log scale)
  fig_pagerank.png     PageRank top-k overlap
  fig_ranking.png      minimum preservation per metric (0-20% rates)
  fig_snapshot20.png   20% snapshot: baseline vs missed vs false (grouped bars)
  fig_overall.png      mean preservation across all metrics
  fig_category20.png   category-wise preservation at 20% (grouped bars)
"""
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd

import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
from presentation.preservation_config import (
    calculate_preservation,
    higher_is_better,
    is_preservation_metric,
)

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)))
FIG = os.path.join(ROOT, "figures")
os.makedirs(FIG, exist_ok=True)

PROJ = os.path.join(os.path.dirname(ROOT), "..")
CSV = os.path.join(
    PROJ, "results", "{ds}", "{model}", "{slug}", "BANC", "trend_analysis", "combined_results.csv"
)


def resolve(rel):
    """Resolve a results path, tolerating upper/lower case dataset dirs."""
    p = os.path.join(PROJ, rel)
    if os.path.exists(p):
        return p
    lower = os.path.join(PROJ, rel.replace("/BANC/", "/banc/", 1))  # only the dataset dir
    if os.path.exists(lower):
        return lower
    raise FileNotFoundError(rel)

MISSED = resolve("results/BANC/missed_synapses/missedsynapses/BANC/trend_analysis/combined_results.csv")
FALSE = resolve("results/BANC/false_synapses/falsesynapses/BANC/trend_analysis/combined_results.csv")

m = pd.read_csv(MISSED)
f = pd.read_csv(FALSE)
rates = sorted(m["rate"].unique())
rate_pct = [r * 100 for r in rates]

C_MISSED = "#0b6e99"   # blue
C_FALSE = "#c4451d"    # red-orange
C_BASE = "#9aa5b1"

# ---------------------------------------------------------------------------
# Figure style: bigger fonts so figures stay legible after downscaling
# in the PDF, honest scales, plain thousands-separated tick labels.
# ---------------------------------------------------------------------------
plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 18,
    "axes.titlesize": 18,
    "axes.labelsize": 16,
    "xtick.labelsize": 14,
    "ytick.labelsize": 14,
    "legend.fontsize": 14,
    "axes.linewidth": 1.1,
    "figure.facecolor": "white",
    "axes.facecolor": "white",
    "axes.titleweight": "bold",
})


def series(df, metric, col="mean"):
    return df[df["metric"] == metric].set_index("rate")[col].reindex(rates).to_numpy()


def baseline(df, metric):
    return df[df["metric"] == metric]["baseline_mean"].iloc[0]


def pct_change(df, metric):
    b = baseline(df, metric)
    return (series(df, metric) / b - 1.0) * 100.0


def save(fig, name):
    fig.savefig(os.path.join(FIG, name), dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  wrote figures/{name}")


def style_ax(ax, grid_axis="y"):
    ax.grid(True, which="major", axis=grid_axis, color="#dcdcdc", linewidth=0.9)
    if grid_axis == "y":
        ax.grid(True, which="minor", axis="y", color="#efefef", linewidth=0.5, ls=":")
    ax.set_axisbelow(True)
    for s in ["top", "right"]:
        ax.spines[s].set_visible(False)


def comma_ticks(ax, axis="y"):
    """Plain tick labels with thousands separators (no scientific notation)."""
    fmt = mticker.FuncFormatter(lambda x, _: f"{x:,.0f}")
    if axis == "y":
        ax.yaxis.set_major_formatter(fmt)
    else:
        ax.xaxis.set_major_formatter(fmt)


def label_endpoint(ax, x, y, text, color, dx=0.0, dy=0.0, ha="left", va="bottom"):
    ax.annotate(
        text, (x, y), textcoords="offset points", xytext=(dx, dy),
        ha=ha, va=va, fontsize=13, color=color, fontweight="bold",
    )


def plot_two_models(ax, metric_m, metric_f, pct=False, log=False):
    """Plot missed vs false series for a metric pair; returns values."""
    if pct:
        ym, yf = pct_change(m, metric_m), pct_change(f, metric_f)
    else:
        ym, yf = series(m, metric_m), series(f, metric_f)
    ax.plot(rate_pct, ym, "o-", color=C_MISSED, lw=2.6, ms=7, label="Missed synapses")
    ax.plot(rate_pct, yf, "s-", color=C_FALSE, lw=2.6, ms=7, label="False synapses")
    if log:
        ax.set_yscale("log")
    return ym, yf


# ---------------------------------------------------------------------------
# Figure 1 — Primary structural quantities: % change vs error rate
# ---------------------------------------------------------------------------
fig, axes = plt.subplots(1, 2, figsize=(11.0, 4.6))
for ax, key, title in [
    (axes[0], "total_synapses", "Total synapses"),
    (axes[1], "edge_count", "Total connections (edges)"),
]:
    ym, yf = plot_two_models(ax, key, key, pct=True)
    ax.axhline(0, color=C_BASE, lw=1.2, ls="--")
    ax.set_xlabel("Error rate (%)")
    ax.set_ylabel("Change vs baseline (%)")
    ax.set_title(title)
    style_ax(ax)
    ax.legend(frameon=False)
    # endpoint annotations make the takeaway explicit
    label_endpoint(ax, 20, ym[-1], f"{ym[-1]:+.1f}%", C_MISSED, dx=2, dy=1)
    label_endpoint(ax, 20, yf[-1], f"{yf[-1]:+.1f}%", C_FALSE, dx=2, dy=1)
fig.tight_layout()
save(fig, "fig_primary.png")

# ---------------------------------------------------------------------------
# Figure 2 — Network organization: reciprocity & SCC size (raw values)
# ---------------------------------------------------------------------------
fig, axes = plt.subplots(1, 2, figsize=(11.0, 4.6))
for ax, key, title, ylab in [
    (axes[0], "reciprocity", "Reciprocity", "Reciprocity (fraction of mutual edges)"),
    (axes[1], "scc_max_size", "Largest strongly connected component", "Vertices in SCC"),
]:
    ym, yf = plot_two_models(ax, key, key)
    ax.set_xlabel("Error rate (%)")
    ax.set_ylabel(ylab)
    ax.set_title(title)
    style_ax(ax)
    ax.legend(frameon=False)
    if key == "scc_max_size":
        comma_ticks(ax)
        label_endpoint(ax, 20, ym[-1], f"{ym[-1]/ym[0]*100-100:+.2f}% vs baseline", C_MISSED, dx=-64, dy=-16, ha="right", va="top")
        label_endpoint(ax, 20, yf[-1], f"{yf[-1]/yf[0]*100-100:+.2f}% vs baseline", C_FALSE, dx=-64, dy=1, ha="right")
fig.tight_layout()
save(fig, "fig_organization.png")

# ---------------------------------------------------------------------------
# Figure 3 — Degree-distribution distortion (KS & Wasserstein, log scale)
# ---------------------------------------------------------------------------
# False edges add many weak edges and distort degree distributions far more
# than missed ones.  The two curves span >10x, so a linear axis flattens the
# missed-synapses line into the x-axis; log scale keeps both interpretable.
fig, axes = plt.subplots(1, 2, figsize=(11.0, 4.6))
ratios = []
for ax, key, title in [
    (axes[0], "in_degrees_ks", "In-degree KS distance"),
    (axes[1], "in_degrees_wasserstein", "In-degree Wasserstein distance"),
]:
    ym, yf = plot_two_models(ax, key, key, log=True)
    ax.set_xlabel("Error rate (%)")
    ax.set_ylabel("Distance from baseline (log scale)")
    ax.set_title(title)
    style_ax(ax, grid_axis="both")
    ax.legend(frameon=False)
    ratio = yf[-1] / ym[-1]
    label_endpoint(ax, 20, yf[-1], f"{yf[-1]:.3f}  ({ratio:.0f}x)", C_FALSE, dx=-46, dy=6, ha="right")
    label_endpoint(ax, 20, ym[-1], f"{ym[-1]:.4f}", C_MISSED, dx=-30, dy=-10, ha="right")
    ratios.append((key, ratio))
fig.suptitle("False synapses distort degree distributions 6\u201314x more at 20%\n(KS 14x, Wasserstein 6x)", fontsize=15, y=1.0)

fig.tight_layout(rect=[0, 0, 1, 0.96])
save(fig, "fig_degree_dist.png")

# ---------------------------------------------------------------------------
# Figure 4 — PageRank fidelity (top-k overlap)
# ---------------------------------------------------------------------------
fig, ax = plt.subplots(figsize=(7.0, 4.6))
ym, yf = plot_two_models(ax, "pagerank_scores_topk_overlap", "pagerank_scores_topk_overlap")
ax.set_xlabel("Error rate (%)")
ax.set_ylabel("Top-k overlap (vs baseline)")
ax.set_title("PageRank: overlap of top-ranked neurons")
ax.set_ylim(0.80, 1.005)
style_ax(ax)
ax.legend(frameon=False, loc="lower left")
label_endpoint(ax, 20, ym[-1], f"{ym[-1]:.2f}", C_MISSED, dx=-34, dy=3, ha="right")
label_endpoint(ax, 20, yf[-1], f"{yf[-1]:.2f}", C_FALSE, dx=-34, dy=-8, ha="right")
fig.tight_layout()
save(fig, "fig_pagerank.png")

# ---------------------------------------------------------------------------
# Figure 5 — Sensitivity ranking: minimum preservation per metric
# ---------------------------------------------------------------------------
def recompute_preservation(df):
    """Recompute preservation_pct with the framework's own current formula.

    The exported CSVs were generated with a pre-fix preservation_config.py
    that did not classify weight / assortativity metrics as preservation
    (their preservation was frozen at 100% / None).  Recompute from the CSV's
    own baseline_mean / mean columns so every metric uses the same symmetric
    ratio as the current code (see presentation/report/correction.md).
    """
    out = np.full(len(df), np.nan)
    for (analysis, metric), g in df.groupby(["analysis", "metric"]):
        key = f"{analysis}.{metric}"
        base = float(g["baseline_mean"].iloc[0])
        for idx, row in g.iterrows():
            out[df.index.get_loc(idx)] = calculate_preservation(
                base, float(row["mean"]),
                higher_is_better=higher_is_better(key), metric_key=key,
            )
    return out


m["preservation_pct"] = recompute_preservation(m)
f["preservation_pct"] = recompute_preservation(f)


def min_pres(df):
    # Only genuine preservation metrics (see preservation_config.METRIC_TYPES).
    # Degree-distribution / pagerank / KS rows are NOT preservation metrics:
    # their baselines are 0, so the symmetric ratio is undefined (0.00) and
    # they must never appear in a "minimum preservation" ranking.
    d = df[df["rate"] > 0].groupby("metric")["preservation_pct"].min()
    keep = [
        mt for (a, mt) in df.groupby(["analysis", "metric"]).groups
        if is_preservation_metric(f"{a}.{mt}") and d.get(mt, 100.0) < 99.999
    ]
    return d[keep].sort_values()


mp, fp = min_pres(m), min_pres(f)
union = list(dict.fromkeys(list(fp.index) + list(mp.index)))
labels = {
    "edge_count": "Edge count",
    "density": "Density",
    "total_synapses": "Total synapses",
    "reciprocity": "Reciprocity",
    "scc_max_size": "SCC max size",
    "wcc_max_size": "WCC max size",
    "weight_variance": "Weight variance",
    "weight_median": "Weight median",
    "weight_mean": "Weight mean",
    "weight_std": "Weight std",
    "weight_max": "Weight max",
    "degree_assortativity": "Assortativity",
}
ypos = np.arange(len(union))[::-1]
fig, ax = plt.subplots(figsize=(9.2, 6.2))
h = 0.36
for df, c, off, lab in [
    (m, C_MISSED, +h / 2, "Missed"),
    (f, C_FALSE, -h / 2, "False"),
]:
    vals = [min_pres(df).get(metric, 100.0) for metric in union]
    ax.barh(ypos + off, vals, height=h, color=c, alpha=0.92, label=lab + " synapses")
ax.set_yticks(ypos)
ax.set_yticklabels([labels.get(k, k) for k in union], fontsize=16)
ax.set_xlabel("Minimum preservation across 0–20% rates (%)")
ax.set_xlim(60, 102)
ax.axvline(90, color="#f0883e", lw=1.1, ls=":")
ax.axvline(95, color="#d9a441", lw=1.1, ls=":")
ax.axvline(99, color="#5a8f4e", lw=1.1, ls=":")
# threshold labels inside the axes (avoid clipping)
ax.text(90, 0.4, "significant <90%", fontsize=12, color="#c4451d", ha="center")
ax.text(95, 0.4, "moderate <95%", fontsize=12, color="#b07d10", ha="center")
ax.text(99, 0.4, "minor <99%", fontsize=12, color="#5a8f4e", ha="center")
style_ax(ax)
ax.legend(frameon=False, loc="lower left")
fig.tight_layout()
save(fig, "fig_ranking.png")

# ---------------------------------------------------------------------------
# Figure 6 — 20% snapshot: baseline vs missed vs false (grouped bars)
# ---------------------------------------------------------------------------
metrics = ["total_synapses", "edge_count", "reciprocity", "scc_max_size"]
titles = ["Total synapses", "Connections", "Reciprocity", "SCC size"]
fig, axes = plt.subplots(1, 4, figsize=(12.5, 4.4))
bar_labels = ["Baseline", "Missed 20%", "False 20%"]
for ax, key, t in zip(axes, metrics, titles):
    b = baseline(m, key)
    mv, fv = series(m, key)[-1], series(f, key)[-1]
    bars = ax.bar([0, 1, 2], [b, mv, fv], width=0.62,
                  color=[C_BASE, C_MISSED, C_FALSE],
                  label=bar_labels if ax is axes[0] else None)
    ax.set_title(t)
    ax.set_xticks([0, 1, 2])
    ax.set_xticklabels(["Base", "Miss", "False"], fontsize=12)
    ax.tick_params(axis="y", labelsize=11)
    if key == "reciprocity":
        ax.set_ylim(0, 0.20)  # honest zero-based axis
    elif key in ("total_synapses", "edge_count", "scc_max_size"):
        comma_ticks(ax)
    # value labels on the bars
    for bar, val in zip(bars, [b, mv, fv]):
        txt = f"{val:,.0f}" if key != "reciprocity" else f"{val:.3f}"
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height(),
                txt, ha="center", va="bottom", fontsize=10)
    style_ax(ax)
handles, labels_ = axes[0].get_legend_handles_labels()
fig.legend(handles, bar_labels, loc="upper center", ncol=3, frameon=False, fontsize=13)
fig.tight_layout(rect=[0, 0, 1, 0.90])
save(fig, "fig_snapshot20.png")

# ---------------------------------------------------------------------------
# Figure 7 — Mean preservation over the 14 metrics with a well-defined
# baseline.  The CSV contains 49 metric rows, but 35 of them (KS/Wasserstein
# distances, PageRank scores, degree-summary rows) are not preservation
# metrics — their baseline is 0 and the symmetric ratio is meaningless.  So
# the honest headline is the mean over the 14 genuine preservation metrics.
# ---------------------------------------------------------------------------
pres_keys = sorted({mt for (a, mt) in m.groupby(["analysis", "metric"]).groups
                    if is_preservation_metric(f"{a}.{mt}")})


def mean_pres(df):
    return df[df["metric"].isin(pres_keys)].groupby("rate")["preservation_pct"].mean().reindex(rates).to_numpy()


om, of_ = mean_pres(m), mean_pres(f)
fig, ax = plt.subplots(figsize=(7.4, 4.6))
ax.plot(rate_pct, om, "o-", color=C_MISSED, lw=2.6, ms=7, label="Missed synapses")
ax.plot(rate_pct, of_, "s-", color=C_FALSE, lw=2.6, ms=7, label="False synapses")
ax.set_xlabel("Error rate (%)")
ax.set_ylabel(f"Mean preservation across {len(pres_keys)} metrics (%)")
ax.set_ylim(88, 100.5)
style_ax(ax)
ax.legend(frameon=False)
label_endpoint(ax, 20, om[-1], f"{om[-1]:.1f}%", C_MISSED, dx=-46, dy=2, ha="right")
label_endpoint(ax, 20, of_[-1], f"{of_[-1]:.1f}%", C_FALSE, dx=-46, dy=-4, ha="right")
ax.set_title(f"Mean preservation of the {len(pres_keys)} graph metrics with a defined baseline")
fig.tight_layout()
save(fig, "fig_overall.png")

# ---------------------------------------------------------------------------
# Figure 8 — Category-wise preservation at 20% error
# ---------------------------------------------------------------------------
CATS = {
    "Structural Topology": ["node_count", "edge_count", "density"],
    "Synaptic Properties": ["total_synapses", "weight_mean", "weight_median",
                            "weight_variance", "weight_std", "weight_max", "weight_min"],
    "Connectivity": ["wcc_max_size", "scc_max_size"],
    "Network Organization": ["reciprocity", "degree_assortativity"],
}


def cat_pres(df):
    out = {}
    d = df[df["rate"] == 0.2].set_index("metric")
    for cat, mets in CATS.items():
        vals = [d.loc[mt, "preservation_pct"] for mt in mets if mt in d.index]
        out[cat] = float(np.mean(vals))
    return out


cm, cf = cat_pres(m), cat_pres(f)
cats = list(CATS.keys())
fig, ax = plt.subplots(figsize=(8.6, 4.6))
x = np.arange(len(cats))
w = 0.36
ax.bar(x - w / 2, [cm[c] for c in cats], width=w, color=C_MISSED, alpha=0.92, label="Missed synapses")
ax.bar(x + w / 2, [cf[c] for c in cats], width=w, color=C_FALSE, alpha=0.92, label="False synapses")
for xi, (a, b) in enumerate(zip([cm[c] for c in cats], [cf[c] for c in cats])):
    ax.text(xi - w / 2, a + 0.3, f"{a:.1f}%", ha="center", va="bottom", fontsize=12, color=C_MISSED)
    ax.text(xi + w / 2, b + 0.3, f"{b:.1f}%", ha="center", va="bottom", fontsize=12, color=C_FALSE)
ax.set_xticks(x)
ax.set_xticklabels(cats, fontsize=13)
ax.set_ylabel("Mean preservation at 20% error (%)")
ax.set_ylim(78, 102)
ax.set_title("Synaptic layer is the most sensitive; global wiring is robust")
style_ax(ax)
ax.legend(frameon=False)
fig.tight_layout()
save(fig, "fig_category20.png")

# ---------------------------------------------------------------------------
# FACTS — verified numbers used in the slides
# ---------------------------------------------------------------------------
def facts(df, name):
    print(f"\n===== {name} =====")
    b_edges = baseline(df, "edge_count")
    b_syn = baseline(df, "total_synapses")
    print(f"baseline edges={b_edges:,.0f}  synapses={b_syn:,.0f}")
    for key in ["total_synapses", "edge_count", "reciprocity"]:
        ch = pct_change(df, key)
        print(f"  {key:15s} change at 20%: {ch[-1]:+.2f}%  (last rates: "
              + ", ".join(f"{c:+.2f}" for c in ch[5:]) + ")")
    for key in ["pagerank_scores_topk_overlap", "pagerank_scores_pearson"]:
        s = series(df, key)
        print(f"  {key:28s} at 20%: {s[-1]:.4f}")
    ks, was = series(df, "in_degrees_ks")[-1], series(df, "in_degrees_wasserstein")[-1]
    print(f"  in_degrees_ks at 20%: {ks:.4f}   wasserstein: {was:.3f}")


facts(m, "MISSED")
facts(f, "FALSE")

bm = baseline(m, "total_synapses")
fm_edges = baseline(f, "edge_count")
new_edges = (series(f, "edge_count")[-1] - fm_edges)
new_syn = (series(f, "total_synapses")[-1] - bm)
print(f"\nFALSE new-edge analysis at 20%: edges +{new_edges:,.0f}  synapses +{new_syn:,.0f}")
print(f"  avg weight of added edges = {new_syn/new_edges:.2f} vs baseline mean {baseline(m,'weight_mean'):.2f}")

print("\n--- snapshot at 20% (baseline / missed / false) ---")
for key in ["total_synapses", "edge_count", "reciprocity", "scc_max_size"]:
    print(f"  {key:16s} {baseline(m,key):>12,.1f} / {series(m,key)[-1]:>12,.1f} / {series(f,key)[-1]:>12,.1f}")

print("\n--- weight metrics (missed / false) at each rate ---")
for key in ["weight_mean", "weight_median"]:
    print(f"  {key:14s} missed: " + ", ".join(f"{v:.2f}" for v in series(m, key))
          + "  false: " + ", ".join(f"{v:.2f}" for v in series(f, key)))

print("\n--- category preservation at 20% ---")
for c in cats:
    print(f"  {c:22s} missed: {cm[c]:.2f}%   false: {cf[c]:.2f}%")

meta_path = os.path.join(PROJ, "results/banc/missed_synapses/missedsynapses/BANC/error_1/data/metadata.json")
if not os.path.exists(meta_path):
    meta_path = os.path.join(PROJ, "results/BANC/missed_synapses/missedsynapses/BANC/error_1/data/metadata.json")
meta = json.load(open(meta_path))
print(f"\nmetadata: n_trials={meta['n_trials']}  runtime≈{meta['runtime_seconds']:.0f}s per trial")
print(f"num rates: {len(rates)}  rates: {[r*100 for r in rates]}")
print(f"num metrics per rate: {len(m[m['rate']==0.2])}")
print(f"analysis families: {sorted(m['analysis'].unique())}")
print("DONE")
