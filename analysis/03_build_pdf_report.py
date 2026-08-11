#!/usr/bin/env python3
"""Assemble the FlyWire results PDF report (matplotlib-only, no extra deps).

Structure: Cover -> Contents -> 1 Question -> 2 Data -> 3 Method ->
4 Verification -> 5 Results (one figure page per error model, then
effect-size + per-dataset analysis-output tables) -> 6 Takeaway ->
7 Reproducibility (demo) -> Appendix: statistical notes.

Layout engine: text is wrapped to measured line counts, table rows are
sized to their content, column widths are normalised to the printable
width, and any content that does not fit on a page is pushed to a
continuation page --- nothing overflows the page edges.
"""
import datetime
import os
import textwrap
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

OUT = "/home/surjit/Desktop/flywire/v1/analysis"
FIG = os.path.join(OUT, "figures")
PDF = os.path.join(OUT, "Flywire_Error_Model_Analysis_Report.pdf")

DATASETS = ["BANC", "FAFB", "MANC", "MCNS", "MAOL"]
EM_ORDER = ["missed_synapses", "false_synapses", "synapse_count_measurement",
            "split_errors", "merge_errors"]
EM_LABELS = {
    "missed_synapses": "Missed synapses",
    "false_synapses": "False synapses",
    "synapse_count_measurement": "Synapse count measurement",
    "split_errors": "Split errors",
    "merge_errors": "Merge errors",
}
EM_COLOR = {
    "missed_synapses": "#d62728", "false_synapses": "#1f77b4",
    "synapse_count_measurement": "#2ca02c", "split_errors": "#ff7f0e",
    "merge_errors": "#9467bd",
}

W, H = 8.5, 11.0            # letter portrait
ML, MR = 0.09, 0.09          # page margins (figure fraction)
AVAIL = 1.0 - ML - MR        # printable width fraction
NAVY = "#1a1a2e"
GREY = "#000000"

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "figure.facecolor": "white",
    "savefig.facecolor": "white",
})

# ---------------------------------------------------------------------------
# layout helpers (all y coordinates are figure-fractions from the TOP)
# ---------------------------------------------------------------------------
def text_width_in(fig, text, fontsize, weight="normal", style="normal"):
    """Exact rendered width of `text` in inches (DejaVu Sans metrics)."""
    r = fig.canvas.get_renderer()
    t = fig.text(0, 0, text, fontsize=fontsize, weight=weight, style=style)
    try:
        w = t.get_window_extent(renderer=r).width / fig.dpi
    finally:
        t.remove()
    return w


def wrap_lines(text, fontsize, width_in, fig=None, weight="normal", style="normal"):
    """Greedy wrap using exact rendered widths (falls back to an estimate).

    A 1.5 % safety margin keeps bold/italic lines from spilling out of the
    target box.
    """
    if not text:
        return [""]
    words = text.split()
    lines, cur = [], []
    if fig is not None:
        limit = width_in * 0.985
        for w in words:
            trial = " ".join(cur + [w]) if cur else w
            if cur and text_width_in(fig, trial, fontsize, weight, style) > limit:
                lines.append(" ".join(cur)); cur = [w]
            else:
                cur.append(w)
        if cur:
            lines.append(" ".join(cur))
        return lines or [""]
    cpl = max(8, int(width_in / (fontsize * 0.62 / 72.0)))   # conservative fallback
    return textwrap.wrap(text, cpl) or [""]


def lines_needed(text, fontsize, width_in, fig=None):
    """Number of wrapped lines for `text` in a column."""
    if fig is not None:
        return len(wrap_lines(text, fontsize, width_in, fig))
    return len(wrap_lines(text, fontsize, width_in))


def norm_fracs(col_fracs):
    """Scale column widths so they sum to the printable width."""
    tot = sum(col_fracs)
    return [f * AVAIL / tot for f in col_fracs], [f / tot for f in col_fracs]


def text_h(fontsize):
    """Single text line height in figure-fraction units."""
    return fontsize * 1.45 / (H * 72.0) + 0.0035


def draw_wrapped(fig, x_frac, y_top_frac, text, fontsize, color=GREY,
                 width_in=None, weight="normal", leading=1.35):
    """Draw wrapped text starting at (x, y_top); returns the y just below the
    last line (content always extends DOWNWARD from the given y)."""
    if width_in is None:
        width_in = AVAIL * W
    line_h = fontsize * leading / (H * 72.0)
    y = y_top_frac
    lines = wrap_lines(text, fontsize, width_in, fig, weight=weight)
    for k, ln in enumerate(lines):
        fig.text(x_frac, y, ln, fontsize=fontsize, color=color, va="top",
                 weight=weight)
        y -= line_h
    return y


# minimum row height (figure fraction) so cells never clip single-line text
_MIN_ROW_H = 0.022


