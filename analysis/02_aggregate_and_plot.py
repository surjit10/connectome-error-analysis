#!/usr/bin/env python3
"""Aggregate the tidy trial data and draw large-format trend figures.

Outputs:
  analysis/aggregated_metrics.csv   (mean/std/n per dataset x error model x rate)
  analysis/relative_change.csv      (% change vs 0% baseline per metric)
  analysis/figures/*.png            (large-format figures, 220 dpi)
"""
import os
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import matplotlib.patches as mpatches
from matplotlib.gridspec import GridSpec

ROOT = "/home/surjit/Desktop/flywire/v1/flywire_results_organized"
OUT  = "/home/surjit/Desktop/flywire/v1/analysis"
FIG  = os.path.join(OUT, "figures")
os.makedirs(FIG, exist_ok=True)

DATASETS     = ["BANC", "FAFB", "MANC", "MCNS", "MAOL"]
ERROR_MODELS = ["missed_synapses", "false_synapses", "synapse_count_measurement",
                "split_errors", "merge_errors"]
EM_LABELS = {
    "missed_synapses":           "Missed Synapses",
    "false_synapses":            "False Synapses",
    "synapse_count_measurement": "Synapse Count Noise",
    "split_errors":              "Split Errors",
    "merge_errors":              "Merge Errors",
}

# One fixed color per metric — reader focuses on trend shape, not dataset identity
METRIC_COLORS = {
    "Edge count":              "#1565C0",   # deep blue
    "Total synapses":          "#00695C",   # teal
    "Mean total degree":       "#6A1B9A",   # purple
    "Largest weak component":  "#E65100",   # deep orange
    "Largest strong component":"#00838F",   # cyan
    "Reciprocity":             "#558B2F",   # olive green
}

# Dataset colors used only in PageRank (one dataset per panel → color is accent)
DS_COLORS = {
    "BANC": "#1565C0",
    "FAFB": "#E65100",
    "MANC": "#2E7D32",
    "MCNS": "#B71C1C",
    "MAOL": "#6A1B9A",
}

ANALYSIS_COLS = {
    "basic_structure": ["metric_node_count", "metric_edge_count", "metric_total_synapses",
                        "metric_weight_mean", "metric_weight_variance", "metric_weight_std",
                        "metric_weight_max", "metric_density"],
    "degree_distribution": ["metric_total_degree_mean", "metric_in_degree_mean",
                            "metric_out_degree_mean", "metric_total_degree_std",
                            "metric_in_degree_max", "metric_out_degree_max"],
    "assortativity": ["metric_degree_assortativity"],
    "connected_components": ["metric_wcc_count", "metric_wcc_max_size",
                             "metric_scc_count", "metric_scc_max_size"],
    "reciprocity": ["metric_reciprocity"],
}

# 6 headline metrics shown in all sensitivity figures
HEADLINE = [
    ("basic_structure",      "metric_edge_count",        "Edge count"),
    ("basic_structure",      "metric_total_synapses",    "Total synapses"),
    ("degree_distribution",  "metric_total_degree_mean", "Mean total degree"),
    ("connected_components", "metric_wcc_max_size",      "Largest weak component"),
    ("connected_components", "metric_scc_max_size",      "Largest strong component"),
    ("reciprocity",          "metric_reciprocity",       "Reciprocity"),
]

NAVY  = "#1A237E"
YLAB  = "Change vs baseline (%)"
MAJOR = [0, 5, 10, 15, 20]

