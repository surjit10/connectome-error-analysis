# FlyWire error-model analysis

Analysis of the organized FlyWire results (`../flywire_results_organized/`): how five
segmentation error models perturb the structure of five Drosophila EM connectomes as the
error rate grows 0 → 20 %.

## Deliverables

| File | What it is |
|---|---|
| `Flywire_Error_Model_Analysis_Report.pdf` | **Main report (54 pages)** — Contents, 1·Question, 2·Data (baseline + coverage), 3·Method (models + effect measure), 4·Verification (checks + anomalies), 5·Results (one page per error model, PageRank, heatmap, effect-size table + per-dataset analysis output), 6·Takeaway, 7·Reproducibility (demo), and a statistical-notes appendix. Tables are content-sized and never overflow the page. |
| `figures/EM_<em>_NN_metric_<metric>.png` | Six per-error-model trend figures (edge count, total synapses, mean degree, largest WCC, largest SCC, reciprocity): relative % change vs error rate, one line per dataset — one full landscape page per (error model, metric) in the report. |
| `figures/pagerank_<em>.png` | PageRank Pearson correlation vs error rate, one figure per error model. |
| `figures/max_change_heatmap.png` | Max observed metric change per error model (assortativity excluded — near-zero baseline). |
| `figures/manifest.json` | Machine-readable index of the generated figures. |

## Pipeline

| Script | Output | Purpose |
|---|---|---|
| `01_load_and_verify.py` | `combined_trials.csv`, `verification_report.txt` | Loads every per-trial CSV from the organized tree; runs completeness, baseline-invariance, degree/density-identity and sensitivity checks. |
| `02_aggregate_and_plot.py` | `aggregated_metrics.csv`, `relative_change.csv`, `pagerank_comparison.csv`, `figures/*.png` | Aggregates trials → mean/std per (dataset, error model, rate, metric); computes relative change vs the 0 % baseline; draws all figures. |
| `03_build_pdf_report.py` | `Flywire_Error_Model_Analysis_Report.pdf` | Assembles the formatted PDF (matplotlib only, no extra dependencies). |

## Statistical care taken in this report

- **Near-zero baselines.** Assortativity's % change (+135 % for false synapses) is a division
  artefact of a near-zero baseline (−0.057 to +0.037; MANC is slightly positive); the report shows it but never ranks models on it, and the
  max-change heatmap excludes assortativity.
- **Partial runs.** FAFB merge (2 trials/rate) and MANC merge (1 trial/rate) are kept as-is and
  flagged; MANC/MAOL false-synapse and MAOL merge runs are absent (Table 2 shows coverage).
- **Means hide spread.** Table 5 averages % changes across datasets; Table 6 lists every
  dataset individually and the min…max spread is printed under Table 5.
- **Axis conventions.** Every trend figure is labelled with error rate (%) on x and
  "% change vs 0% baseline (mean over trials)" on y; PageRank is plotted as the correlation
  value (baseline = 1.0 by construction), not a % change.

## Verification summary (from `verification_report.txt`)

- **1,030 trials** across 5 datasets × up to 5 error models × 10 rates × up to 5 replicates; all 6 analyses SUCCESS (6,180 analysis rows, 0 failures).
- 0 % baseline is **bit-identical** across trials and error models within each dataset.
- Degree/density identities hold to machine precision (rel. err < 7e-13).
- Anomalies investigated and explained, not "fixed": false-synapse W1 invariance is a
  mathematical identity (deterministic edge additions); synapse-count measurement
  changes weights only (predicted variance increase matches theory); flat WCC for false
  synapses and flat edge count for split errors are by design.
- Partial runs kept as-is: FAFB merge (2 trials/rate), MANC merge (1 trial/rate).

## Key results

At 20 % error (means across datasets):

| Error model | Edge count | Total synapses | Weight variance | Mean degree | Largest WCC | Largest SCC | PageRank r |
|---|---|---|---|---|---|---|---|
| Missed synapses | −4.9 % | −20.0 % | −30.3 % | −4.9 % | −0.0 % | −0.0 % | 0.999 |
| False synapses | +19.4 % | +7.6 % | −13.8 % | +19.4 % | +0.0 % | +0.6 % | 0.994 |
| Syn. count measurement | +0.0 % | +0.0 % | +5.5 % | +0.0 % | +0.0 % | +0.0 % | 0.999 |
| Split errors | −0.0 % | −0.0 % | +0.0 % | −14.9 % | +17.7 % | +17.6 % | 0.995 |
| Merge errors | −10.9 % | −0.1 % | +46.9 % | −2.6 % | −8.6 % | −9.0 % | 0.989 |

Takeaways: deleting connections hurts more than adding them; measurement noise is benign;
split/merge errors change topology (neuron counts) rather than edges; PageRank rankings are
robust (>0.97) even at 20 % error; all five datasets respond qualitatively identically.