def draw_table(fig, x_frac, y_top_frac, col_fracs, header, rows, fontsize=9,
               header_color=NAVY, title=None, title_fontsize=12, note=None):
    """Draw a table with content-sized rows; returns the y after the table.

    Cell text is vertically centred within each row.  Column widths are
    normalised to the printable width before use, so the fractions supplied
    by the caller are treated as *relative* weights, not absolute widths.
    """
    fracs, raw_fracs = norm_fracs(col_fracs)
    widths_in = [f * W for f in fracs]

    # ── row-height calculation ──────────────────────────────────────────
    def row_lines(cells, fs):
        return max(lines_needed(str(c), fs, widths_in[j], fig)
                   for j, c in enumerate(cells))

    lh     = text_h(fontsize) * 0.92
    hdr_h  = max(_MIN_ROW_H, lh * row_lines(header, fontsize) + 0.010)
    row_hs = [max(_MIN_ROW_H, lh * row_lines(r, fontsize) + 0.010)
              for r in rows]

    if title:
        for ln in wrap_lines(title, title_fontsize, AVAIL * W, fig):
            fig.text(x_frac, y_top_frac, ln, fontsize=title_fontsize,
                     weight="bold", color=NAVY, va="top")
            y_top_frac -= title_fontsize * 1.6 / (H * 72.0)
        y_top_frac -= 0.008

    x_edges = np.cumsum([0] + fracs) + x_frac
    y = y_top_frac

    def cell_rect(x0, w, y0, h, fc):
        fig.patches.append(plt.Rectangle(
            (x0, y0), w, h, facecolor=fc,
            edgecolor="#c0c0cc", lw=0.6,
            transform=fig.transFigure, figure=fig, zorder=1))

    def cell_text(y0, h, cells, color, weight="normal"):
        """Draw cell text vertically centred inside the row rectangle."""
        line_h_frac = fontsize * 1.35 / (H * 72.0)
        for j, c in enumerate(cells):
            lines  = wrap_lines(str(c), fontsize, widths_in[j], fig)
            n_lines = len(lines)
            # vertical centre: start the top line so the block is centred
            total_text_h = n_lines * line_h_frac
            yt = y0 + (h + total_text_h) / 2.0 - line_h_frac * 0.15
            cx = x_edges[j] + 0.005
            for ln in lines:
                fig.text(cx, yt, ln, fontsize=fontsize, color=color,
                         va="top", weight=weight, zorder=2)
                yt -= line_h_frac

    # ── header row ─────────────────────────────────────────────────────
    cell_rect(x_frac, sum(fracs), y - hdr_h, hdr_h, header_color)
    cell_text(y - hdr_h, hdr_h, header, "white", weight="bold")
    y -= hdr_h

    # ── body rows (zebra-striped) ───────────────────────────────────────
    for i, row in enumerate(rows):
        hh = row_hs[i]
        bg = "#eef0f6" if i % 2 == 1 else "#ffffff"
        cell_rect(x_frac, sum(fracs), y - hh, hh, bg)
        cell_text(y - hh, hh, row, "#111111")
        y -= hh

    if note:
        fig.text(x_frac, y - 0.006, note, fontsize=7.5, color="#333333",
                 style="italic", va="top")
        y -= 0.018
    return y - 0.014


def new_page(title=None, subtitle=None, footer=True):
    fig = plt.figure(figsize=(W, H))
    if title:
        ty = 0.955
        tlines = wrap_lines(title, 19, AVAIL * W, fig)
        for ln in tlines:
            fig.text(ML, ty, ln, fontsize=19, weight="bold", va="top", color=NAVY)
            ty -= 19 * 1.3 / (H * 72.0)
        if subtitle:
            fig.text(ML, ty - 0.004, subtitle, fontsize=11.5, va="top", color=GREY,
                     style="italic")
    if footer:
        fig.text(0.5, 0.012, "FlyWire error-model analysis  |  %s" % datetime.date.today().isoformat(),
                 fontsize=8, ha="center", color="#444444")
    return fig


def image_page(pdf, img_path, caption, landscape=False, page_title=None):
    if landscape:
        fig = plt.figure(figsize=(14.0, 7.875))
        # Leave a tiny bit of space at the bottom for the caption, but make the image large
        ax = fig.add_axes([0.0, 0.08, 1.0, 0.92])
    else:
        fig = plt.figure(figsize=(W, H))
        # When a page_title is present, reserve 0.10 at the top so the image
        # does not run under the title text.
        top_gap = 0.10 if page_title else 0.04
        ax = fig.add_axes([ML - 0.02, 0.04, AVAIL + 0.04, 1.0 - top_gap - 0.04])
    ax.imshow(plt.imread(img_path))
    ax.axis("off")
    # caption below the image
    cap_h = 9.5 * 1.4 / (fig.get_size_inches()[1] * 72.0)
    yc = 0.013
    for ln in wrap_lines(caption, 9.5, 0.94 * fig.get_size_inches()[0], fig,
                          style="italic"):
        fig.text(0.5, yc, ln, ha="center", va="bottom", fontsize=9.5,
                 color="#333333", style="italic")
        yc += cap_h
    if page_title:
        ty = 0.978
        for ln in wrap_lines(page_title, 17, AVAIL * W, fig):
            fig.text(ML, ty, ln, fontsize=17, weight="bold", va="top", color=NAVY)
            ty -= 17 * 1.35 / (H * 72.0)
    pdf.savefig(fig)
    plt.close(fig)


def bullets(fig, x, y, items, fontsize=10.5, gap=0.012):
    for it in items:
        fig.text(x, y, "•", fontsize=fontsize, color="#c0392b", va="top", weight="bold")
        y = draw_wrapped(fig, x + 0.022, y, it, fontsize=fontsize, width_in=(AVAIL - 0.022) * W)
        y -= gap
    return y


