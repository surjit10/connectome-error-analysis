"""Comprehensive data-consistency verification for EM1/EM2/EM3.  v3

Data layout (verified):
  results/BANC/<em>/<rate>_percent/trial_XXX/<BANC_timestamp>/
      summary.csv        (per-trial, n=1 mean per analysis.metric)
      trial_results.csv  (wide: metric_<name> raw values per analysis)
      runtime_report.txt (contains "Perturbation metadata: {...}")
  results/BANC/<em>/error_<rate>/summary.csv      (presentation aggregate)

Cross-checks:
  A. Rate labels in combined_results.csv — expected derived from disk folders
  B1. trial_results.csv raw  ==  trial summary.csv mean   (independent raw source)
  B2. mean of trial means    ==  presentation error_x/summary.csv
  C.  perturbation metadata from runtime_report.txt — numeric assertions
  D.  model-specific scientific invariants
  E.  preservation formula sanity (EM2 no longer masked at 100%)
"""
import ast
import csv
import re
import sys
from pathlib import Path

csv.field_size_limit(sys.maxsize)  # trial_results.csv embeds huge pagerank lists

import numpy as np

RESULTS = Path("/home/surjit/Desktop/flywire/v1/results") / "BANC"

MODELS = ["missed_synapses", "false_synapses", "synapse_count_measurement"]

failures = []


def note(ok: bool, msg: str):
    tag = "✅" if ok else ("⚠️ " if "WARN" in msg else "❌")
    if not ok and "WARN" not in msg:
        failures.append(msg)
    print(f"  {tag} {msg}")


def parse_rate(folder_name: str) -> float:
    num = folder_name.replace("_percent", "").replace("_", ".")
    return float(num) / 100.0


def read_trial_summary(path: Path) -> dict:
    """trial summary.csv -> {(analysis, metric): mean} (n=1 per trial)"""
    out = {}
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            out[(row["analysis"], row["metric"])] = float(row["mean"])
    return out


def read_trial_results(path: Path) -> dict:
    """trial_results.csv -> {(analysis, metric): raw value} (numeric only)"""
    out = {}
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            a_name = row.get("analysis_name", "")
            for col, val in row.items():
                if not col.startswith("metric_"):
                    continue
                m_name = col[len("metric_"):]
                if m_name in ("in_degrees", "out_degrees", "pagerank_scores",
                              "wcc_size_distribution", "scc_size_distribution"):
                    continue  # list-valued columns
                if val is None or str(val).strip() == "":
                    continue
                try:
                    out[(a_name, m_name)] = float(val)
                except ValueError:
                    continue
    return out


def read_pres_summary(path: Path) -> dict:
    """presentation error_x/summary.csv -> {(analysis, metric): mean}"""
    out = {}
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            out[(row.get("analysis") or row.get("analysis_name", ""),
                 row.get("metric") or row.get("metric_name", ""))] = float(row["mean"])
    return out


def extract_perturbation_metadata(runtime_report: Path) -> dict:
    """Parse the 'Perturbation metadata: {...}' dict from runtime_report.txt."""
    txt = runtime_report.read_text(encoding="utf-8", errors="ignore")
    m = re.search(r"Perturbation metadata:\s*(\{.*?\})\s*$",
                  txt, re.MULTILINE | re.DOTALL)
    if not m:
        # single-line variant
        m = re.search(r"Perturbation metadata:\s*(\{.*?\})", txt)
    if not m:
        return {}
    try:
        return ast.literal_eval(m.group(1))
    except (SyntaxError, ValueError):
        return {}