# ── global style ───────────────────────────────────────────────────────────────
plt.rcParams.update({
    "figure.dpi":        100,
    "savefig.dpi":       220,
    "font.family":       "DejaVu Sans",
    "font.size":         11,
    "axes.titlesize":    12,
    "axes.labelsize":    11,
    "xtick.labelsize":   10,
    "ytick.labelsize":   10,
    "legend.fontsize":   10,
    "axes.grid":         True,
    "grid.alpha":        0.35,
    "grid.linewidth":    0.7,
    "grid.color":        "#aaaaaa",
    "axes.linewidth":    1.1,
    "axes.edgecolor":    "#555555",
    "axes.spines.top":   False,
    "axes.spines.right": False,
    "axes.facecolor":    "#f8f9fa",   # very light grey panel background
    "figure.facecolor":  "white",
    "savefig.facecolor": "white",
    "text.color":        "#111111",
    "axes.labelcolor":   "#111111",
    "xtick.color":       "#444444",
    "ytick.color":       "#444444",
})


# ─── data loading ─────────────────────────────────────────────────────────────
def load():
    return pd.read_csv(os.path.join(OUT, "combined_trials.csv"))


def load_pagerank(em):
    rows = []
    for ds in DATASETS:
        rd = os.path.join(ROOT, ds, em, "reports")
        if not os.path.isdir(rd):
            continue
        for rate_dir in sorted(os.listdir(rd)):
            mf = os.path.join(rd, rate_dir, "data", "metrics.json")
            if not os.path.exists(mf):
                continue
            try:
                d  = json.load(open(mf))
                pg = d.get("pagerank", {})
                pr = pg.get("pagerank_scores_pearson")
                if pr:
                    sp = pg.get("pagerank_scores_spearman")
                    tk = pg.get("pagerank_scores_topk_overlap")
                    rate = float(rate_dir.replace("_percent", "").replace("_", "."))
                    rows.append({"dataset": ds, "error_model": em, "rate": rate,
                                 "pr_pearson": pr["mean"],
                                 "pr_spearman": sp["mean"] if sp else float("nan"),
                                 "pr_topk100": tk["mean"] if tk else float("nan")})
            except Exception:
                pass
    return pd.DataFrame(rows)


def aggregate(data):
    rows = []
    for (ds, em, rate), grp in data.groupby(["dataset", "error_model", "rate"]):
        for an, cols in ANALYSIS_COLS.items():
            sub = grp[grp.analysis_name == an]
            if sub.empty:
                continue
            for c in cols:
                vals = sub[c].dropna()
                if len(vals) == 0:
                    continue
                rows.append({
                    "dataset": ds, "error_model": em, "rate": rate, "analysis": an,
                    "metric": c, "mean": vals.mean(), "std": vals.std(ddof=0),
                    "n": len(vals),
                })
    return pd.DataFrame(rows)


# ─── axis helpers ─────────────────────────────────────────────────────────────
def _style_panel(ax, show_xlab=False, show_ylab=False):
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.yaxis.set_major_locator(mticker.MaxNLocator(nbins=4, prune="both"))
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.1f"))
    ax.set_xticks(MAJOR)
    if show_xlab:
        ax.set_xlabel("Error rate (%)", labelpad=3, fontsize=10)
    else:
        ax.set_xticklabels([])
    if show_ylab:
        ax.set_ylabel(YLAB, fontsize=10, labelpad=3)
    else:
        ax.set_yticklabels([])


def _zero_line(ax):
    ax.axhline(0, color="#555555", lw=1.1, ls="--", alpha=0.75, zorder=1)


def _flat_label(ax, msg="No significant change"):
    """Overlay a subtle text note when the line is essentially flat."""
    ax.text(0.5, 0.5, msg, transform=ax.transAxes, ha="center", va="center",
            fontsize=9, color="#888888", style="italic",
            bbox=dict(boxstyle="round,pad=0.3", facecolor="white",
                      edgecolor="#cccccc", alpha=0.8))


def _threshold_is_flat(y, threshold=0.25):
    """True when all values are within ±threshold of zero — flat / negligible."""
    return float(y.abs().max()) < threshold


def _endpoint_label(ax, x_last, y_last, color, fmt="{:+.1f}%", rmax=20, rpad=5):
    """Single endpoint annotation to the right of the last point."""
    ax.annotate(fmt.format(y_last), (x_last, y_last),
                textcoords="offset points", xytext=(5, 0),
                ha="left", va="center", fontsize=9.5,
                weight="bold", color=color, clip_on=False)


