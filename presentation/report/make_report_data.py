#!/usr/bin/env python3
"""Emit every number and LaTeX table for the report (report.tex) directly
from the experiment CSVs.  Run:  python make_report_data.py  -> report_data.tex
"""
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)))
PROJ = os.path.join(os.path.dirname(ROOT), "..")
sys.path.insert(0, PROJ)
from presentation.preservation_config import (  # noqa: E402
    calculate_preservation,
    higher_is_better,
    is_preservation_metric,
)


def resolve(rel):
    for cand in (os.path.join(PROJ, rel), os.path.join(PROJ, rel.replace("/BANC/", "/banc/", 1))):
        if os.path.exists(cand):
            return cand
    raise FileNotFoundError(rel)


MISSED = resolve("results/BANC/missed_synapses/missedsynapses/BANC/trend_analysis/combined_results.csv")
FALSE = resolve("results/BANC/false_synapses/falsesynapses/BANC/trend_analysis/combined_results.csv")

m = pd.read_csv(MISSED)
f = pd.read_csv(FALSE)
rates = sorted(m["rate"].unique())


def series(df, metric, col="mean"):
    return df[df["metric"] == metric].set_index("rate")[col].reindex(rates).to_numpy()


def baseline(df, metric):
    return df[df["metric"] == metric]["baseline_mean"].iloc[0]


def pct_change(df, metric):
    b = baseline(df, metric)
    return (series(df, metric) / b - 1.0) * 100.0


def recompute(df):
    out = np.full(len(df), np.nan)
    for (a, mt), g in df.groupby(["analysis", "metric"]):
        key = f"{a}.{mt}"
        base = float(g["baseline_mean"].iloc[0])
        for idx, row in g.iterrows():
            out[df.index.get_loc(idx)] = calculate_preservation(
                base, float(row["mean"]), higher_is_better=higher_is_better(key), metric_key=key)
    return out


m["preservation_pct"] = recompute(m)
f["preservation_pct"] = recompute(f)

pres_keys = sorted({mt for (a, mt) in m.groupby(["analysis", "metric"]).groups
                    if is_preservation_metric(f"{a}.{mt}")})

# ---------------------------------------------------------------- helpers ---
def rel_sigma(df, metric, rate=0.2):
    """sigma / mean (%) at a given rate — the reproducibility metric."""
    row = df[(df["metric"] == metric) & (df["rate"] == rate)].iloc[0]
    return row["std"] / row["mean"] * 100.0


def status_counts(df, rate=0.2):
    return df[(df["rate"] == rate)]["biological_status"].value_counts().to_dict()


CATS = {
    "Structural Topology": ["node_count", "edge_count", "density"],
    "Synaptic Properties": ["total_synapses", "weight_mean", "weight_median",
                            "weight_variance", "weight_std", "weight_max", "weight_min"],
    "Connectivity": ["wcc_max_size", "scc_max_size"],
    "Network Organization": ["reciprocity", "degree_assortativity"],
}


def cat_pres(df, rate=0.2):
    d = df[df["rate"] == rate].set_index("metric")
    return {cat: float(np.mean([d.loc[mt, "preservation_pct"] for mt in mets]))
            for cat, mets in CATS.items() if all(mt in d.index for mt in mets)}


def min_pres(df):
    d = df[df["rate"] > 0].groupby("metric")["preservation_pct"].min()
    keep = [mt for mt in pres_keys if d.get(mt, 100.0) < 99.999]
    return d[keep].sort_values()


cm, cf = cat_pres(m), cat_pres(f)
mp, fp = min_pres(m), min_pres(f)
union = list(dict.fromkeys(list(fp.index) + list(mp.index)))

