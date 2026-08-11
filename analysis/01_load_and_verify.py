#!/usr/bin/env python3
"""Load every trial_results.csv into one tidy table and verify data consistency.

Checks performed:
  1. completeness: all 6 analyses present & SUCCESS per trial
  2. baseline invariance: at 0% error the network must be identical -> scalar
     metrics must match across trials AND across error models of the same dataset
  3. internal consistency: degree_mean == edges/n, density == edges/(n*(n-1))
  4. sensitivity: metrics that never move as the error rate rises are flagged
  5. cross-error-model agreement at baseline (catches 'wrong formula' runs)

Outputs:
  analysis/combined_trials.csv      (long/tidy, scalar metrics only)
  analysis/verification_report.txt
"""
import os
import numpy as np
import pandas as pd

ROOT = "/home/surjit/Desktop/flywire/v1/flywire_results_organized"
OUT = "/home/surjit/Desktop/flywire/v1/analysis"
os.makedirs(OUT, exist_ok=True)

DATASETS = ["BANC", "FAFB", "MANC", "MCNS", "MAOL"]
ERROR_MODELS = ["missed_synapses", "false_synapses", "synapse_count_measurement",
                "split_errors", "merge_errors"]

METRIC_COLS = [
    "metric_node_count", "metric_edge_count", "metric_total_synapses",
    "metric_weight_mean", "metric_weight_median", "metric_weight_variance",
    "metric_weight_std", "metric_weight_max", "metric_weight_min", "metric_density",
    "metric_in_degree_mean", "metric_in_degree_median", "metric_in_degree_variance",
    "metric_in_degree_std", "metric_in_degree_max", "metric_in_degree_min",
    "metric_out_degree_mean", "metric_out_degree_median", "metric_out_degree_variance",
    "metric_out_degree_std", "metric_out_degree_max", "metric_out_degree_min",
    "metric_total_degree_mean", "metric_total_degree_median", "metric_total_degree_variance",
    "metric_total_degree_std", "metric_total_degree_max", "metric_total_degree_min",
    "metric_degree_assortativity",
    "metric_wcc_count", "metric_wcc_max_size",
    "metric_scc_count", "metric_scc_max_size",
    "metric_reciprocity",
]
USECOLS = ["experiment_id", "analysis_name", "status", "runtime_seconds"] + METRIC_COLS


def rate_to_float(rate_dir):
    return float(rate_dir.replace("_percent", "").replace("_", "."))


def load_all():
    rows = []
    for ds in DATASETS:
        for em in ERROR_MODELS:
            trials_dir = os.path.join(ROOT, ds, em, "trials")
            if not os.path.isdir(trials_dir):
                continue
            for rate_dir in sorted(os.listdir(trials_dir)):
                rate = rate_to_float(rate_dir)
                for trial_dir in sorted(os.listdir(os.path.join(trials_dir, rate_dir))):
                    f = os.path.join(trials_dir, rate_dir, trial_dir, "trial_results.csv")
                    if not os.path.exists(f):
                        continue
                    df = pd.read_csv(f, usecols=USECOLS)
                    df["dataset"] = ds
                    df["error_model"] = em
                    df["rate"] = rate
                    df["trial"] = int(trial_dir.split("_")[1])
                    rows.append(df)
    return pd.concat(rows, ignore_index=True)


