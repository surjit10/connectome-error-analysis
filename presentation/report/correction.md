# Correction Report — Weight & Assortativity Preservation in BANC Results

**Date:** 2026-08-06
**Scope:** BANC results — EM1 (missed synapses) + EM2 (false synapses)
**Deliverable corrected:** `presentation/report/main.tex` → `main.pdf` (13 slides) + regenerated figures in `presentation/report/figures/`

---

## 1. The Abnormality

The exported experiment results under

```
results/BANC/missed_synapses/missedsynapses/BANC/trend_analysis/combined_results.csv
results/BANC/false_synapses/falsesynapses/BANC/trend_analysis/combined_results.csv
```

contain **incorrect `preservation_pct` values for the six weight metrics
(`weight_mean`, `weight_median`, `weight_variance`, `weight_std`, `weight_max`,
`weight_min`) and for `degree_assortativity`** in **both** error models.

The CSV reports **`preservation_pct = 100.000`** for these metrics at **every
error rate**, even though the underlying metric values changed substantially.
For example, at the 20% error rate:

| Metric | Model | Baseline | Perturbed @20% | True preservation* | CSV value |
|---|---|---|---|---|---|
| `weight_mean` | missed | 5.9038 | 4.8783 | **82.63%** | 100.000% |
| `weight_median` | missed | 4.0 | 3.0 | **75.00%** | 100.000% |
| `weight_variance` | missed | 89.4575 | 61.6791 | **68.95%** | 100.000% |
| `weight_std` | missed | 9.4582 | 7.8536 | **83.04%** | 100.000% |
| `weight_max` | missed | 913 | 841 | **92.11%** | 100.000% |
| `weight_mean` | false | 5.9038 | 5.4130 | **91.69%** | 100.000% |
| `weight_median` | false | 4.0 | 3.0 | **75.00%** | 100.000% |
| `degree_assortativity` | missed | −0.04643 | −0.04974 | **99.67%** | 100.000% |
| `degree_assortativity` | false | −0.04643 | −0.03154 | **98.51%** | 100.000% |

\* = recomputed with the framework's own `calculate_preservation()`
(`presentation/preservation_config.py`), symmetric ratio
`min(B,P)/max(B,P) × 100` (and the special `1 − |Δ|` formula for assortativity).

The same defect appears in the per-rate exports:
`error_20/data/metrics.json` stores `"preservation_pct": null` for these
metrics, and `error_20/summary.csv` classifies them as `metric_type=similarity`
with an empty preservation column — while the **current** `METRIC_TYPES`
config in `presentation/preservation_config.py` classifies all of them as
`preservation` metrics.

### Root cause

The `results/BANC/` exports were generated with an **older revision of
`presentation/preservation_config.py`** (before commit `9f826fe`, Aug 4 2026)
that did not include `weight_*` in `METRIC_TYPES`, and before commit `9bf0470`
which introduced the assortativity-specific preservation formula. Under that
old config, `get_metric_type()` fell back to `"similarity"` for these metrics,
so `is_preservation_metric()` returned `False` and the exporters wrote the
fallback values `100.0` (trend CSV) / `null` (metrics.json).

The **raw measurements themselves were never wrong** — the `baseline_mean` and
`mean` columns are correct and consistent (e.g. `total_synapses` derived from
them matches the independent totals). Only the *preservation interpretation
layer* was stale.

---

## 2. Is it Corrected?

**In the presentation: YES.**

The slide-9 table in `main.tex` ("Category-wise Preservation at 20% Error") was
updated with values recomputed via the framework's **current**
`calculate_preservation()` from the CSV's own `baseline_mean`/`mean` columns
(`presentation/report/make_figures.py` → `recompute_preservation()`):

| Category | Metrics | Missed (before → corrected) | False (before → corrected) |
|---|---|---|---|
| Structural Topology | 3 | 97.87% (unchanged) | 88.89% (unchanged) |
| Synaptic Properties | 7 | **97.14% → 83.10%** | **98.70% → 90.67%** |
| Connectivity | 2 | 99.97% (unchanged) | 99.80% (unchanged) |
| Network Organization | 2 | **99.70% → 99.53%** | **96.69% → 95.95%** |

The ranking figure (`fig_ranking`, slide 8) was regenerated from the corrected
preservation values and now correctly shows the weight metrics as the
**most-sensitive** metrics (weight variance 69%, median 75% under missed),
which the stale 100% values had hidden.

Secondary wording corrections in the deck (all data-backed):

- "6–15× more" → "**14–27×** more" (in-degree KS ratio range across rates is
  13.8×–27.3×; 14.5× at 20%).
- Slide 11 "every sensitive metric monotone" → softened: primary quantities
  (synapses, edges, KS) are monotone; higher-order metrics (reciprocity, top-k)
  show mild low-rate non-monotonicity (false reciprocity dips 0.8–2% then rises).
