#!/usr/bin/env python3
"""Generate all figures for the Beamer presentation directly from the
experiment outputs (combined_results.csv for both error models).

Every figure is derived from the raw aggregated data; no numbers are hard-coded.
Also prints a FACTS section used to verify slide statements.
"""
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
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

MISSED = "results/BANC/missed_synapses/missedsynapses/BANC/trend_analysis/combined_results.csv"
FALSE = "results/BANC/false_synapses/falsesynapses/BANC/trend_analysis/combined_results.csv"
# paths relative to project root
PROJ = os.path.join(os.path.dirname(ROOT), "..")
MISSED = os.path.join(PROJ, MISSED)
FALSE = os.path.join(PROJ, FALSE)

m = pd.read_csv(MISSED)
f = pd.read_csv(FALSE)
rates = sorted(m["rate"].unique())
rate_pct = [r * 100 for r in rates]

C_MISSED = "#0b6e99"   # blue
C_FALSE = "#c4451d"    # red-orange
C_BASE = "#9aa5b1"

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 15,
    "axes.titlesize": 15,
    "axes.labelsize": 14,
    "xtick.labelsize": 12,
    "ytick.labelsize": 12,
    "legend.fontsize": 12,
    "axes.linewidth": 1.0,
    "figure.facecolor": "white",
    "axes.facecolor": "white",
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


def style_ax(ax):
    ax.grid(True, which="major", axis="y", color="#e8e8e8", linewidth=0.8)
    ax.set_axisbelow(True)
    for s in ["top", "right"]:
        ax.spines[s].set_visible(False)


# ---------------------------------------------------------------------------
# Figure 1 — Primary structural quantities: % change vs error rate
# ---------------------------------------------------------------------------
fig, axes = plt.subplots(1, 2, figsize=(9.5, 4.2))
for ax, key, title, unit in [
    (axes[0], "total_synapses", "Total synapses", "%"),
    (axes[1], "edge_count", "Total connections (edges)", "%"),
]:
    ax.plot(rate_pct, pct_change(m, key), "o-", color=C_MISSED, lw=2.4, ms=6, label="Missed synapses")
    ax.plot(rate_pct, pct_change(f, key), "s-", color=C_FALSE, lw=2.4, ms=6, label="False synapses")
    ax.axhline(0, color=C_BASE, lw=1.0, ls="--")
    ax.set_xlabel("Error rate (%)")
    ax.set_ylabel("Change vs baseline (%)")
    ax.set_title(title)
    style_ax(ax)
    ax.legend(frameon=False)
fig.tight_layout()
save(fig, "fig_primary.png")

# ---------------------------------------------------------------------------
# Figure 2 — Network organization: reciprocity & SCC size (raw values)
# ---------------------------------------------------------------------------
fig, axes = plt.subplots(1, 2, figsize=(9.5, 4.2))
for ax, key, title in [
    (axes[0], "reciprocity", "Reciprocity"),
    (axes[1], "scc_max_size", "Largest strongly connected component"),
]:
    for df, c, lab in [(m, C_MISSED, "Missed"), (f, C_FALSE, "False")]:
        ax.plot(rate_pct, series(df, key), "o-", color=c, lw=2.4, ms=6, label=lab + " synapses")
    ax.set_xlabel("Error rate (%)")
    ax.set_ylabel("Value" if key == "reciprocity" else "Vertices in SCC")
    ax.set_title(title)
    style_ax(ax)
    ax.legend(frameon=False)
fig.tight_layout()
save(fig, "fig_organization.png")

# ---------------------------------------------------------------------------
# Figure 3 — Degree-distribution distortion (KS & Wasserstein distances)
# ---------------------------------------------------------------------------
fig, axes = plt.subplots(1, 2, figsize=(9.5, 4.2))
for ax, key, title in [
    (axes[0], "in_degrees_ks", "In-degree KS distance"),
    (axes[1], "in_degrees_wasserstein", "In-degree Wasserstein distance"),
]:
    for df, c, lab in [(m, C_MISSED, "Missed"), (f, C_FALSE, "False")]:
        ax.plot(rate_pct, series(df, key), "o-", color=c, lw=2.4, ms=6, label=lab + " synapses")
    ax.set_xlabel("Error rate (%)")
    ax.set_ylabel("Distance from baseline")
    ax.set_title(title)
    style_ax(ax)
    ax.legend(frameon=False)
fig.tight_layout()
save(fig, "fig_degree_dist.png")

# ---------------------------------------------------------------------------
# Figure 4 — PageRank fidelity (top-k overlap)
# ---------------------------------------------------------------------------
fig, ax = plt.subplots(figsize=(6.2, 4.2))
for df, c, lab in [(m, C_MISSED, "Missed"), (f, C_FALSE, "False")]:
    ax.plot(rate_pct, series(df, "pagerank_scores_topk_overlap"), "o-", color=c, lw=2.4, ms=6, label=lab + " synapses")