def _jitter_labels(endpoints, min_dist):
    """
    Given a list of endpoint dicts, adjust 'y' to ensure min_dist separation.
    Uses a simple relaxation/spring approach.
    """
    eps = sorted(endpoints, key=lambda e: e['y_orig'])
    for _ in range(25):
        for i in range(len(eps) - 1):
            diff = eps[i+1]['y'] - eps[i]['y']
            if diff < min_dist:
                push = (min_dist - diff) / 2.0
                eps[i]['y'] -= push
                eps[i+1]['y'] += push
    return eps

# ─── Figure 2 · EM sensitivity — presentation layout ──────────
def plot_em_metric(em, metric_idx, rel, rmax):
    """
    One large presentation-ready figure for a single (error_model, metric) combination.
    Layout: 1 large axis plotting all available datasets as distinct lines.
    Figure size: 14x8 (16:9 ratio). Large fonts for slide decks.
    """
    an, col, label = HEADLINE[metric_idx]
    sub      = rel[rel.error_model == em]
    ds_avail = [d for d in DATASETS if not sub[(sub.dataset == d) &
                                                (sub.analysis == an) &
                                                (sub.metric == col)].empty]
    if not ds_avail:
        return None

    fig, ax = plt.subplots(figsize=(14, 7.875), facecolor="white")
    fig.subplots_adjust(left=0.08, right=0.82, top=0.84, bottom=0.14)
    
    RPAD = rmax * 0.05

    endpoints = []
    vals_all = []
    for ds in ds_avail:
        s = sub[(sub.dataset == ds) & (sub.analysis == an) & (sub.metric == col)]
        if not s.empty:
            vals_all.extend(s.rel_change_pct.tolist())
    
    if vals_all:
        lo, hi = min(vals_all), max(vals_all)
        pad = max(abs(hi - lo) * 0.15, 0.3)
        ylim = (lo - pad, hi + pad)
    else:
        ylim = (-1, 1)
        
    y_range = ylim[1] - ylim[0]
    if y_range == 0: y_range = 2.0
    min_dist = y_range * 0.07  # 7% of axis height for label separation

    # Zero line (draw behind data)
    ax.axhline(0, color="#555555", lw=2.5, ls="--", alpha=0.75, zorder=1)

    for ds in ds_avail:
        s  = sub[(sub.dataset == ds) & (sub.analysis == an) & (sub.metric == col)]
        if s.empty: continue
        
        s = s.sort_values("rate")
        y = s.rel_change_pct
        color = DS_COLORS[ds]
        
        ax.plot(s.rate, y, "-o", color=color, lw=4.5, ms=11, zorder=3)
        
        # save endpoint for direct labeling
        last_x = float(s.rate.iloc[-1])
        last_y = float(y.iloc[-1])
        endpoints.append({
            'x': last_x, 'y': last_y, 'y_orig': last_y,
            'text': f"{ds} {last_y:+.1f}%", 'color': color
        })

    # Jitter and draw labels
    if endpoints:
        eps = _jitter_labels(endpoints, min_dist)
        for ep in eps:
            ax.annotate(ep['text'], (ep['x'], ep['y']),
                        textcoords="offset points", xytext=(12, 0),
                        ha="left", va="center", fontsize=16,
                        weight="bold", color=ep['color'], clip_on=False)
            if abs(ep['y'] - ep['y_orig']) > y_range * 0.01:
                ax.plot([ep['x'], ep['x'] + rmax * 0.025], [ep['y_orig'], ep['y']],
                        color=ep['color'], lw=2.0, alpha=0.4, zorder=2)

    ax.set_xlim(-0.5, rmax + RPAD)
    ax.set_ylim(*ylim)
    ax.set_xticks(MAJOR)
    
    ax.set_xlabel("Error rate (%)", labelpad=10, fontsize=18)
    ax.set_ylabel("Change vs baseline (%)", fontsize=18, labelpad=10)
    
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_linewidth(1.8)
    ax.spines["bottom"].set_linewidth(1.8)
    
    ax.tick_params(axis='both', which='major', labelsize=15, width=1.8, length=7)
    ax.yaxis.set_major_locator(mticker.MaxNLocator(nbins=7, prune="both"))
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.1f"))

    em_lbl = EM_LABELS[em]
    fig.suptitle(f"{em_lbl}  —  {label}",
                 fontsize=26, weight="bold", y=0.96, color=NAVY)
    fig.text(0.5, 0.88,
             "y = % change vs 0 % baseline (mean over replicate trials). Dashed line = no change.",
             ha="center", va="top", fontsize=15, color="#555555", style="italic")

    out = os.path.join(FIG, f"EM_{em}_{metric_idx:02d}_{col}.png")
    fig.savefig(out, bbox_inches="tight", facecolor="white", dpi=160)
    plt.close(fig)
    print("wrote", out)
    return out