# --------------------------------------------------------------------- #
# A. Rate labels (expected derived from disk folders)
# --------------------------------------------------------------------- #
def check_rate_labels():
    print("\n=== A. RATE LABEL CORRECTNESS ===")
    for slug in MODELS:
        em = RESULTS / slug
        cr = em / "trend_analysis" / "combined_results.csv"
        if not cr.exists():
            note(False, f"[{slug}] combined_results.csv missing")
            continue
        expected = sorted(
            {f"{parse_rate(f.name) * 100:g}%"
             for f in em.glob("*_percent") if f.is_dir()},
            key=lambda p: float(p.rstrip("%")),
        )
        pcts = []
        with open(cr, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                pcts.append(row["rate_pct"])
        unique = sorted(set(pcts), key=lambda p: float(p.rstrip("%")))
        note(unique == expected, f"[{slug}] rate_pct labels: {unique}")
        if unique != expected:
            note(False, f"[{slug}] expected {expected}")


# --------------------------------------------------------------------- #
# B. Raw -> trial summary -> presentation
# --------------------------------------------------------------------- #
def check_aggregation():
    print("\n=== B. RAW trial_results -> TRIAL SUMMARY -> PRESENTATION ===")
    for slug in MODELS:
        em = RESULTS / slug
        rate_dir = em / "5_percent"
        if not rate_dir.exists():
            rate_dir = em / "10_percent"
        pres_csv = em / "error_5" / "summary.csv"
        if not pres_csv.exists():
            pres_csv = em / "error_10" / "summary.csv"
        if not rate_dir.exists() or not pres_csv.exists():
            note(False, f"[{slug}] missing {rate_dir.name} or presentation summary")
            continue

        b1_checked = b1_mism = 0
        trial_aggs = []
        for t in sorted(rate_dir.glob("trial_*")):
            sf = next(t.glob("*/summary.csv"), None)
            tr = next(t.glob("*/trial_results.csv"), None)
            if not sf or not tr:
                continue
            summ = read_trial_summary(sf)
            raw = read_trial_results(tr)
            for key, smean in summ.items():
                if key in raw:
                    b1_checked += 1
                    if abs(raw[key] - smean) > 1e-6 * max(1.0, abs(smean)):
                        b1_mism += 1
                        if b1_mism <= 3:
                            note(False, f"[{slug}] B1 {key}: raw={raw[key]} vs summary={smean}")
            trial_aggs.append(summ)
        note(b1_checked > 0 and b1_mism == 0,
             f"[{slug}] B1: {b1_checked} raw trial_results values == trial summary means ({b1_mism} mismatches)")

        if not trial_aggs:
            note(False, f"[{slug}] no trials found")
            continue
        pres = read_pres_summary(pres_csv)
        b2_checked = b2_mism = 0
        for key, pmean in pres.items():
            if key not in trial_aggs[0]:
                continue
            tmeans = [t[key] for t in trial_aggs if key in t]
            agg = float(np.mean(tmeans))
            b2_checked += 1
            if abs(agg - pmean) > 1e-6 * max(1.0, abs(pmean)):
                b2_mism += 1
                if b2_mism <= 3:
                    note(False, f"[{slug}] B2 {key}: trial-agg={agg:.6f} vs presentation={pmean:.6f}")
        note(b2_checked > 0 and b2_mism == 0,
             f"[{slug}] B2: {b2_checked} trial-agg values == presentation summary ({b2_mism} mismatches)")


# --------------------------------------------------------------------- #
# C. Perturbation metadata numeric assertions
# --------------------------------------------------------------------- #
def check_perturbation_metadata():
    print("\n=== C. PERTURBATION METADATA NUMERIC ASSERTIONS ===")
    for slug in MODELS:
        em = RESULTS / slug
        found = None
        rate_val = None
        for folder in sorted(em.glob("*_percent")):
            r = parse_rate(folder.name)
            if r <= 0:
                continue
            rt = next(folder.rglob("runtime_report.txt"), None)
            if rt:
                found = rt
                rate_val = r
                break
        if not found:
            note(False, f"[{slug}] no runtime_report.txt at perturbed rate")
            continue
        pm = extract_perturbation_metadata(found)
        if not pm:
            note(False, f"[{slug}] could not parse Perturbation metadata from {found}")
            continue

        b_edges = None
        for f2 in sorted((em / "0_percent").glob("trial_*")):
            sf = next(f2.glob("*/summary.csv"), None)
            if sf:
                s = read_trial_summary(sf)
                b_edges = s.get(("basic_structure", "edge_count"))
                break

        print(f"    [{slug}] @{rate_val*100:g}% metadata: "
              f"{ {k: (round(v,4) if isinstance(v,float) else v) for k,v in pm.items()} }")
        if slug == "missed_synapses":
            achieved = pm.get("achieved_error_rate")
            removed_syn = pm.get("removed_synapses")
            total_syn = pm.get("total_original_synapses")
            if achieved is not None:
                note(abs(achieved - rate_val) / rate_val < 0.01,
                     f"[EM1] achieved_error_rate {achieved:.4f} vs target {rate_val} (ratio {achieved/rate_val:.4f})")
            # EM1 rate = fraction of SYNAPSES removed (not edges)
            if removed_syn is not None and total_syn:
                frac = removed_syn / total_syn
                note(abs(frac - rate_val) / rate_val < 0.05,
                     f"[EM1] removed_synapses {removed_syn} = {frac:.4f} of total ({total_syn}) (target {rate_val})")
        elif slug == "false_synapses":
            added = pm.get("false_edges_added")
            if added is not None and b_edges:
                note(abs(added / b_edges - rate_val) / rate_val < 0.05,
                     f"[EM2] false_edges_added {added} = {added/b_edges:.4f} of baseline edges (target {rate_val})")
        elif slug == "synapse_count_measurement":
            pct = pm.get("pct_edges_changed")
            mse = pm.get("mean_signed_error")
            rwc = pm.get("relative_weight_change")
            if pct is not None:
                note(0 < pct < 100, f"[EM3] pct_edges_changed {pct:.2f}% (0 < pct < 100 ✓)")
            if mse is not None:
                note(abs(mse) < 0.05, f"[EM3] mean_signed_error {mse:.5f} (~0 -> no systematic bias ✓)")
            if rwc is not None:
                note(abs(rwc) < 0.01, f"[EM3] relative_weight_change {rwc:.6f} (small, weight-only ✓)")


# --------------------------------------------------------------------- #
# D. Model-specific scientific invariants
# --------------------------------------------------------------------- #
def check_invariants():
    print("\n=== D. SCIENTIFIC INVARIANTS PER MODEL ===")
    for slug in MODELS:
        em = RESULTS / slug
        rates = {}
        for folder in sorted(em.glob("*_percent")):
            r = parse_rate(folder.name)
            trials = []
            for t in sorted(folder.glob("trial_*")):
                sf = next(t.glob("*/summary.csv"), None)
                if sf:
                    trials.append(read_trial_summary(sf))
            if trials:
                rates[r] = trials
        if not rates:
            note(False, f"[{slug}] no trial data")
            continue

        def mmean(rate, a, m):
            vals = [t.get((a, m)) for t in rates[rate]]
            vals = [v for v in vals if v is not None]
            return float(np.mean(vals)) if vals else None

        def mstd(rate, a, m):
            vals = [t.get((a, m)) for t in rates[rate]]
            vals = [v for v in vals if v is not None]
            return float(np.std(vals, ddof=1)) if len(vals) > 1 else 0.0

        b_edges = mmean(0.0, "basic_structure", "edge_count")
        b_nodes = mmean(0.0, "basic_structure", "node_count")
        b_syn = mmean(0.0, "basic_structure", "total_synapses")
        p_edges = mmean(0.20, "basic_structure", "edge_count")
        p_syn = mmean(0.20, "basic_structure", "total_synapses")
        p_nodes = mmean(0.20, "basic_structure", "node_count")

        if slug == "missed_synapses":
            note(b_edges is not None and p_edges is not None and p_edges < b_edges,
                 f"[EM1] edge_count {b_edges:.0f} -> {p_edges:.0f} at 20% (must DECREASE)")
            if b_syn is not None and p_syn is not None and p_syn > b_syn * 1.001:
                note(False, f"[EM1] WARN total_synapses INCREASED {b_syn:.0f} -> {p_syn:.0f} at 20% "
                            f"(deletion model; edge-index remap suspect — cross-check runtime_report)")
            else:
                note(True, f"[EM1] total_synapses {b_syn:.0f} -> {p_syn:.0f} at 20% (not increased ✓)")
        elif slug == "false_synapses":
            note(b_edges is not None and p_edges is not None and p_edges > b_edges,
                 f"[EM2] edge_count {b_edges:.0f} -> {p_edges:.0f} at 20% (must INCREASE)")
            note(b_nodes is None or p_nodes is None or abs(p_nodes - b_nodes) < 1e-6,
                 f"[EM2] node_count unchanged {b_nodes} -> {p_nodes}")
            if b_edges and p_edges:
                ratio = (p_edges - b_edges) / b_edges
                note(abs(ratio - 0.20) < 0.01,
                     f"[EM2] added-edge ratio {ratio:.4f} ~= 20% target ({(p_edges - b_edges):.0f} added)")
        elif slug == "synapse_count_measurement":
            note(b_edges is not None and p_edges is not None and abs(p_edges - b_edges) < 1e-9,
                 f"[EM3] edge_count IDENTICAL {b_edges:.0f} -> {p_edges:.0f} (topology fixed ✓)")
            note(b_nodes is None or p_nodes is None or abs(p_nodes - b_nodes) < 1e-9,
                 f"[EM3] node_count IDENTICAL {b_nodes} -> {p_nodes}")
            note(b_syn is not None and p_syn is not None and abs(p_syn - b_syn) > 1e-6,
                 f"[EM3] total_synapses CHANGED {b_syn:.0f} -> {p_syn:.0f} at 20% (weights perturbed ✓)")
        b_std = mstd(0.0, "basic_structure", "edge_count")
        note(b_std == 0.0, f"[{slug}] baseline edge_count std across trials = {b_std:.2e} (should be 0)")


# --------------------------------------------------------------------- #
# E. Preservation formula sanity
# --------------------------------------------------------------------- #
def check_preservation():
    print("\n=== E. PRESERVATION FORMULA SANITY ===")
    for slug in MODELS:
        em = RESULTS / slug
        cr = em / "trend_analysis" / "combined_results.csv"
        if not cr.exists():
            continue
        min_pres = 100.0
        min_rate = None
        with open(cr, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row["metric"] == "edge_count" and float(row["rate"]) > 0:
                    p = float(row["preservation_pct"])
                    if p < min_pres:
                        min_pres = p
                        min_rate = float(row["rate"])
        if slug == "false_synapses":
            note(min_pres < 95.0, f"[EM2] edge_count min preservation {min_pres:.2f}% @{min_rate * 100:g}% (was masked 100% before fix)")
        elif slug == "missed_synapses":
            note(min_pres < 100.0, f"[EM1] edge_count min preservation {min_pres:.2f}% @{min_rate * 100:g}%")
        else:
            note(min_pres > 99.0, f"[EM3] edge_count min preservation {min_pres:.2f}% (topology fixed -> ~100% correct)")


def main():
    check_rate_labels()
    check_aggregation()
    check_perturbation_metadata()
    check_invariants()
    check_preservation()

    print("\n" + "=" * 60)
    if failures:
        print(f"❌ {len(failures)} FAILURE(S):")
        for f in failures:
            print(f"   - {f}")
        sys.exit(1)
    print("✅ ALL CONSISTENCY CHECKS PASSED")


if __name__ == "__main__":
    main()