- Slide 12 "PageRank ranking survive to >99%" → corrected: giant SCC / node
  count >99%; PageRank correlation stays ≥0.98 (false: 0.9833, top-k 0.89).
- "0.97 → 0.89" arrows reworded: 0.97 is the *missed* top-k at 20%, 0.89 the
  *false* value — a cross-model comparison, not an erosion trajectory.
- Slide 11 table relabeled "95% CI width" → "**σ / mean (rel.)**" (the numbers
  shown are σ/mean, 0.009%/0.005%, not CI half-widths 0.0079%/0.0047%).

**In the exported CSVs: NO — deliberately.**

The `results/BANC/.../combined_results.csv` and `metrics.json` files were left
untouched. They still contain the stale `100.000` / `null` preservation values
for weight & assortativity metrics. Re-deriving them from the raw columns is
exact (that is what `make_figures.py` now does), but overwriting the historical
experiment exports is a separate decision.

---

## 3. If You Re-run, Will You Get Correct Results?

**YES — a fresh run with the current codebase produces correct values, with no
code changes needed.**

- The current `presentation/preservation_config.py` (working tree = commit
  `738e623`) classifies `weight_*` as `preservation` in `METRIC_TYPES` and
  contains the assortativity-specific formula introduced in `9bf0470`.
- `presentation/trend_exporter.py`, `single_rate_exporter.py`, and the ranking
  plotter all call `calculate_preservation(ev.baseline_mean, ev.mean, ...)`
  through `is_preservation_metric()`, so a re-export (or a full
  notebook/experiment run) will write e.g. `82.63` (missed weight_mean) and
  `98.51` (false assortativity) instead of `100.000`.
- The regression is pinned by the existing exports' raw columns: the corrected
  values above are recomputed from the same `baseline_mean`/`mean` numbers, so
  a fresh pipeline run reproduces them exactly.

**Caveats:**

1. **Re-export vs. re-run.** If you only re-run the presentation layer
   (`0-temp/regen_all_presentations.py`), it rebuilds exports from the
   per-trial `summary.csv` / `trial_results.csv` files under
   `results/BANC/<model>/error_*/trial_*/` — those must still exist for a
   faithful re-export. If they have been cleaned up, a full experiment re-run
   is required.
2. **Runtime.** The full EM1+EM2 BANC matrix (10 rates × 5 trials × 2 models)
   takes roughly 5 h; the corrected values only depend on the reporting layer,
   so you do *not* need to re-run the stochastic perturbation to fix them.
3. **Other models.** `synapse_count_measurement` and `split_errors` results
   were not audited here; the same stale-config defect could affect them if
   they were exported before `9f826fe`/`9bf0470`.

---

## 4. Files Changed (this correction)

| File | Change |
|---|---|
| `presentation/report/main.tex` | Slide-9 table values + footnote; KS-range wording; monotonicity wording; PageRank conclusion; top-k arrows; CI-width label |
| `presentation/report/make_figures.py` | Added `recompute_preservation()` (framework formula), weight/assortativity metric labels, x-range widened; figures regenerated |
| `presentation/report/figures/*.png` | Regenerated (7 figures) from corrected preservation values |
| `presentation/report/correction.md` | This document |

Experiment code, error models, statistics engine, and `results/` exports were
**not** modified.

---

## 5. Quick Verification

```bash
# Recompute the slide-9 table from the CSVs (framework's own formula):
cd /home/surjit/Desktop/flywire/v1
python - <<'EOF'
import pandas as pd
from presentation.preservation_config import calculate_preservation, higher_is_better
for name, path in [("MISSED","results/BANC/missed_synapses/missedsynapses/BANC/trend_analysis/combined_results.csv"),
                   ("FALSE","results/BANC/false_synapses/falsesynapses/BANC/trend_analysis/combined_results.csv")]:
    df = pd.read_csv(path)
    for met in ["weight_mean","weight_median","weight_variance","degree_assortativity"]:
        r = df[df["metric"]==met]; key = f"{r['analysis'].iloc[0]}.{met}"
        p = calculate_preservation(float(r["baseline_mean"].iloc[0]), float(r[r['rate']==0.2]['mean'].iloc[0]),
                                   higher_is_better=higher_is_better(key), metric_key=key)
        print(f"{name:6s} {met:22s} -> {p:.2f}%")
EOF
# Expected: MISSED weight_mean -> 82.63, weight_median -> 75.00,
#           weight_variance -> 68.95, degree_assortativity -> 99.67
#           FALSE  weight_mean -> 91.69, weight_median -> 75.00,
#           weight_variance -> 84.97, degree_assortativity -> 98.51
```