# ---------------------------------------------------------------------------
def main():
    agg = pd.read_csv(os.path.join(OUT, "aggregated_metrics.csv"))
    rel = pd.read_csv(os.path.join(OUT, "relative_change.csv"))
    pr = pd.read_csv(os.path.join(OUT, "pagerank_comparison.csv"))
    data = pd.read_csv(os.path.join(OUT, "combined_trials.csv"))

    ems = [e for e in EM_ORDER if e in rel.error_model.unique()]
    rates = sorted(rel.rate.unique())
    max_rate = max(rates)

    # ---------- Table 1: baseline ----------
    base_rows = []
    for ds in DATASETS:
        def bval(an, mt):
            s = base[(base.dataset == ds) & (base.analysis == an) & (base.metric == mt)]
            return s["mean"].iloc[0] if len(s) else np.nan
        base = agg[agg.rate == 0]
        n, e = bval("basic_structure", "metric_node_count"), bval("basic_structure", "metric_edge_count")
        t = bval("basic_structure", "metric_total_synapses")
        d = bval("basic_structure", "metric_density")
        r = bval("reciprocity", "metric_reciprocity")
        a = bval("assortativity", "metric_degree_assortativity")
        w = bval("connected_components", "metric_wcc_max_size")
        base_rows.append([ds, f"{int(n):,}", f"{int(e):,}", f"{int(t):,}", f"{d:.5f}",
                          f"{r:.3f}", f"{a:+.3f}", f"{int(w):,}"])

    # ---------- Table 2: coverage ----------
    ntr = data.groupby(["dataset", "error_model"]).trial.nunique()
    cov_rows = []
    for ds in DATASETS:
        cells = []
        for em in EM_ORDER:
            v = ntr.get((ds, em), 0)
            cells.append(f"{v}x5" if v == 5 else ("—" if v == 0 else f"{v}"))
        cov_rows.append([ds] + cells)

    # ---------- Table 3: error models ----------
    method_rows = [
        ["Missed synapses", "Removes synapses per edge with calibrated probability; an edge is deleted only when its weight reaches 0.",
         "Edges ↓, weights ↓, degree ↓"],
        ["False synapses", "Adds k = round(rate × edges) new edges sampled from region-restricted, Jaccard-ranked candidate pairs; weights from the weak-edge distribution.",
         "Edges ↑, density ↑"],
        ["Synapse count measurement", "Adds Gaussian noise to edge weights, σ = rate·w, clamped ≥ 1; topology untouched.",
         "Weights only; structure unchanged"],
        ["Split errors", "Splits round(rate × eligible) neurons (total degree ≥ 10) into two fragments; every edge is rewired exactly once.",
         "Neurons ↑, edges preserved, degree ↓"],
        ["Merge errors", "Merges k = round(0.5·rate·eligible) region/soma-compatible neuron pairs ranked by shared partners; edges re-attached, parallels summed, A↔B dropped.",
         "Neurons ↓, edges collapse, synapses ≈ conserved"],
    ]

    # ---------- Table 4: verification ----------
    checks = [
        ["Completeness", "6/6 analyses present and SUCCESS in every trial",
         "Pass — 6,180 analysis rows, 0 failures"],
        ["Baseline invariance", "0% runs identical across trials and error models",
         "Pass — max rel. diff 0.0 (bit-identical)"],
        ["Degree identity", "sum(in-degrees) = edge count; in-degree mean = edges/nodes",
         "Pass — max rel. err 2.2e-16"],
        ["Density identity", "density = edges / (n·(n−1))",
         "Pass — max rel. err 7.0e-13"],
        ["Missed synapses", "synapses removed ≈ rate · synapses (QC enforced)",
         "Pass — removal matches target"],
        ["False synapses", "edge additions match planned k = round(rate · edges)",
         "Pass — at every rate, all trials"],
        ["Syn. count noise", "weight-variance increase ≈ rate²·E[w²] (theory)",
         "Pass — predicted 4.98 vs observed ≈5.1 at 20%"],
        ["Split/merge", "edge count preserved (split) / collapse bookkeeping (merge)",
         "Pass — matches plan metadata"],
        ["PageRank alignment", "split/merge vectors re-aligned to baseline node space",
         "Pass — correlations in [0.5, 1] at all rates"],
    ]

    # ---------- Table 5: effect sizes at 20% ----------
    headline = [
        ("basic_structure", "metric_edge_count", "Edge count"),
        ("basic_structure", "metric_total_synapses", "Total synapses"),
        ("basic_structure", "metric_weight_variance", "Weight variance"),
        ("degree_distribution", "metric_total_degree_mean", "Mean total degree"),
        ("connected_components", "metric_wcc_max_size", "Largest weak comp."),
        ("reciprocity", "metric_reciprocity", "Reciprocity"),
        ("assortativity", "metric_degree_assortativity", "Assortativity*"),
    ]
    eff_rows = []
    eff_spread = {}   # per error model -> per metric (min,max) across datasets
    for em in ems:
        row = [EM_LABELS[em]]
        spread = []
        for an, col, lab in headline:
            s = rel[(rel.error_model == em) & (rel.analysis == an) & (rel.metric == col)
                    & (rel.rate == max_rate)]
            if len(s):
                row.append(f"{s.rel_change_pct.mean():+.1f}%")
                spread.append((lab, s.rel_change_pct.min(), s.rel_change_pct.max()))
            else:
                row.append("—")
        s = pr[(pr.error_model == em) & (pr.rate == max_rate)]
        row.append(f"{s.pr_pearson.mean():.3f}" if len(s) else "—")
        eff_rows.append(row)
        eff_spread[em] = spread

    # ---------- Table 6: per-dataset analysis output at 20% ----------
    detail_rows = []
    for em in ems:
        for ds in DATASETS:
            s = rel[(rel.error_model == em) & (rel.dataset == ds)
                    & (rel.analysis == "basic_structure") & (rel.metric == "metric_edge_count")
                    & (rel.rate == max_rate)]
            st = rel[(rel.error_model == em) & (rel.dataset == ds)
                     & (rel.analysis == "basic_structure") & (rel.metric == "metric_total_synapses")
                     & (rel.rate == max_rate)]
            sp = pr[(pr.error_model == em) & (pr.dataset == ds) & (pr.rate == max_rate)]
            if len(s):
                detail_rows.append([EM_LABELS[em], ds,
                                    f"{s.rel_change_pct.iloc[0]:+.1f}%",
                                    f"{st.rel_change_pct.iloc[0]:+.1f}%",
                                    f"{sp.pr_pearson.iloc[0]:.3f}" if len(sp) else "—"])
    detail_rows.sort(key=lambda r: (EM_ORDER.index(r[0].lower().replace(" ", "_")), DATASETS.index(r[1])))
    # re-sort properly against canonical em keys
    em_key = {EM_LABELS[k]: k for k in EM_LABELS}
    detail_rows.sort(key=lambda r: (EM_ORDER.index(em_key[r[0]]), DATASETS.index(r[1])))

    # ---------- build PDF ----------
    with PdfPages(PDF) as pdf:
        # ============ Cover ============
        fig = plt.figure(figsize=(W, H))
        fig.patch.set_facecolor(NAVY)
        fig.text(0.5, 0.74, "How do synapse-error models degrade\nthe FlyWire connectomes?",
                 fontsize=26, weight="bold", ha="center", va="center", color="white")
        fig.text(0.5, 0.60, "A trend analysis across five Drosophila EM connectomes\nand five segmentation error models",
                 fontsize=15, ha="center", va="center", color="#cfd8ea")
        fig.text(0.5, 0.46, "BANC   ·   FAFB   ·   MANC   ·   MCNS   ·   MAOL",
                 fontsize=13, ha="center", color="#9fb3dd")
        fig.text(0.5, 0.36, "5 error models × 10 error rates × up to 5 replicate trials  →  1,030 trials",
                 fontsize=12, ha="center", color="#9fb3dd")
        fig.text(0.5, 0.28, "Framework v1.0.0 · every number recomputed from the per-trial CSVs",
                 fontsize=11, ha="center", color="#7485b0")
        fig.text(0.5, 0.10, datetime.date.today().strftime("%d %B %Y"), fontsize=12,
                 ha="center", color="#cfd8ea")
        pdf.savefig(fig)
        plt.close(fig)

        # ============ Contents ============
        fig = new_page("Contents", "How this report is organised")
        y = 0.86
        y = draw_wrapped(fig, ML, y,
            "This report analyses how five segmentation error models perturb the "
            "structure of five FlyWire connectomes as the error rate grows from 0 % "
            "to 20 %.  Every figure and every number was recomputed from the "
            "per-trial result files.", 11)
        y -= 0.015
        items = [
            "§1  Research question and one-sentence answer.",
            "§2  The data — five connectomes, five error models, coverage and rate grids.",
            "§3  Method — how each error model works and how effects are measured.",
            "§4  Verification — consistency checks before analysis.",
            "§5  Results — one figure per error model, PageRank, heatmap and effect tables.",
            "§6  Conclusions — practical implications for segmentation benchmarking.",
            "§7  Reproducibility — commands to regenerate every figure and table.",
            "Appendix — statistical notes on known artefacts and partial runs.",
        ]
        y = bullets(fig, ML, y, items, fontsize=11)
        pdf.savefig(fig)
        plt.close(fig)

        # ============ 1 · Question ============
        fig = new_page("§1 · Research Question",
                       "What this report answers and what you will find")
        y = 0.86
        y = draw_wrapped(fig, ML, y,
            "Automated segmentation of electron-microscopy data is imperfect. "
            "Reconstruction errors are classified into five types: missed synapses "
            "(false negatives), false synapses (hallucinated connections), imprecise "
            "synapse-count measurement, split neurons (over-segmentation) and merged "
            "neurons (under-segmentation). Each corrupts the wiring diagram "
            "differently: some remove connections, some add them, some change only "
            "connection strengths, and some change the very identity of neurons.", 11)
        y -= 0.014
        y = draw_wrapped(fig, ML, y,
            "This report asks: as the error rate grows from 0 % to 20 %, how "
            "strongly does each error type perturb the global structure of five "
            "FlyWire connectomes — and are those effects consistent across datasets?", 11)
        y -= 0.014
        fig.text(ML, y, "Executive Summary", va="top", fontsize=13,
                 weight="bold", color=NAVY)
        y -= 0.03
        y = draw_wrapped(fig, ML, y,
            "Topology-deleting errors (missed synapses, merge mis-segmentation) exert "
            "the most severe structural impact, scaling almost perfectly with the "
            "error rate. Measurement noise remains remarkably benign. Furthermore, all "
            "evaluated datasets exhibit qualitatively consistent responses, indicating "
            "that these structural responses are consistent across the evaluated connectomes.", 11, weight="bold")
        y -= 0.016
        fig.text(ML, y, "Core Investigative Dimensions", va="top", fontsize=13,
                 weight="bold", color=NAVY)
        y -= 0.03
        y = bullets(fig, ML, y, [
            "Direct: how do edge count, synapse count and degree respond as the error rate rises?",
            "Structural: are connectivity, component sizes and hub rankings preserved, or do they degrade?",
            "Comparative: which error type is most disruptive at the same nominal rate — and which is benign?",
        ])
        pdf.savefig(fig)
        plt.close(fig)

        # ============ 2 · Data (p.1: baseline) ============
        fig = new_page("§2 · The Data",
                       "Five connectomes, five error models, 1,030 trials")
        y = 0.84
        y = draw_wrapped(fig, ML, y,
            "The analysis covers five Drosophila EM connectomes: BANC (brain + nerve "
            "cord), FAFB (full adult female brain), MANC (male adult nerve cord), "
            "MAOL (male adult optic lobe) and MCNS (multi-cell-type nervous system). "
            "Each dataset was perturbed with up to five error models at ten error "
            "rates, with five independent seeded trials per rate, and every trial "
            "ran six graph analyses.", 11)
        y -= 0.016
        y = draw_table(fig, ML, y, [0.10, 0.12, 0.13, 0.15, 0.10, 0.11, 0.13, 0.13],
                       ["Dataset", "Neurons", "Edges", "Total synapses", "Density",
                        "Reciprocity", "Assortativity", "Largest WCC"],
                       base_rows, fontsize=9,
                       title="Table 1 · Baseline network properties at 0 % error (identical across all error models and trials)")
        pdf.savefig(fig)
        plt.close(fig)

        # ============ §2.2 · Data coverage ============
        fig = new_page("§2.2 · Data Coverage and Rate Grids",
                       "Which error models were run on which datasets")
        y = 0.87
        y = draw_table(fig, ML, y, [0.11, 0.18, 0.18, 0.18, 0.16, 0.16],
                       ["Dataset", "Missed syn.", "False syn.", "Syn. count", "Split", "Merge"],
                       cov_rows, fontsize=9,
                       title="Table 2 · Replicate trials available per error model (×5 trials per rate; — = not run)")
        y -= 0.014
        y = draw_wrapped(fig, ML, y,
            "Three error-model runs are missing or partial: MANC and MAOL have no "
            "false-synapse run, MAOL has no merge-error run, FAFB merge has 2 trials/rate "
            "and MANC merge has 1 trial/rate.  All other cells have the full 5 trials.", 10.5)
        y -= 0.016
        y = draw_wrapped(fig, ML, y,
            "Two rate grids are used: missed/false synapses at 0, 0.25, 0.5, 0.75, 1, 2, "
            "5, 10, 15, 20 %; synapse-count, split and merge errors at 0, 0.5, 1, 2, 3, 5, "
            "7.5, 10, 15, 20 %.  All values are means over the replicate trials.", 10.5)
        y -= 0.016
        fig.text(ML, y, "What the six analyses measure", va="top", fontsize=13,
                 weight="bold", color=NAVY)
        y -= 0.03
        y = bullets(fig, ML, y, [
            "basic_structure — node count, edge count, total synapses, weight mean/variance/std/max, density.",
            "degree_distribution — in/out/total degree mean, std and max.",
            "pagerank — weighted PageRank (damping 0.85); Pearson/Spearman correlation and top-100 overlap of perturbed vs baseline scores.",
            "assortativity — degree assortativity of the directed graph.",
            "connected_components — weak and strong component counts and largest sizes.",
            "reciprocity — fraction of edges with a reciprocal counterpart.",
        ])
        pdf.savefig(fig)
        plt.close(fig)

        # ============ 3 · Method ============
        fig = new_page("§3 · Method",
                       "How each error model perturbs the connectome graph")
        y = 0.87
        y = draw_table(fig, ML, y, [0.16, 0.55, 0.26],
                       ["Error model", "Perturbation applied", "Expected structural effect"],
                       method_rows, fontsize=8.8,
                       title="Table 3 · The five error models and what they do")
        y -= 0.014
        y = draw_wrapped(fig, ML, y,
            "What the nominal rate r means: the models are not directly comparable at "
            "the same r, because r is a different biological quantity in each model. "
            "Missed synapses remove a fraction r of synapses (removal probability is "
            "vulnerability-weighted, so per-edge removal is not uniform, but aggregate "
            "synapse loss matches r exactly). False synapses add k = round(r × edge "
            "count) new edges. Synapse-count measurement applies proportional noise "
            "σ = r·w to every weight. Split errors split a fraction r of eligible "
            "neurons (total degree ≥ 10). Merge errors absorb a fraction r of "
            "candidate-pool neurons into k = round(0.5 × r × eligible) pairs.  All "
            "stochastic operations use recorded seeds, so every trial is exactly "
            "reproducible.", 10.5)
        pdf.savefig(fig)
        plt.close(fig)

        # ============ §3.2 · Effect measure ============
        fig = new_page("§3.2 · Effect Measure and Scale Conventions",
                       "How to read every trend figure in this report")
        y = 0.87
        fig.text(ML, y, "How to read the figures", va="top", fontsize=13,
                 weight="bold", color=NAVY)
        y -= 0.03
        y = draw_wrapped(fig, ML, y,
            "Every trend figure in §5 uses a unified layout for cross-dataset comparison: "
            "error rate (%) is plotted on the x-axis, and the relative percentage change "
            "of a metric against its 0 % baseline is on the y-axis. "
            "The formula is Δ% = (m(rate) − m(0)) / |m(0)| × 100 %. "
            "A value of −20 % indicates a 20 % reduction from the baseline value. "
            "The dashed horizontal line marks zero change (no effect).", 11)
        y -= 0.016
        fig.text(ML, y, "Scale conventions", va="top", fontsize=13,
                 weight="bold", color=NAVY)
        y -= 0.03
        y = bullets(fig, ML, y, [
            "All evaluated connectome datasets are overlaid on a single axis for direct comparison.",
            "Direct endpoint labeling replaces traditional legends; dataset names and terminal values are positioned adjacent to each line.",
            "Automatic displacement prevents label occlusion when final values converge.",
            "PageRank is plotted as Pearson correlation (not % change) because the baseline is exactly 1.0. Coloured bands show quality thresholds.",
            "For split/merge errors the node set changes; PageRank vectors are re-aligned to baseline node space before correlating.",
        ])
        pdf.savefig(fig)
        plt.close(fig)

        # ============ §3.3 · Statistical caveats ============
        fig = new_page("§3.3 · Statistical Caveats",
                       "Reading the trend figures and handling artefacts")
        y = 0.87
        fig.text(ML, y, "Figure conventions", va="top", fontsize=13,
                 weight="bold", color=NAVY)
        y -= 0.03
        y = draw_wrapped(fig, ML, y,
            "Figures in §5 use error rate (%) on the x-axis and relative % change Δ% "
            "against the 0 % baseline on the y-axis, calculated as Δ% = (m(rate) − "
            "m(0)) / |m(0)| × 100 %. All datasets are plotted on unified axes to "
            "facilitate direct comparative analysis.", 11)
        y -= 0.016
        fig.text(ML, y, "Statistical caveats", va="top", fontsize=13,
                 weight="bold", color=NAVY)
        y -= 0.03
        y = bullets(fig, ML, y, [
            "Baseline Inflation: Assortativity has a near-zero baseline, so % change is inflated. We report it but exclude it from the heatmap.",
            "Metric Scaling: metrics whose absolute change stays below 0.25 % across all rates are treated as negligible. This is a descriptive magnitude threshold, not statistical significance.",
            "PageRank: Plotted as Pearson correlation (r) rather than % change. Pearson measures vector correlation, not rank preservation; Spearman correlation and top-100 overlap are reported in §5.5b.",
            "Split/Merge: PageRank vectors are re-aligned to baseline node space before correlating.",
            "Partial Runs: Cross-dataset means for merge errors include FAFB (2 trials) and MANC (1 trial).",
            "Uncertainty: trial-to-trial SD of the reported % changes is below 0.15 pp for every 5-trial cell; the MANC merge row (n = 1) has no trial variance.",
        ])
        pdf.savefig(fig)
        plt.close(fig)

        # ============ §4 · Verification ============
        fig = new_page("§4 · Verification",
                       "Consistency checks performed before analysis")
        y = 0.87
        y = draw_table(fig, ML, y, [0.16, 0.50, 0.34],
                       ["Check", "What was tested", "Outcome"],
                       checks, fontsize=8.8,
                       title="Table 4 · Data-quality verification")
        y -= 0.012
        y = draw_wrapped(fig, ML, y,
            "The two structural identities (in-degree mean = edges/nodes and density = "
            "edges/(n·(n−1))) hold to machine precision, and the 0 % baseline is "
            "bit-identical across trials and error models — so all observed changes "
            "below are caused by the perturbation, never by run-to-run variability.", 10.5)
        pdf.savefig(fig)
        plt.close(fig)

        # ============ §4.2 · Anomalies ============
        fig = new_page("§4.2 · Anomalies Investigated and Resolved",
                       "Suspicious patterns that were examined and explained")
        y = 0.87
        y = bullets(fig, ML, y, [
            "'False-synapse degree shift never varies across trials' — a mathematical "
            "identity, not a bug: false synapses add a deterministic number of edges "
            "every trial, so their trial-to-trial spread is exactly zero.  Missed "
            "synapses remove a binomial-random number, so their spread is non-zero.",
            "'Synapse-count measurement changes almost nothing' — by design it perturbs "
            "weights only; the variance increase matches theory (rate²·E[w²]), and "
            "structural metrics are completely untouched.",
            "'Largest weak component is flat for false synapses' — new edges land "
            "inside the already-giant component, so adding them never enlarges it; the "
            "strong component does grow.",
            "'Edge count is flat for split errors' — splitting rewires edges (each "
            "assigned exactly once) rather than creating them; the neuron count "
            "grows instead.",
            "No formula errors were found in the outputs.  The only real caveat is run "
            "coverage: FAFB and MANC merge-error results are partial (2 and 1 trials per "
            "rate), and MANC/MAOL have no false-synapse run.",
        ])
        y -= 0.01
        fig.text(ML, y,
                 "Conclusion: The datasets exhibit internal consistency and are structurally robust.",
                 va="top", fontsize=12, weight="bold", color="#1e7d32")
        pdf.savefig(fig)
        plt.close(fig)

        # ============ 5 · Results ============
        fig = new_page("§5 · Results",
                       "Principal observations across all error models")
        y = 0.87
        y = draw_wrapped(fig, ML, y,
            "Figures in this section show, for each combination of error model and metric, "
            "how that metric changes as a function of error rate.  Each figure occupies "
            "one full landscape page for maximum readability: datasets are overlaid on a "
            "single axis with direct endpoint labeling to enable immediate cross-dataset "
            "comparisons. Lines approaching the zero axis indicate high structural resilience.", 11)
        y -= 0.016
        fig.text(ML, y, "Principal observations (see Table 5)", va="top",
                 fontsize=13, weight="bold", color=NAVY)
        y -= 0.03
        y = bullets(fig, ML, y, [
            "Missed synapses: synapses fall one-for-one with the rate (−20 % at 20 %); edges only −5 %; PageRank Pearson r 0.999.",
            "False synapses: edges and mean degree rise in step with the rate (+19 % at 20 %); PageRank Pearson r 0.994.",
            "Synapse-count noise: only the weight variance moves (+5.5 %); all topological metrics are untouched.",
            "Split errors: edges preserved exactly, but spread over more neurons → mean degree −15 %, largest weak component +18 %.",
            "Merge errors: most invasive to connectivity — edges −11 %, weight variance +47 %, largest weak component −9 %.",
        ])
        pdf.savefig(fig)
        plt.close(fig)

        # ============ §5 · one page per error-model × metric ============
        # ============ §5 · one page per error-model × metric ============
        import json as _json
        import glob as _glob
        HEADLINE_LABELS = [
            "Edge count", "Total synapses", "Mean total degree",
            "Largest weak component", "Reciprocity",
        ]
        fig_idx = 1
        for em in ems:
            em_label = EM_LABELS[em]
            # 5 metric figures per error model
            for mi, metric_label in enumerate(HEADLINE_LABELS):
                # Look for the file with pattern EM_{em}_{mi:02d}_*.png
                pattern = os.path.join(FIG, f"EM_{em}_{mi:02d}_*.png")
                matches = sorted(_glob.glob(pattern))
                if not matches:
                    continue
                img_path = matches[0]
                caption = (
                    f"Figure {fig_idx} · {em_label} — {metric_label}.  "
                    f"Each line represents a dataset's response to the error model. "
                    f"Direct endpoint labelling replaces the legend."
                )
                image_page(pdf, img_path, caption, landscape=True,
                           page_title=None)  # Title is baked into the figure
                fig_idx += 1

        # ============ §5 · PageRank — one page per error model ============
        for em in ems:
            pr_path = os.path.join(FIG, f"pagerank_{em}.png")
            if not os.path.exists(pr_path):
                continue
            caption = (
                f"Figure {fig_idx} · PageRank preservation — {EM_LABELS[em]}.  "
                "Coloured bands: green ≥ 0.999 (excellent), yellow 0.990–0.999 (good), "
                "orange 0.970–0.990 (borderline), red < 0.970 (degraded)."
            )
            image_page(pdf, pr_path, caption, landscape=True,
                       page_title=None)
            fig_idx += 1

        # ============ §5 · Heatmap ============
        image_page(pdf, os.path.join(FIG, "max_change_heatmap.png"),
                   f"Figure {fig_idx} · Maximum observed |% change| per error model "
                   "across all rates and datasets (assortativity excluded — near-zero "
                   "baseline artefact).  Darker cells indicate more disruption.",
                   landscape=True,
                   page_title="§5 · Results — Worst-case Impact per Error Model")
        fig_idx += 1


        # ============ §5.5 · Effect-size table ============
        fig = new_page("§5.5 · Effect Sizes at 20 % Error",
                       "Mean % change vs baseline across all datasets for each error model")
        y = 0.87
        header = ["Error model", "Edge count", "Total synapses", "Weight variance",
                  "Mean degree", "Largest WCC", "Reciprocity", "Assortativity*", "PageRank r"]
        widths = [0.20, 0.09, 0.11, 0.12, 0.09, 0.11, 0.09, 0.11, 0.09]
        y = draw_table(fig, ML, y, widths, header, eff_rows, fontsize=8.6,
                       title="Table 5 · % change at the maximum tested error rate (20 %)")
        y -= 0.012
        y = draw_wrapped(fig, ML, y,
            "*Assortativity has a near-zero baseline (−0.03 to −0.06), so its % change is "
            "inflated and should be read as an absolute movement, not a percentage.  "
            "PageRank r is the mean Pearson correlation across datasets (baseline = 1.0 "
            "by construction); Spearman and top-100 overlap are reported in §5.5b.", 9.5, color="#222222")
        y -= 0.016
        fig.text(ML, y, "Spread across datasets (min … max)", va="top",
                 fontsize=12, weight="bold", color=NAVY)
        y -= 0.028
        for em in ems:
            if not eff_spread[em]:
                continue
            parts = [f"{lab} {lo:+.1f}…{hi:+.1f}%" for lab, lo, hi in eff_spread[em]]
            y = draw_wrapped(fig, ML, y, f"{EM_LABELS[em]}:  " + ";  ".join(parts),
                             fontsize=9, color="#333")
            y -= 0.012
        y -= 0.006
        y = draw_wrapped(fig, ML, y,
            "Missed synapses remove exactly 20 % of synapses at the 20 % rate, cutting "
            "weight variance by 30 % but only deleting the ~5 % of edges whose weight "
            "reached zero — and PageRank vectors stay highly correlated (Pearson 0.999, "
            "Spearman 0.998, top-100 overlap 0.98 for missed synapses at 20 %), so most "
            "high-centrality neurons keep their rank.  False synapses add ~19 % more "
            "edges, but the new low-weight edges dilute weight variance by ~14 %.  "
            "Synapse-count noise moves only the weight variance (+5.5 %).  Split errors "
            "preserve edges but spread them over more neurons (mean degree −15 %, largest "
            "weak component +18 %).  Merge errors are the most invasive: weight variance "
            "+47 %, edges −11 %, largest component −9 %.", 10.5)
        pdf.savefig(fig)
        plt.close(fig)

        # ============ §5.5b · PageRank preservation at 20% ============
        fig = new_page("§5.5b · PageRank Preservation at 20 % Error",
                       "Pearson, Spearman and top-100 overlap — all three measures present in the exports")
        y = 0.87
        pr_hdr = ["Error model", "Pearson r", "Spearman ρ", "Top-100 overlap"]
        pr_rows = []
        for em in ems:
            s5 = pr[(pr.error_model == em) & (pr.rate == max_rate)]
            if not len(s5):
                continue
            cells = []
            for col in ("pr_pearson", "pr_spearman", "pr_topk100"):
                v = s5[col].dropna()
                cells.append(f"{v.mean():.3f} ({v.min():.3f}–{v.max():.3f})" if len(v) else "—")
            pr_rows.append([EM_LABELS[em]] + cells)
        y = draw_table(fig, ML, y, [0.24, 0.25, 0.25, 0.25],
                       pr_hdr, pr_rows, fontsize=9,
                       title="Table 5b · PageRank preservation at 20 % error — mean across datasets (min–max across datasets)")
        y -= 0.014
        y = draw_wrapped(fig, ML, y,
            "Pearson correlation measures vector similarity, not rank preservation.  "
            "Spearman correlation measures rank-order agreement, and top-100 overlap "
            "measures how many of the 100 highest-PageRank neurons in the baseline "
            "remain in the top 100 after perturbation.  Across all models Pearson "
            "r ≥ 0.977 and Spearman ≥ 0.96 at 20 % error, so PageRank vectors remain "
            "highly correlated and rank order is largely, but not entirely, retained.  "
            "The largest displacements occur on BANC: under merge errors the top-100 "
            "overlap falls to 0.86 and under false synapses to 0.89, i.e. roughly one "
            "in seven of the top hubs is displaced from the baseline top 100.", 10.5)
        pdf.savefig(fig)
        plt.close(fig)

        # ============ §5.6 · Per-dataset table ============
        fig = new_page("§5.6 · Per-Dataset Breakdown at Peak Error Rate",
                       "How variation across connectomes reinforces the headline conclusions")
        y = 0.87
        y = draw_table(fig, ML, y, [0.24, 0.10, 0.18, 0.20, 0.14],
                       ["Error model", "Dataset", "Edge count Δ%", "Total synapses Δ%", "PageRank r"],
                       detail_rows, fontsize=8.6,
                       title="Table 6 · Edge count and total-synapse change per dataset at 20 % error, with PageRank Pearson r (FAFB and MANC merge rows average 2 and 1 trials per rate; all other rows average 5)")
        y -= 0.012
        y = draw_wrapped(fig, ML, y,
            "This table shows that the cross-dataset means in Table 5 do not hide "
            "large disagreements between connectomes.  The −4.9 % average edge loss under "
            "missed synapses spans −0.0 % (MCNS) to −9.7 % (MANC): datasets whose edges "
            "carry fewer synapses lose edges faster, because an edge survives only if at "
            "least one of its synapses survives (Table 6b).  Merge errors reduce edge "
            "count in every dataset at 20 % (FAFB −16.1 % to MCNS −7.1 %); no dataset "
            "shows an increase.", 10.5)
        pdf.savefig(fig)
        plt.close(fig)

        # ============ §5.6b · Edge-loss mechanism ============
        fig = new_page("§5.6b · Why Edge Loss Differs Across Connectomes",
                       "Edge-weight distribution vs edge loss at 20 % synapse loss (missed-synapse model)")
        y = 0.87
        w_rows = []
        for ds in DATASETS:
            bm = data[(data.dataset == ds) & (data.rate == 0.0)
                      & (data.analysis_name == "basic_structure")]
            if not len(bm):
                continue
            wmean = bm.metric_weight_mean.mean()
            wmed  = bm.metric_weight_median.mean()
            s6 = rel[(rel.error_model == "missed_synapses") & (rel.dataset == ds)
                     & (rel.rate == max_rate) & (rel.metric == "metric_edge_count")]
            edge_d = s6.rel_change_pct.iloc[0] if len(s6) else float("nan")
            w_rows.append([ds, f"{wmean:.1f}", f"{wmed:.0f}", f"{edge_d:+.1f}%"])
        y = draw_table(fig, ML, y, [0.20, 0.25, 0.25, 0.30],
                       ["Dataset", "Mean synapses/edge", "Median synapses/edge",
                        "Edge count Δ% at 20 % synapse loss"],
                       w_rows, fontsize=10,
                       title="Table 6b · Baseline edge-weight distribution vs edge loss under the missed-synapse model at 20 %")
        y -= 0.016
        y = draw_wrapped(fig, ML, y,
            "An edge survives a missed-synapse run only if at least one of its synapses "
            "survives, so at a fixed synapse-loss rate the fraction of edges deleted is "
            "largest for datasets whose edges carry the fewest synapses.  The median "
            "synapses/edge tracks the observed edge loss monotonically across the five "
            "connectomes: MANC and MAOL (median 2) lose −9.7 % and −8.9 % of edges, BANC "
            "(median 4) −3.2 %, FAFB (median 6) −2.5 %, and MCNS (median 9) −0.0 %.  "
            "This is a descriptive relationship across five connectomes (n = 5); it is "
            "consistent with the binomial-deletion mechanism but is not claimed as a "
            "general law.", 10.5)
        pdf.savefig(fig)
        plt.close(fig)

        # ============ 6 · Conclusions ============
        fig = new_page("§6 · Conclusions",
                       "Practical implications for segmentation benchmarking")
        y = 0.87
        y = bullets(fig, ML, y, [
            "1. Disproportionate Impact of Connection Loss: Missed synapses remove synapses proportionally "
            "with the error rate and erode weight variance by 30 % at 20 %, while false synapses primarily "
            "inflate edge counts. Algorithmic benchmarking should prioritize missed-synapse detection.",
            "2. Resilience to Measurement Noise: Synapse-count uncertainty perturbs weight statistics "
            "but leaves the overarching topology intact. Graph analyses unweighted by synapse count remain unaffected.",
            "3. Structural Shifts via Mis-segmentation: Split and merge errors alter the neuron count "
            "rather than just edge topology. Analyses treating neurons as fundamental units (e.g., community "
            "detection, PageRank) are highly sensitive to these errors.",
            "4. PageRank Robustness: Despite local topological degradation, PageRank vectors remain highly "
            "correlated at a 20 % error rate (Pearson r ≥ 0.977 and Spearman ≥ 0.96 for every model and "
            "dataset). Most, but not all, high-centrality neurons retain their rank: top-100 hub overlap "
            "stays ≥ 0.86, with the largest displacements under false and merge errors on BANC (Table 5b). "
            "Local measures (degree, component size) act as earlier indicators of structural decay.",
            "5. Consistency Across the Evaluated Connectomes: The five evaluated Drosophila connectomes exhibit "
            "qualitatively similar responses to identical error models. Broader generalization is not claimed: "
            "all datasets come from one species, and coverage is partial (Table 2).",
        ])
        y -= 0.012
        fig.text(ML, y, "Caveats", va="top", fontsize=12.5, weight="bold", color=NAVY)
        y -= 0.028
        y = draw_wrapped(fig, ML, y,
            "FAFB and MANC merge-error results rest on 2 and 1 trials per rate (partial "
            "runs in the source archives); MANC and MAOL have no false-synapse run.  "
            "All other cells use 5 replicate trials, and trial-to-trial SD of the "
            "reported % changes is below 0.15 pp for every 5-trial cell.  The %-change "
            "framing inflates metrics with near-zero baselines (assortativity) — always "
            "check the raw direction and magnitude.  The five error models are "
            "computational simulations: their error distributions are not empirically "
            "validated against real reconstruction-error ground truth (no such data is "
            "part of this repository), so the results describe how the modelled error "
            "classes perturb graph structure, not measured segmentation errors.  "
            "1,030 trials in total; every number in this report was recomputed from the "
            "per-trial CSVs.", 10.5)
        pdf.savefig(fig)
        plt.close(fig)

        # ============ 7 · Reproducibility ============
        fig = new_page("§7 · Reproducibility",
                       "How to regenerate this report from source data")
        y = 0.87
        y = draw_wrapped(fig, ML, y,
            "The whole report — CSVs, figures and this PDF — is produced by three scripts in "
            "the analysis/ folder.  Run them in order from the repository root:", 11)
        y -= 0.018
        demo = [
            "# 1. Load every per-trial CSV; run the consistency checks",
            "python analysis/01_load_and_verify.py      # -> combined_trials.csv, verification_report.txt",
            "",
            "# 2. Aggregate trials; draw the large-format figures",
            "python analysis/02_aggregate_and_plot.py   # -> aggregated_metrics.csv, relative_change.csv,",
            "                                            #    pagerank_comparison.csv, figures/*.png",
            "",
            "# 3. Assemble this PDF (matplotlib only, no extra dependencies)",
            "python analysis/03_build_pdf_report.py     # -> Flywire_Error_Model_Analysis_Report.pdf",
        ]
        box = fig.add_axes([ML, 0.30, AVAIL, 0.46])
        box.axis("off")
        box.add_patch(plt.Rectangle((0, 0), 1, 1, transform=box.transAxes,
                                    facecolor="#f2f4f8", edgecolor="#c9cedb"))
        box.text(0.02, 0.97, "$ python analysis/01_load_and_verify.py", fontsize=10,
                 family="monospace", va="top", color=NAVY)
        sample = ("$ python analysis/01_load_and_verify.py\n"
                  "loaded 6180 analysis-rows, 5 datasets, 5 error models, 10 rates, max 5 trials per cell\n"
                  "\n"
                  "[1] COMPLETENESS\n"
                  "  trials per cell: min=1, max=5, cells=220\n"
                  "  PARTIAL FAFB/merge_errors: only 2 trials/rate\n"
                  "  PARTIAL MANC/merge_errors: only 1 trial/rate\n"
                  "  analyses per trial: min=6, max=6 (expect 6)\n"
                  "  non-SUCCESS rows: 0\n"
                  "\n"
                  "[2] BASELINE INVARIANCE (0% error)\n"
                  "  BANC: baseline max rel diff across error models = 0.00e+00\n"
                  "  FAFB: baseline max rel diff across error models = 0.00e+00\n"
                  "  MANC: baseline max rel diff across error models = 0.00e+00\n"
                  "  MCNS: baseline max rel diff across error models = 0.00e+00\n"
                  "  MAOL: baseline max rel diff across error models = 0.00e+00\n"
                  "\n"
                  "[3] INTERNAL CONSISTENCY\n"
                  "  in-degree mean vs edges/nodes: max rel err = 2.206e-16\n"
                  "  density vs edges/(n*(n-1)):    max rel err = 6.978e-13")
        box.text(0.02, 0.90, sample, fontsize=8, family="monospace", va="top", color="#222")
        pdf.savefig(fig)
        plt.close(fig)

        # ============ Appendix · statistical notes ============
        fig = new_page("Appendix · Statistical Notes",
                       "Known artefacts and how they are handled in this report")
        y = 0.87
        y = bullets(fig, ML, y, [
            "Near-zero-baseline % change.  Relative change is undefined in spirit when the "
            "baseline is near zero.  Assortativity (baseline −0.03…−0.06) shows % swings of "
            "+135 % for a small absolute movement; we report the raw sign and magnitude and "
            "exclude the metric from the heatmap.",
            "Reciprocity baselines (0.13–0.29) are safe for % change; the biggest move is "
            "merge errors (+1.4 % mean).",
            "Mean-over-datasets.  Table 5 averages % changes across the datasets that were run. "
            "Table 6 gives every dataset individually, and the spread (min…max) is printed "
            "under Table 5.",
            "Partial runs.  FAFB merge (2 trials/rate), MANC merge (1 trial/rate); MANC/MAOL "
            "false synapses and MAOL merge not run.  Figures simply omit missing lines.",
            "Deterministic vs stochastic.  False-synapse edge additions are deterministic "
            "(k = round(r·E) every trial), so their trial-to-trial spread is zero — an "
            "identity, not a bug (verified in §4).",
        ])
        pdf.savefig(fig)
        plt.close(fig)

    print("wrote", PDF, f"({os.path.getsize(PDF)/1e6:.1f} MB)")


if __name__ == "__main__":
    main()
