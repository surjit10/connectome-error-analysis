# BANC Error-Model Presentation (Beamer)

Slide deck: **"Impact of Reconstruction Errors on Connectome Graph Analysis"** —
an experimental comparison of **missed synapses** (EM1) and **false synapses**
(EM2) on the BANC connectome.

## Contents

| File | Purpose |
|------|---------|
| `main.tex` | Complete Beamer presentation (12 slides, TikZ diagrams) |
| `make_figures.py` | Regenerates every figure from the raw experiment CSVs |
| `figures/` | Generated figures (PNG, 200 dpi) |
| `main.pdf` | Compiled deck |

## Data provenance

Every number and figure is derived from the experiment outputs:

- `results/BANC/missed_synapses/missedsynapses/BANC/trend_analysis/combined_results.csv`
- `results/BANC/false_synapses/falsesynapses/BANC/trend_analysis/combined_results.csv`

These aggregate 5 trials × 10 error rates (0–20%) × 49 metrics per model.

## Regenerate figures

```bash
python3 make_figures.py        # or: .venv/bin/python make_figures.py
```

## Compile

```bash
pdflatex -interaction=nonstopmode main.tex
pdflatex -interaction=nonstopmode main.tex   # second pass for page refs
```

Requires a TeX distribution with **beamer** and **pgf (TikZ)** (e.g.
`tlmgr install beamer pgf` on TinyTeX).