# ─── Figure 3 · PageRank — one figure per error model ────────────────────────
def plot_pagerank_single(em, pr_all, rmax, y_lo, BANDS):
    """One landscape-sized PageRank figure for a single error model."""
    sub      = pr_all[pr_all.error_model == em]
    ds_avail = [d for d in DATASETS
                if not sub[sub.dataset == d].empty]
    if not ds_avail:
        return None

    fig, ax = plt.subplots(figsize=(14, 7.875), constrained_layout=False)
    fig.subplots_adjust(left=0.10, right=0.82, top=0.84, bottom=0.14)

    # Draw quality bands
    for b_lo, b_hi, b_fc, b_lbl in BANDS:
        if b_hi > y_lo:
            ax.axhspan(max(b_lo, y_lo), min(b_hi, 1.005),
                       facecolor=b_fc, alpha=0.65, linewidth=0, zorder=0)

    endpoints = []
    y_range = 1.005 - y_lo
    min_dist = y_range * 0.05  # 5% of height

    for ds in ds_avail:
        s = sub[sub.dataset == ds].sort_values("rate")
        if s.empty:
            continue
        color = DS_COLORS[ds]
        ax.plot(s.rate, s.pr_pearson, "-o", color=color,
                lw=4.0, ms=11, label=ds, zorder=3)
        
        last_x = float(s.rate.iloc[-1])
        last_y = float(s.pr_pearson.iloc[-1])
        endpoints.append({
            'x': last_x, 'y': last_y, 'y_orig': last_y,
            'text': f"{ds} {last_y:.4f}", 'color': color
        })

    if endpoints:
        eps = _jitter_labels(endpoints, min_dist)
        for ep in eps:
            ax.annotate(ep['text'], (ep['x'], ep['y']),
                        textcoords="offset points", xytext=(12, 0),
                        ha="left", va="center", fontsize=15,
                        weight="bold", color=ep['color'], clip_on=False)
            if abs(ep['y'] - ep['y_orig']) > y_range * 0.01:
                ax.plot([ep['x'], ep['x'] + rmax * 0.025], [ep['y_orig'], ep['y']],
                        color=ep['color'], lw=2.0, alpha=0.4, zorder=2)

    ax.set_ylim(y_lo, 1.005)
    ax.set_xlim(-0.5, rmax + rmax * 0.05)
    ax.set_xticks(MAJOR)
    
    ax.set_xlabel("Error rate (%)", fontsize=18, labelpad=10)
    ax.set_ylabel("Pearson r\n(perturbed vs baseline)",
                  fontsize=18, labelpad=10)
    
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_linewidth(1.8)
    ax.spines["bottom"].set_linewidth(1.8)
    
    ax.tick_params(axis='both', which='major', labelsize=15, width=1.8, length=7)
    ax.yaxis.set_major_locator(mticker.MaxNLocator(nbins=7, prune="both"))
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.3f"))

    # Band legend inside
    band_patches = [mpatches.Patch(facecolor=fc, label=lbl,
                                   edgecolor="#cccccc", alpha=0.8)
                    for b_lo, b_hi, fc, lbl in BANDS if b_hi > y_lo]
    ax.legend(handles=band_patches, loc="lower left", fontsize=14,
              frameon=True, framealpha=0.95, edgecolor="#cccccc",
              title="Quality bands", title_fontsize=13)

    fig.suptitle(f"PageRank Preservation  —  {EM_LABELS[em]}",
                 fontsize=26, weight="bold", y=0.96, color=NAVY)
    fig.text(0.5, 0.88,
             "Pearson correlation of perturbed vs baseline PageRank vectors (synapse-weighted, damping 0.85).",
             ha="center", fontsize=15, color="#555555", style="italic")

    out = os.path.join(FIG, f"pagerank_{em}.png")
    fig.savefig(out, bbox_inches="tight", facecolor="white", dpi=160)
    plt.close(fig)
    print("wrote", out)
    return out