R = {}  # named facts used by report.tex
R["baseline_neurons"] = f"{baseline(m, 'node_count'):,.0f}"
R["baseline_edges"] = f"{baseline(m, 'edge_count'):,.0f}"
R["baseline_synapses"] = f"{baseline(m, 'total_synapses'):,.0f}"
R["baseline_scc"] = f"{baseline(m, 'scc_max_size'):,.0f}"
R["baseline_recip"] = f"{baseline(m, 'reciprocity'):.4f}"
R["baseline_weight_mean"] = f"{baseline(m, 'weight_mean'):.2f}"
R["missed_syn20"] = f"{pct_change(m, 'total_synapses')[-1]:+.1f}"
R["missed_edge20"] = f"{pct_change(m, 'edge_count')[-1]:+.1f}"
R["missed_recip20"] = f"{pct_change(m, 'reciprocity')[-1]:+.1f}"
R["missed_topk20"] = f"{series(m, 'pagerank_scores_topk_overlap')[-1]:.3f}"
R["missed_pearson20"] = f"{series(m, 'pagerank_scores_pearson')[-1]:.4f}"
R["missed_ks20"] = f"{series(m, 'in_degrees_ks')[-1]:.4f}"
R["missed_w20"] = f"{series(m, 'in_degrees_wasserstein')[-1]:.2f}"
R["missed_scc20"] = f"{pct_change(m, 'scc_max_size')[-1]:+.2f}"
R["false_syn20"] = f"{pct_change(f, 'total_synapses')[-1]:+.1f}"
R["false_edge20"] = f"{pct_change(f, 'edge_count')[-1]:+.1f}"
R["false_recip20"] = f"{pct_change(f, 'reciprocity')[-1]:+.1f}"
R["false_topk20"] = f"{series(f, 'pagerank_scores_topk_overlap')[-1]:.3f}"
R["false_pearson20"] = f"{series(f, 'pagerank_scores_pearson')[-1]:.4f}"
R["false_ks20"] = f"{series(f, 'in_degrees_ks')[-1]:.4f}"
R["false_w20"] = f"{series(f, 'in_degrees_wasserstein')[-1]:.2f}"
R["false_scc20"] = f"{pct_change(f, 'scc_max_size')[-1]:+.2f}"
R["ks_ratio"] = f"{series(f, 'in_degrees_ks')[-1] / series(m, 'in_degrees_ks')[-1]:.1f}"
R["w_ratio"] = f"{series(f, 'in_degrees_wasserstein')[-1] / series(m, 'in_degrees_wasserstein')[-1]:.1f}"
R["added_edges"] = f"{series(f, 'edge_count')[-1] - baseline(f, 'edge_count'):,.0f}"
R["added_synapses"] = f"{series(f, 'total_synapses')[-1] - baseline(m, 'total_synapses'):,.0f}"
R["added_weight"] = (
    f"{(series(f, 'total_synapses')[-1] - baseline(m, 'total_synapses')) / (series(f, 'edge_count')[-1] - baseline(f, 'edge_count')):.2f}"
)
R["mean_pres_missed20"] = f"{m[m['metric'].isin(pres_keys) & (m['rate'] == 0.2)]['preservation_pct'].mean():.1f}"
R["mean_pres_false20"] = f"{f[f['metric'].isin(pres_keys) & (f['rate'] == 0.2)]['preservation_pct'].mean():.1f}"
R["n_pres_metrics"] = str(len(pres_keys))
R["sigma_syn_missed"] = f"{rel_sigma(m, 'total_synapses'):.3f}"
R["sigma_syn_false"] = f"{rel_sigma(f, 'total_synapses'):.3f}"
R["sigma_edge_missed"] = f"{rel_sigma(m, 'edge_count'):.3f}"
R["sigma_edge_false"] = f"{rel_sigma(f, 'edge_count'):.3f}"

labels = {
    "edge_count": "Edge count", "density": "Density", "total_synapses": "Total synapses",
    "reciprocity": "Reciprocity", "scc_max_size": "SCC max size", "wcc_max_size": "WCC max size",
    "weight_variance": "Weight variance", "weight_median": "Weight median",
    "weight_mean": "Weight mean", "weight_std": "Weight std", "weight_max": "Weight max",
    "degree_assortativity": "Assortativity",
}

# ---------------------------------------------------------------- emit -------
# report_data.tex  : named facts (\newcommand) used inline in report.tex
# table1.tex .. table4.tex : captioned table bodies, \input at their place

def cmdname(k):
    """snake_case key -> camelCase LaTeX control sequence.

    TeX control words may only contain letters, so digit suffixes are
    spelled out: missed_syn20 -> \\missedSynTwenty.
    """
    parts = k.split("_")
    name = parts[0] + "".join(p.capitalize() for p in parts[1:])
    name = name.replace("20", "Twenty")
    return "\\" + name


facts = []
for k, v in R.items():
    facts.append(f"\\newcommand{{{cmdname(k)}}}{{{v}}}")