def main():
    data = load_all()
    print(f"loaded {len(data)} analysis-rows, {data.dataset.nunique()} datasets, "
          f"{data.error_model.nunique()} error models, "
          f"{data.rate.nunique()} rates, max {data.trial.nunique()} trials per cell")
    data.to_csv(os.path.join(OUT, "combined_trials.csv"), index=False)

    report = []
    rep = report.append
    rep("=" * 78)
    rep("FLYWIRE RESULTS - DATA CONSISTENCY VERIFICATION")
    rep("=" * 78)

    rep("\n[1] COMPLETENESS")
    grp = data.groupby(["dataset", "error_model", "rate"]).trial.nunique()
    rep(f"  trials per cell: min={grp.min()}, max={grp.max()}, cells={len(grp)}")
    for (ds, em, rate), n in grp.items():
        if n < 5:
            rep(f"  PARTIAL {ds}/{em} rate={rate}: only {n} trials")

    cnt = data.groupby(["dataset", "error_model", "rate", "trial"]).analysis_name.nunique()
    rep(f"  analyses per trial: min={cnt.min()}, max={cnt.max()} (expect 6)")
    bad_status = data[data.status != "SUCCESS"]
    rep(f"  non-SUCCESS rows: {len(bad_status)}")
    for _, r in bad_status.iterrows():
        rep(f"    {r.dataset}/{r.error_model} rate={r.rate} t{r.trial} {r.analysis_name}: {r.status}")

    rep("\n[2] BASELINE INVARIANCE (0% error)")
    base = data[data.rate == 0]
    for ds in DATASETS:
        sub = base[base.dataset == ds]
        if sub.empty:
            continue
        ems = sorted(sub.error_model.unique())
        piv = sub.pivot_table(
            index=["error_model", "trial"],
            values=["metric_node_count", "metric_edge_count", "metric_total_synapses",
                    "metric_density", "metric_reciprocity", "metric_degree_assortativity"],
            aggfunc="first")
        worst_all = 0.0
        if len(ems) > 1:
            ref = piv.loc[ems[0]].mean()
            for em in ems[1:]:
                diff = (piv.loc[em].mean() - ref).abs() / ref.replace(0, np.nan)
                worst_all = max(worst_all, diff.max())
            rep(f"  {ds}: baseline max rel diff across error models = {worst_all:.2e}")
        for em in ems:
            sub2 = sub[sub.error_model == em]
            stds = sub2.groupby("analysis_name")[["metric_edge_count", "metric_density",
                                                   "metric_reciprocity"]].std().max().max()
            rep(f"    {ds}/{em}: max std of baseline metrics across 5 trials = {stds:.6g}")

    rep("\n[3] INTERNAL CONSISTENCY")
    bs = data[data.analysis_name == "basic_structure"]
    dd = data[data.analysis_name == "degree_distribution"].rename(
        columns={"metric_in_degree_mean": "metric_in_degree_mean_dd"})
    m = bs.merge(dd[["dataset", "error_model", "rate", "trial", "metric_in_degree_mean_dd"]],
                 on=["dataset", "error_model", "rate", "trial"])
    expected = m.metric_edge_count / m.metric_node_count
    m["degree_rel_err"] = (m.metric_in_degree_mean_dd - expected).abs() / expected
    dens_exp = m.metric_edge_count / (m.metric_node_count * (m.metric_node_count - 1))
    m["density_rel_err"] = (m.metric_density - dens_exp).abs() / dens_exp
    rep(f"  in-degree mean vs edges/nodes: max rel err = {m.degree_rel_err.max():.3e}")
    rep(f"  density vs edges/(n*(n-1)):    max rel err = {m.density_rel_err.max():.3e}")

    rep("\n[4] SENSITIVITY (metrics that never respond to error rate)")
    key = ["metric_edge_count", "metric_density", "metric_total_degree_mean",
           "metric_degree_assortativity", "metric_wcc_max_size", "metric_scc_max_size",
           "metric_reciprocity"]
    flat = []
    for ds in DATASETS:
        for em in ERROR_MODELS:
            sub = data[(data.dataset == ds) & (data.error_model == em)]
            if sub.empty:
                continue
            base0 = sub[sub.rate == 0].groupby("analysis_name")[key].mean()
            hi = sub[sub.rate == sub.rate.max()].groupby("analysis_name")[key].mean()
            for k in key:
                for an in base0.index:
                    b0, h = base0.loc[an, k], hi.loc[an, k]
                    if b0 and abs(b0) > 1e-12 and abs((h - b0) / abs(b0)) < 1e-9:
                        flat.append(f"{ds}/{em} {an}.{k}")
    rep("  FLAT (0% -> max%): " + ("; ".join(flat) if flat else "none"))

    rep("\n[5] BASELINE TABLE (rate=0)")
    b = base.groupby("dataset").agg(
        nodes=("metric_node_count", "first"),
        edges=("metric_edge_count", "first"),
        total_synapses=("metric_total_synapses", "first"),
        density=("metric_density", "mean"),
        reciprocity=("metric_reciprocity", "mean"),
        assortativity=("metric_degree_assortativity", "mean"),
        wcc_max=("metric_wcc_max_size", "mean"),
        scc_max=("metric_scc_max_size", "mean"),
    )
    rep(b.to_string())

    with open(os.path.join(OUT, "verification_report.txt"), "w") as f:
        f.write("\n".join(report))
    print("\n".join(report))
    print(f"\nwrote combined_trials.csv and verification_report.txt")


if __name__ == "__main__":
    main()