# ─── Figure 4 · heatmap ───────────────────────────────────────────────────────
def plot_heatmap(rel, ems_present):
    SAFE = ["metric_edge_count", "metric_total_synapses", "metric_weight_variance",
            "metric_total_degree_mean", "metric_wcc_max_size", "metric_scc_count",
            "metric_reciprocity"]
    grp_rel = rel[rel.metric.isin(SAFE)].copy()
    rows = []
    for (ds, em), grp in grp_rel.groupby(["dataset", "error_model"]):
        if grp.empty:
            rows.append({"dataset": ds, "error_model": em,
                         "max_abs_change_pct": np.nan, "metric": "", "rate": np.nan})
            continue
        best = grp.assign(ab=grp.rel_change_pct.abs()).sort_values("ab",
                                                                   ascending=False).iloc[0]
        rows.append({"dataset": ds, "error_model": em,
                     "max_abs_change_pct": best.ab,
                     "metric": best.metric, "rate": best.rate})
    METRIC_SHORT = {
        "metric_edge_count": "Edges",
        "metric_total_synapses": "Synapses",
        "metric_weight_variance": "Wt. var.",
        "metric_total_degree_mean": "Degree",
        "metric_wcc_max_size": "WCC",
        "metric_scc_count": "SCC count",
        "metric_reciprocity": "Reciprocity"
    }

    mtrx = (pd.DataFrame(rows)
              .pivot(index="dataset", columns="error_model",
                     values="max_abs_change_pct")
              .reindex(index=DATASETS, columns=ems_present))
              
    mtrx_m = (pd.DataFrame(rows)
              .pivot(index="dataset", columns="error_model",
                     values="metric")
              .reindex(index=DATASETS, columns=ems_present))

    fig, ax = plt.subplots(figsize=(13, 5.5), facecolor="white")
    im = ax.imshow(mtrx.values.astype(float), cmap="YlOrRd", aspect="auto", vmin=0)
    ax.set_xticks(range(len(ems_present)))
    ax.set_xticklabels([EM_LABELS[e] for e in ems_present],
                        rotation=25, ha="right", fontsize=12)
    ax.set_yticks(range(len(DATASETS)))
    ax.set_yticklabels(DATASETS, fontsize=12.5)
    fig.subplots_adjust(bottom=0.24, top=0.86, left=0.10, right=0.96)

    for i in range(len(DATASETS)):
        for j in range(len(ems_present)):
            v = mtrx.values[i, j]
            m = mtrx_m.values[i, j]
            if np.isfinite(v):
                text_color = "white" if v > 45 else "#111111"
                short_m = METRIC_SHORT.get(m, str(m))
                ax.text(j, i, f"{v:.1f}%\n({short_m})", ha="center", va="center",
                        fontsize=10.5, color=text_color, weight="bold")
            else:
                ax.text(j, i, "n/a", ha="center", va="center",
                        fontsize=10.5, color="#aaaaaa", style="italic")

    cbar = fig.colorbar(im, ax=ax, fraction=0.025, pad=0.02)
    cbar.set_label("Max observed |% change| vs baseline", fontsize=11)
    cbar.ax.tick_params(labelsize=10)

    ax.set_title(
        "Worst-case impact of each error model across all FlyWire connectomes\n"
        "(Maximum |% change| over all error rates; darker = more disruption; "
        "assortativity excluded \u2014 near-zero baseline)",
        fontsize=12, pad=10, color="#111111",
    )
    out = os.path.join(FIG, "max_change_heatmap.png")
    fig.savefig(out, bbox_inches="tight", facecolor="white", dpi=220)
    plt.close(fig)
    print("wrote", out)