with open(os.path.join(ROOT, "report_data.tex"), "w") as fh:
    fh.write("%% Auto-generated by make_report_data.py -- DO NOT EDIT BY HAND\n")
    fh.write("%% Regenerate with:  python make_report_data.py\n")
    fh.write("\n".join(facts) + "\n")

# ---- Table 1: snapshot at 20% ------------------------------------------------
def table1():
    rows = [
        ("Total synapses", "total_synapses", "{:,.0f}", 1),
        ("Connections (edges)", "edge_count", "{:,.0f}", 1),
        ("Reciprocity", "reciprocity", "{:.4f}", 1),
        ("Giant SCC size", "scc_max_size", "{:,.0f}", 2),
    ]
    out = ["\\begin{tabular}{lccccl}", "  \\toprule",
           "  \\textbf{Metric} & \\textbf{Baseline} & \\textbf{Missed @20\\%} & \\textbf{False @20\\%} & \\textbf{Missed} & \\textbf{False}\\\\",
           "  & & & & \\textbf{change} & \\textbf{change}\\\\",
           "  \\midrule"]
    for name, key, fmt, prec in rows:
        b = baseline(m, key)
        mv, fv = series(m, key)[-1], series(f, key)[-1]
        ch_m = (mv / b - 1) * 100
        ch_f = (fv / b - 1) * 100
        out.append(f"  {name} & {fmt.format(b)} & {fmt.format(mv)} & {fmt.format(fv)}"
                   f" & {ch_m:+.{prec}f}\\% & {ch_f:+.{prec}f}\\%\\\\")
    out += ["  \\bottomrule", "\\end{tabular}"]
    return out


# ---- Table 2: category preservation at 20% -----------------------------------
def table2():
    out = ["\\begin{tabular}{lccc}", "  \\toprule",
           "  \\textbf{Category} & \\textbf{Member metrics} & \\textbf{Missed} & \\textbf{False}\\\\",
           "  \\midrule"]
    for cat in CATS:
        out.append(f"  {cat} & {len(CATS[cat])} & {cm[cat]:.1f}\\% & {cf[cat]:.1f}\\%\\\\")
    out += ["  \\bottomrule", "\\end{tabular}"]
    return out


# ---- Table 3: sensitivity ranking (minimum preservation 0-20%) ---------------
def table3():
    out = ["\\begin{tabular}{lcc}", "  \\toprule",
           "  \\textbf{Metric} & \\textbf{Missed} & \\textbf{False}\\\\",
           "  \\midrule"]
    for mt in union:
        out.append(f"  {labels.get(mt, mt)} & {mp.get(mt, 100.0):.2f}\\% & {fp.get(mt, 100.0):.2f}\\%\\\\")
    out += ["  \\bottomrule", "\\end{tabular}"]
    return out


# ---- Table 4: reproducibility (sigma / mean at 20%) ---------------------------
def table4():
    return ["\\begin{tabular}{lccc}", "  \\toprule",
            "  \\textbf{Metric} & \\textbf{Missed} & \\textbf{False}\\\\",
            "  \\midrule",
            f"  Total synapses & $\\pm${rel_sigma(m, 'total_synapses'):.3f}\\% & $\\pm${rel_sigma(f, 'total_synapses'):.3f}\\%\\\\",
            f"  Edge count & $\\pm${rel_sigma(m, 'edge_count'):.3f}\\% & $\\pm${rel_sigma(f, 'edge_count'):.3f}\\%\\\\",
            f"  Giant SCC & $\\pm${rel_sigma(m, 'scc_max_size'):.3f}\\% & $\\pm${rel_sigma(f, 'scc_max_size'):.3f}\\%\\\\",
            "  \\bottomrule", "\\end{tabular}"]


for name, fn in [("table1", table1), ("table2", table2), ("table3", table3), ("table4", table4)]:
    with open(os.path.join(ROOT, name + ".tex"), "w") as fh:
        fh.write("% Auto-generated by make_report_data.py\n")
        fh.write("\n".join(fn()) + "\n")
    print(f"wrote {name}.tex")
print("\nKey facts:")
for k in ["baseline_synapses", "missed_syn20", "missed_edge20", "false_edge20",
          "false_syn20", "ks_ratio", "w_ratio", "false_topk20", "missed_topk20",
          "mean_pres_missed20", "mean_pres_false20", "added_edges", "added_weight"]:
    print(f"  {k}: {R[k]}")