ax.set_xlabel("Error rate (%)")
ax.set_ylabel("Top-k overlap (vs baseline)")
ax.set_title("PageRank: overlap of top-ranked neurons")
ax.set_ylim(0.8, 1.01)
style_ax(ax)
ax.legend(frameon=False)
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
    metric_key = {f"{a}.{mt}": mt for (a, mt) in df.groupby(["analysis", "metric"]).groups}
    d = df[df["rate"] > 0].groupby("metric")["preservation_pct"].min()
    # keep only preservation metrics that actually move
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
fig, ax = plt.subplots(figsize=(8.6, 5.6))
h = 0.36
for df, c, off, lab in [
    (m, C_MISSED, +h / 2, "Missed"),
    (f, C_FALSE, -h / 2, "False"),
]:
    vals = [min_pres(df).get(metric, 100.0) for metric in union]
    ax.barh(ypos + off, vals, height=h, color=c, alpha=0.9, label=lab + " synapses")
ax.set_yticks(ypos)
ax.set_yticklabels([labels.get(k, k) for k in union], fontsize=16)
ax.set_xlabel("Minimum preservation across 0–20% rates (%)", fontsize=15)
ax.set_xlim(64, 102)
ax.axvline(90, color="#f0883e", lw=1.0, ls=":")
ax.axvline(95, color="#d9a441", lw=1.0, ls=":")
ax.axvline(99, color="#5a8f4e", lw=1.0, ls=":")
ax.text(90.3, -1.2, "significant <90", fontsize=11, color="#c4451d")
ax.text(95.3, -1.2, "moderate <95", fontsize=11, color="#d98a1d")
ax.text(99.3, -1.2, "minor <99", fontsize=11, color="#7a9e2e")
style_ax(ax)
ax.legend(frameon=False, loc="lower left")
fig.tight_layout()
save(fig, "fig_ranking.png")

# ---------------------------------------------------------------------------
# Figure 6 — 20% snapshot: baseline vs missed vs false (grouped bars)
# ---------------------------------------------------------------------------
metrics = ["total_synapses", "edge_count", "reciprocity", "scc_max_size"]
titles = ["Total synapses", "Connections", "Reciprocity", "SCC size"]
fig, axes = plt.subplots(1, 4, figsize=(11.5, 3.9))
for ax, key, t in zip(axes, metrics, titles):
    b = baseline(m, key)
    mv, fv = series(m, key)[-1], series(f, key)[-1]
    ax.bar([0], [b], width=0.6, color=C_BASE, label="Baseline")
    ax.bar([1], [mv], width=0.6, color=C_MISSED, label="Missed 20%")
    ax.bar([2], [fv], width=0.6, color=C_FALSE, label="False 20%")
    ax.set_title(t, fontsize=13)
    ax.set_xticks([0, 1, 2])
    ax.set_xticklabels(["Base", "Miss", "False"], fontsize=11)
    ax.tick_params(axis="y", labelsize=10)
    style_ax(ax)
    if key == "reciprocity":
        ax.set_ylim(0, 0.16)
handles, labels_ = axes[0].get_legend_handles_labels()
fig.legend(handles, labels_, loc="upper center", ncol=3, frameon=False, fontsize=12)
fig.tight_layout(rect=[0, 0, 1, 0.92])
save(fig, "fig_snapshot20.png")

# ---------------------------------------------------------------------------
# Figure 7 — Overall mean preservation across all 49 metrics
# ---------------------------------------------------------------------------
fig, ax = plt.subplots(figsize=(6.2, 4.2))
om = m.groupby("rate")["preservation_pct"].mean().reindex(rates).to_numpy()
of_ = f.groupby("rate")["preservation_pct"].mean().reindex(rates).to_numpy()
ax.plot(rate_pct, om, "o-", color=C_MISSED, lw=2.4, ms=6, label="Missed synapses")
ax.plot(rate_pct, of_, "s-", color=C_FALSE, lw=2.4, ms=6, label="False synapses")
ax.set_xlabel("Error rate (%)")
ax.set_ylabel("Mean preservation across 49 metrics (%)")
ax.set_ylim(98.5, 100.2)
style_ax(ax)
ax.legend(frameon=False)
fig.tight_layout()
save(fig, "fig_overall.png")

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

print("\n--- weight metrics ---")
for key in ["weight_mean", "weight_median"]:
    print(f"  {key:14s} missed: " + ", ".join(f"{v:.2f}" for v in series(m, key))
          + "  false: " + ", ".join(f"{v:.2f}" for v in series(f, key)))

# summary used on title / setup slides
meta = json.load(open(os.path.join(PROJ, "results/BANC/missed_synapses/missedsynapses/BANC/error_1/data/metadata.json")))
print(f"\nmetadata: n_trials={meta['n_trials']}  runtime≈{meta['runtime_seconds']:.0f}s per trial")
print(f"num rates: {len(rates)}  rates: {[r*100 for r in rates]}")
print(f"num metrics per rate: {len(m[m['rate']==0.2])}")
print(f"analysis families: {sorted(m['analysis'].unique())}")
print("DONE")