# ─── main ────────────────────────────────────────────────────────────────────
def main():
    data = load()
    agg  = aggregate(data)
    agg.to_csv(os.path.join(OUT, "aggregated_metrics.csv"), index=False)

    # Relative change vs baseline
    rel_rows = []
    base = agg[agg.rate == 0].set_index(["dataset", "error_model", "analysis", "metric"])["mean"]
    for _, r in agg[agg.rate > 0].iterrows():
        key = (r.dataset, r.error_model, r.analysis, r.metric)
        b0  = base.get(key)
        val = r["mean"]
        if b0 is None or abs(b0) < 1e-12:
            continue
        rel_rows.append({
            "dataset": r.dataset, "error_model": r.error_model, "rate": r.rate,
            "analysis": r.analysis, "metric": r.metric,
            "baseline": b0, "value": val,
            "rel_change_pct":  (val - b0) / abs(b0) * 100.0,
            "rel_std_pct":      r["std"] / abs(b0) * 100.0,
            "n":                r["n"],
        })
    rel = pd.DataFrame(rel_rows)
    rel.to_csv(os.path.join(OUT, "relative_change.csv"), index=False)

    ems_present = sorted(data.error_model.unique())
    rmax        = float(data.rate.max())

    # Figure 2 · one figure per (error_model, metric) = 5x5 = up to 25 clean pages
    em_metric_files = {}   # em -> [list of output paths in metric order]
    for em in ems_present:
        paths = []
        for mi in range(len(HEADLINE)):
            p = plot_em_metric(em, mi, rel, rmax)
            if p:
                paths.append((mi, p))
        em_metric_files[em] = paths

    # Figure 3 · PageRank — one figure per error model
    pr_all = pd.concat([load_pagerank(em) for em in ems_present], ignore_index=True)
    pr_all.to_csv(os.path.join(OUT, "pagerank_comparison.csv"), index=False)

    pr_min = pr_all.pr_pearson.min() if len(pr_all) else 0.94
    y_lo   = max(0.50, np.floor(pr_min * 40) / 40 - 0.005)
    BANDS  = [
        (0.999, 1.005, "#e8f5e9", "Excellent (\u2265 0.999)"),
        (0.990, 0.999, "#fff9c4", "Good (0.990\u20130.999)"),
        (0.970, 0.990, "#fff3e0", "Borderline (0.970\u20130.990)"),
        (y_lo,  0.970, "#ffebee", "Degraded (< 0.970)"),
    ]
    pr_files = {}
    for em in ems_present:
        p = plot_pagerank_single(em, pr_all, rmax, y_lo, BANDS)
        if p:
            pr_files[em] = p

    # Figure 4 · Heatmap
    plot_heatmap(rel, ems_present)

    # Write a manifest so 03_build_pdf_report.py can read exact filenames
    import json as _json
    manifest = {
        "em_metric_files": {em: v for em, v in em_metric_files.items()},
        "pr_files": pr_files,
        "headline": [(an, col, lbl) for an, col, lbl in HEADLINE],
    }
    with open(os.path.join(OUT, "figures", "manifest.json"), "w") as f:
        _json.dump(manifest, f, indent=2)

    print("done — figures in", FIG)


if __name__ == "__main__":
    main()
