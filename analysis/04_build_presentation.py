#!/usr/bin/env python3
"""Build a professional 5-minute presentation PDF (matplotlib-only).

Target: 12 slides, matching the exact flow of the original LaTeX deck.
  1. Cover
  2. Experimental Design
  3. Overview — Worst-Case Impact
  4. Missed Synapses
  5. False Synapses
  6. Synapse-Count Noise
  7. Split Errors
  8. Merge Errors
  9. PageRank Robustness
 10. What the Results Mean
 11. Analysis — What the Results Tell Us
 12. Takeaway and Next Steps
"""
import datetime
import os
import textwrap
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.patches import FancyBboxPatch

OUT = "/home/surjit/Desktop/flywire/v1/analysis"
FIG = os.path.join(OUT, "figures")
PDF = os.path.join(OUT, "antigravity_presentation.pdf")

# ── design tokens ───────────────────────────────────────────────────────────
W, H = 16.0, 9.0                       # widescreen 16:9
NAVY      = "#0F1B2D"
NAVY_MID  = "#1A2D47"
ACCENT    = "#0B6E99"
ACCENT2   = "#C4451D"
WHITE     = "#FFFFFF"
LIGHT_BG  = "#F5F7FA"
GREY      = "#3B4858"
LIGHT_GRY = "#8899AA"
SLIDE_BG  = "#FFFFFF"
OKGREEN   = "#4A9E6F"

MX = 0.06

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "figure.facecolor": SLIDE_BG,
    "savefig.facecolor": SLIDE_BG,
})

def _tw(fig, text, fs, weight="normal", style="normal"):
    r = fig.canvas.get_renderer()
    t = fig.text(0, 0, text, fontsize=fs, weight=weight, style=style)
    try:
        return t.get_window_extent(renderer=r).width / fig.dpi
    finally:
        t.remove()

def wrap(text, fs, w_in, fig, weight="normal", style="normal"):
    out = []
    for seg in str(text).split("\n"):
        words, cur = seg.split(), []
        lines = []
        lim = w_in * 0.98
        for wd in words:
            trial = " ".join(cur + [wd]) if cur else wd
            if cur and _tw(fig, trial, fs, weight, style) > lim:
                lines.append(" ".join(cur)); cur = [wd]
            else:
                cur.append(wd)
        if cur:
            lines.append(" ".join(cur))
        out.extend(lines or [""])
    return out

def draw_text(fig, x, y, text, fs, color=GREY, weight="normal",
              width=None, leading=1.40, ha="left", style="normal"):
    if width is None: width = (1.0 - 2 * MX) * W
    lh = fs * leading / (H * 72.0)
    for ln in wrap(text, fs, width, fig, weight, style):
        fig.text(x, y, ln, fontsize=fs, color=color, va="top",
                 weight=weight, ha=ha, style=style)
        y -= lh
    return y

def bullet(fig, x, y, items, fs=13, gap=0.012, bullet_color=ACCENT2,
           text_color=GREY, width=None):
    if width is None: width = (1.0 - 2 * MX - 0.025) * W
    for it in items:
        fig.text(x, y, "▸", fontsize=fs, color=bullet_color, va="top", weight="bold")
        y = draw_text(fig, x + 0.018, y, it, fs, color=text_color, width=width)
        y -= gap
    return y

def slide_number(fig, n, total):
    fig.text(0.97, 0.015, f"{n} / {total}", fontsize=9, color=LIGHT_GRY, ha="right", va="bottom")

def footer_bar(fig):
    fig.patches.append(plt.Rectangle((0, 0), 1, 0.035, facecolor=LIGHT_BG, transform=fig.transFigure, figure=fig, zorder=0))
    fig.text(0.03, 0.015, "FlyWire Connectome Research — Progress Update", fontsize=8, color=LIGHT_GRY, va="bottom")

def section_title(fig, title, subtitle=None):
    ty = 0.94
    for ln in wrap(title, 22, (1.0 - 2 * MX) * W, fig, weight="bold"):
        fig.text(MX, ty, ln, fontsize=22, color=NAVY, weight="bold", va="top")
        ty -= 22 * 1.35 / (H * 72.0)
    fig.patches.append(plt.Rectangle((MX, ty - 0.004), 0.88, 0.004, facecolor=ACCENT, transform=fig.transFigure, figure=fig))
    ty -= 0.020
    if subtitle:
        fig.text(MX, ty, subtitle, fontsize=12, color=LIGHT_GRY, va="top", style="italic")
        ty -= 0.035
    return ty

def add_figure(fig, img_path, rect):
    ax = fig.add_axes(rect)
    ax.imshow(plt.imread(img_path))
    ax.axis("off")
    return ax

def value_box(fig, x, y, label, value, color=ACCENT, w=0.14, h=0.10):
    fig.patches.append(FancyBboxPatch((x, y - h), w, h, boxstyle="round,pad=0.006",
        facecolor=LIGHT_BG, edgecolor="#D0D8E0", linewidth=0.8, transform=fig.transFigure, figure=fig, zorder=1))
    fig.text(x + w / 2, y - 0.015, value, fontsize=16, weight="bold", color=color, ha="center", va="top", zorder=2)
    fig.text(x + w / 2, y - h + 0.012, label, fontsize=8, color=LIGHT_GRY, ha="center", va="bottom", zorder=2)

def draw_table(fig, x, y, col_ws, header, rows, fs=10.5, hdr_bg=NAVY):
    total_w = sum(col_ws) if sum(col_ws) < 1.0 else 1.0 - 2 * MX
    ws = [c / sum(col_ws) * total_w for c in col_ws]
    xs = np.cumsum([0] + ws) + x
    lh = fs * 1.55 / (H * 72.0)
    rh = lh + 0.012
    fig.patches.append(plt.Rectangle((x, y - rh), total_w, rh, facecolor=hdr_bg, transform=fig.transFigure, figure=fig, zorder=1))
    for j, h in enumerate(header):
        fig.text(xs[j] + 0.006, y - rh / 2, h, fontsize=fs - 1, color=WHITE, weight="bold", va="center", zorder=2)
    y -= rh
    for i, row in enumerate(rows):
        bg = "#EEF0F6" if i % 2 == 0 else WHITE
        fig.patches.append(plt.Rectangle((x, y - rh), total_w, rh, facecolor=bg, transform=fig.transFigure, figure=fig, zorder=1))
        for j, c in enumerate(row):
            clr = "#222"
            if c.startswith("+"): clr = ACCENT
            elif c.startswith("-") or c.startswith("−"): clr = ACCENT2
            fig.text(xs[j] + 0.006, y - rh / 2, str(c), fontsize=fs - 1, color=clr, va="center", zorder=2)
        y -= rh
    return y - 0.010

def block_box(fig, x, y, title, text, w, title_bg=NAVY):
    draw_text(fig, x, y, title, 13, weight="bold", color=NAVY)
    y -= 0.04
    fig.patches.append(FancyBboxPatch((x, y - 0.12), w, 0.12, boxstyle="round,pad=0.01",
        facecolor=LIGHT_BG, edgecolor=ACCENT, linewidth=1.0, transform=fig.transFigure, figure=fig, zorder=1))
    draw_text(fig, x + 0.01, y - 0.015, text, 11, width=w * W * 0.95)
    return y - 0.15

# ═══════════════════════════════════════════════════════════════════════════
def main():
    TOTAL_SLIDES = 12
    with PdfPages(PDF) as pdf:

        # ── Slide 1 · Cover ─────────────────────────────────────────────
        fig = plt.figure(figsize=(W, H))
        fig.patch.set_facecolor(NAVY)
        fig.patches.append(plt.Rectangle((0, 0.385), 1, 0.008, facecolor=ACCENT, transform=fig.transFigure, figure=fig))
        fig.text(0.5, 0.015, datetime.date.today().strftime("%d %B %Y"), fontsize=11, ha="center", color="#6688AA", va="bottom")
        fig.text(0.5, 0.78, "RESEARCH PROGRESS UPDATE", fontsize=11, ha="center", color=ACCENT, weight="bold", va="center")
        fig.text(0.5, 0.66, "How Do Reconstruction Errors\nAffect Connectome Graph Analysis?",
                 fontsize=30, ha="center", va="center", color=WHITE, weight="bold", linespacing=1.35)
        fig.text(0.5, 0.48, "As reconstruction error grows 0 → 20 %, how strongly does each error type\nperturb graph structure and downstream graph analyses?",
                 fontsize=14, ha="center", va="center", color="#9FB3DD", linespacing=1.5, style="italic")
        chip_names = ["BANC", "FAFB", "MANC", "MCNS", "MAOL"]
        cx_start = 0.5 - 0.095 * 2
        for i, cn in enumerate(chip_names):
            cx = cx_start + i * 0.095
            fig.patches.append(FancyBboxPatch((cx - 0.032, 0.29), 0.064, 0.04, boxstyle="round,pad=0.005",
                facecolor=NAVY_MID, edgecolor=ACCENT, linewidth=1.0, transform=fig.transFigure, figure=fig))
            fig.text(cx, 0.31, cn, fontsize=11, color=WHITE, ha="center", va="center", weight="bold")
        fig.text(0.5, 0.24, "5 connectomes  ×  5 error models  ×  10 error rates  ×  up to 5 trials  →  1,030 trials",
                 fontsize=12, ha="center", color="#7485B0")
        pdf.savefig(fig); plt.close(fig)

        # ── Slide 2 · Experimental Design ───────────────────────────────
        fig = plt.figure(figsize=(W, H))
        y = section_title(fig, "Experimental Design", "A systematic simulation of segmentation errors")
        footer_bar(fig); slide_number(fig, 2, TOTAL_SLIDES)
        boxes = [("Baseline\nConnectome", 0.08), ("Simulated\nReconstruction Error", 0.30),
                 ("Graph\nAnalyses", 0.55), ("Cross-Dataset\nComparison", 0.77)]
        by, bw, bh = y - 0.04, 0.17, 0.09
        for label, bx in boxes:
            fig.patches.append(FancyBboxPatch((bx, by - bh), bw, bh, boxstyle="round,pad=0.008",
                facecolor=LIGHT_BG, edgecolor=ACCENT, linewidth=1.2, transform=fig.transFigure, figure=fig))
            fig.text(bx + bw / 2, by - bh / 2, label, fontsize=11, color=NAVY, ha="center", va="center", weight="bold", linespacing=1.3)
        for i in range(3):
            ax0 = boxes[i][1] + bw + 0.003
            ax1 = boxes[i + 1][1] - 0.003
            fig.text((ax0 + ax1) / 2, by - bh / 2, "→", fontsize=20, color=ACCENT, ha="center", va="center", weight="bold")
        y = by - bh - 0.05
        kpis = [("Connectomes", "5", ACCENT), ("Error Models", "5", ACCENT),
                ("Max Error Rate", "20%", ACCENT2), ("Total Trials", "1,030", ACCENT),
                ("Analysis Rows", "6,180", ACCENT), ("Failures", "0", OKGREEN)]
        kx = MX
        for lab, val, clr in kpis:
            value_box(fig, kx, y, lab, val, color=clr, w=0.13, h=0.095)
            kx += 0.145
        y -= 0.14
        fig.patches.append(FancyBboxPatch((MX, y - 0.06), 0.88, 0.06, boxstyle="round,pad=0.006",
            facecolor="#EAF4E8", edgecolor=OKGREEN, linewidth=1.0, transform=fig.transFigure, figure=fig))
        fig.text(MX + 0.012, y - 0.03, "Reliability Checks:", fontsize=11, weight="bold", color="#2E7D32", va="center")
        draw_text(fig, MX + 0.14, y - 0.03 + 0.008, "Baseline invariance and graph identities verified — the perturbed graphs change only through the applied error model.", 11, color="#333")
        pdf.savefig(fig); plt.close(fig)

        # ── Slide 3 · Overview Worst Case ───────────────────────────────
        fig = plt.figure(figsize=(W, H))
        y = section_title(fig, "Overview — Worst-Case Impact per Error Model", "Max |% change| over all error rates; darker = more disruption")
        footer_bar(fig); slide_number(fig, 3, TOTAL_SLIDES)
        tbl_header = ["Error model", "What moves", "Max"]
        tbl_rows = [
            ["Missed", "synapses, weight variance", "−30%"],
            ["False", "edges, connectivity", "+20%"],
            ["Count noise", "weights only", "+6%"],
            ["Split", "degree, WCC/SCC", "+18%"],
            ["Merge", "edges, weights, WCC/SCC", "+47%"],
        ]
        draw_table(fig, MX, y - 0.02, [0.10, 0.18, 0.08], tbl_header, tbl_rows, fs=12)
        heatmap_path = os.path.join(FIG, "max_change_heatmap.png")
        if os.path.exists(heatmap_path):
            add_figure(fig, heatmap_path, [0.45, 0.20, 0.50, 0.65])
        fig.patches.append(FancyBboxPatch((MX, 0.12), 0.88, 0.05, boxstyle="round,pad=0.006",
            facecolor=LIGHT_BG, edgecolor=NAVY, linewidth=1.0, transform=fig.transFigure, figure=fig))
        fig.text(MX + 0.012, 0.145, "Takeaway:", fontsize=11, weight="bold", color=NAVY, va="center")
        draw_text(fig, MX + 0.08, 0.145 + 0.008, "Five distinct fingerprints — each error model is detailed on the following slides.", 11)
        pdf.savefig(fig); plt.close(fig)

        # ── Slides 4-8 · Per-Model Results ──────────────────────────────
        model_slides = [
            {
                "title": "Missed Synapses — the Synaptic Layer Shrinks",
                "subtitle": "Synapse removal: count falls one-for-one with the rate; deletions land on light edges.",
                "fig_left": os.path.join(FIG, "EM_missed_synapses_01_metric_total_synapses.png"),
                "fig_right": os.path.join(FIG, "EM_missed_synapses_00_metric_edge_count.png"),
                "cap_left": "Total synapses: Exactly −20% at 20% on every dataset.",
                "cap_right": "Edge count: Only −4.9% — losses land on light connections.",
                "takeaway": "Weighted layer erodes (variance −30.3%) but the skeleton survives; PageRank r = 0.999.",
                "slide_n": 4,
            },
            {
                "title": "False Synapses — Connectivity Is Inflated",
                "subtitle": "Hallucinated edges inflate connectivity; the weak component stays flat, the core grows.",
                "fig_left": os.path.join(FIG, "EM_false_synapses_00_metric_edge_count.png"),
                "fig_right": os.path.join(FIG, "EM_false_synapses_04_metric_scc_max_size.png"),
                "cap_left": "Edge count: +19.4% at 20% — connectivity inflated.",
                "cap_right": "Strong component: +0.6% — new edges extend the core.",
                "takeaway": "Connectivity inflates, weights dilute (−13.8%); global ranking stable (r = 0.994).",
                "slide_n": 5,
            },
            {
                "title": "Synapse-Count Noise — the Control Result",
                "subtitle": "Measurement noise is benign: only weighted statistics move.",
                "fig_left": os.path.join(FIG, "EM_synapse_count_measurement_00_metric_edge_count.png"),
                "fig_right": None,
                "cap_left": "Edge count: Flat at 0.0% — never touches topology. Degree, WCC, SCC are equally flat.",
                "cap_right": None,
                "takeaway": "Measurement noise is benign: only weighted statistics move (variance +5.5%); topology and ranking are untouched (r = 0.999).",
                "slide_n": 6,
            },
            {
                "title": "Split Errors — Fragmentation",
                "subtitle": "Over-segmentation: the same edges are spread across more neuron identities.",
                "fig_left": os.path.join(FIG, "EM_split_errors_02_metric_total_degree_mean.png"),
                "fig_right": os.path.join(FIG, "EM_split_errors_04_metric_scc_max_size.png"),
                "cap_left": "Mean degree: −14.9% — edge budget preserved but diluted.",
                "cap_right": "Strong component: +17.6% (WCC +17.7%) — fragmentation.",
                "takeaway": "Edges kept but spread out → degree falls, components fragment; PageRank r = 0.995.",
                "slide_n": 7,
            },
            {
                "title": "Merge Errors — the Most Invasive",
                "subtitle": "Under-segmentation: neuron pairs collapse, concentrating connectivity.",
                "fig_left": os.path.join(FIG, "EM_merge_errors_00_metric_edge_count.png"),
                "fig_right": os.path.join(FIG, "EM_merge_errors_04_metric_scc_max_size.png"),
                "cap_left": "Edge count: −10.9% — connections collapse as pairs merge.",
                "cap_right": "Strong component: −9.0% (WCC −8.6%) — the graph condenses.",
                "takeaway": "Strongest distortion: weight variance +46.9%, edges −10.9%, components ~−9%; r = 0.989.",
                "slide_n": 8,
            },
        ]
        for ms in model_slides:
            fig = plt.figure(figsize=(W, H))
            y = section_title(fig, ms["title"], ms["subtitle"])
            footer_bar(fig); slide_number(fig, ms["slide_n"], TOTAL_SLIDES)
            img_top = y - 0.02
            img_h = 0.45
            if ms["fig_right"] is not None:
                add_figure(fig, ms["fig_left"], [MX, img_top - img_h, 0.40, img_h])
                draw_text(fig, MX, img_top - img_h - 0.015, ms["cap_left"], 10, color=LIGHT_GRY, weight="bold", width=0.40*W, ha="center")
                add_figure(fig, ms["fig_right"], [0.52, img_top - img_h, 0.40, img_h])
                draw_text(fig, 0.52, img_top - img_h - 0.015, ms["cap_right"], 10, color=LIGHT_GRY, weight="bold", width=0.40*W, ha="center")
            else:
                add_figure(fig, ms["fig_left"], [MX, img_top - img_h, 0.40, img_h])
                draw_text(fig, MX, img_top - img_h - 0.015, ms["cap_left"], 10, color=LIGHT_GRY, weight="bold", width=0.40*W, ha="center")
                # text table for noise control
                tbl = [["Edge count", "0.0%"], ["Mean degree", "0.0%"], ["WCC / SCC", "0.0%"], ["Weight variance", "+5.5%"], ["PageRank r", "0.999"]]
                draw_table(fig, 0.52, img_top - 0.05, [0.20, 0.10], ["Metric at 20%", "Change"], tbl, fs=12)
            
            ty = 0.12
            fig.patches.append(FancyBboxPatch((MX, ty), 0.88, 0.05, boxstyle="round,pad=0.006",
                facecolor=LIGHT_BG, edgecolor=NAVY, linewidth=1.0, transform=fig.transFigure, figure=fig))
            fig.text(MX + 0.012, ty + 0.025, "Takeaway:", fontsize=11, weight="bold", color=NAVY, va="center")
            draw_text(fig, MX + 0.08, ty + 0.025 + 0.008, ms["takeaway"], 11, color="#333")
            pdf.savefig(fig); plt.close(fig)

        # ── Slide 9 · PageRank Robustness ───────────────────────────────
        fig = plt.figure(figsize=(W, H))
        y = section_title(fig, "PageRank Robustness Across All Five Connectomes", "Global ranking survives; top-100 hub overlap is the fragile part")
        footer_bar(fig); slide_number(fig, 9, TOTAL_SLIDES)
        fy = y - 0.015
        fh = 0.42
        pr_best = os.path.join(FIG, "pagerank_missed_synapses.png")
        pr_worst = os.path.join(FIG, "pagerank_merge_errors.png")
        if os.path.exists(pr_best):
            add_figure(fig, pr_best, [MX, fy - fh, 0.40, fh])
            draw_text(fig, MX, fy - fh - 0.015, "Best case — missed (r ≥ 0.998)", 10, color=LIGHT_GRY, weight="bold", width=0.40*W, ha="center")
        if os.path.exists(pr_worst):
            add_figure(fig, pr_worst, [0.52, fy - fh, 0.40, fh])
            draw_text(fig, 0.52, fy - fh - 0.015, "Worst case — merge (r ≥ 0.977)", 10, color=LIGHT_GRY, weight="bold", width=0.40*W, ha="center")
        
        ty = fy - fh - 0.06
        pr_tbl_header = ["At 20 %", "Missed", "False", "Noise", "Split", "Merge"]
        pr_tbl_rows = [
            ["Pearson r", "0.999", "0.994", "0.999", "0.995", "0.989"],
            ["Spearman", "0.998", "0.971", "0.999", "0.976", "0.989"],
            ["Top-100", "0.980", "0.951", "0.976", "0.956", "0.924"],
        ]
        draw_table(fig, MX, ty, [0.18, 0.12, 0.12, 0.12, 0.12, 0.12], pr_tbl_header, pr_tbl_rows, fs=11)
        
        fig.patches.append(FancyBboxPatch((MX, 0.12), 0.88, 0.05, boxstyle="round,pad=0.006",
            facecolor=LIGHT_BG, edgecolor=NAVY, linewidth=1.0, transform=fig.transFigure, figure=fig))
        fig.text(MX + 0.012, 0.145, "Takeaway:", fontsize=11, weight="bold", color=NAVY, va="center")
        draw_text(fig, MX + 0.08, 0.145 + 0.008, "At 20%: Pearson ≥ 0.977, Spearman ≥ 0.96 everywhere — global ranking survives; top-100 hub overlap (≥ 0.86, weakest on BANC) is the fragile part.", 11, color="#333")
        pdf.savefig(fig); plt.close(fig)

        # ── Slide 10 · What the Results Mean ────────────────────────────
        fig = plt.figure(figsize=(W, H))
        y = section_title(fig, "What the Results Mean")
        footer_bar(fig); slide_number(fig, 10, TOTAL_SLIDES)
        y -= 0.02
        b1_txt = "Missed / false synapses change connectivity and weighted statistics; noise changes weighted statistics only; split errors change degree and component structure; merge errors change everything."
        block_box(fig, MX, y, "1 · Different error types have distinct graph fingerprints", b1_txt, 0.88)
        y -= 0.22
        b2_txt = "Split preserves edges, spreads them over more neurons, and fragments components. Merge collapses neuron identities, loses edges, and concentrates connectivity."
        block_box(fig, MX, y, "2 · Split and merge move the graph in opposite directions", b2_txt, 0.88)
        y -= 0.22
        b3_txt = "Structure can change substantially while global PageRank stays highly correlated — an error can distort the graph without destroying the identity of its important hubs."
        block_box(fig, MX, y, "3 · Robustness is metric-dependent", b3_txt, 0.88)
        pdf.savefig(fig); plt.close(fig)

        # ── Slide 11 · Analysis & Conclusions ───────────────────────────
        fig = plt.figure(figsize=(W, H))
        y = section_title(fig, "Analysis — What the Results Tell Us")
        footer_bar(fig); slide_number(fig, 11, TOTAL_SLIDES)
        conclusions = [
            "Connectivity layer vs. neuron-identity layer. Missed and false synapses act on the connectivity layer (edges, synapses, weights); split and merge errors act on the neuron-identity layer (which nodes exist and how they are grouped).",
            "Weighted statistics are the early indicators. Weight variance is the most sensitive metric, moving more strongly than topology for four of the five models.",
            "Component structure is the structural indicator. WCC/SCC capture split fragmentation (+17.7%/+17.6%) and merge condensation (−8.6%/−9.0%) that edge counts alone miss — SCC should stay a headline metric.",
            "PageRank is comparatively robust. Global rankings survive (r ≥ 0.977, Spearman ≥ 0.96) even when structure changes a lot; hub identity (top-100) is the fragile part.",
            "Consistent across five connectomes. All datasets respond qualitatively the same; benchmarking effort is best spent on missed-synapse detection, which does the most damage at equal rates."
        ]
        y = bullet(fig, MX, y - 0.02, conclusions, fs=12, gap=0.035, width=0.85*W)
        draw_text(fig, MX, y - 0.04, "Limitations: simulated error models, not empirical measurements; FAFB merge (2 trials/rate) and MANC merge (1 trial/rate) are partial runs; MANC and MAOL lack false-synapse runs; assortativity% is unreliable.", 9, color=LIGHT_GRY, style="italic")
        pdf.savefig(fig); plt.close(fig)

        # ── Slide 12 · Takeaway and Next Steps ──────────────────────────
        fig = plt.figure(figsize=(W, H))
        fig.patches.append(plt.Rectangle((0, 0.62), 1, 0.38, facecolor=NAVY, transform=fig.transFigure, figure=fig))
        fig.patches.append(plt.Rectangle((0, 0.61), 1, 0.012, facecolor=ACCENT, transform=fig.transFigure, figure=fig))
        fig.text(0.5, 0.88, "Takeaway and Next Steps", fontsize=26, weight="bold", color=WHITE, ha="center", va="center")
        fig.text(0.5, 0.74, "Graph analyses are not simply robust or fragile —\nreliability depends on the error type and on the analysis used.",
                 fontsize=16, ha="center", va="center", color="#BDD0E8", linespacing=1.5, style="italic")
        footer_bar(fig); slide_number(fig, 12, TOTAL_SLIDES)
        col_y = 0.55
        fig.text(MX + 0.02, col_y, "Summary", fontsize=16, weight="bold", color=NAVY, va="top")
        sum_items = [
            "Measurement noise is benign for topology.",
            "Missed / false synapses: characteristic connectivity changes.",
            "Split errors: strong component-structure effects.",
            "Merge errors: most invasive perturbation.",
            "PageRank remains comparatively robust."
        ]
        bullet(fig, MX + 0.03, col_y - 0.04, sum_items, fs=12, gap=0.015, width=0.35 * W, bullet_color=ACCENT)
        fig.text(0.54, col_y, "Next steps", fontsize=16, weight="bold", color=NAVY, va="top")
        next_items = [
            "Finalize the reporting / visualization layer.",
            "Keep SCC as a headline structural metric.",
            "Continue validation and biological interpretation.",
            "Treat these as simulated error models — not empirical measurements."
        ]
        bullet(fig, 0.55, col_y - 0.04, next_items, fs=12, gap=0.015, width=0.35 * W, bullet_color=ACCENT2)
        fig.text(0.5, 0.06, "Caveats: FAFB merge = 2 trials/rate, MANC merge = 1 trial/rate; MANC / MAOL lack false-synapse runs; assortativity % unreliable.",
                 fontsize=9, ha="center", va="bottom", color=LIGHT_GRY, style="italic")
        pdf.savefig(fig); plt.close(fig)

    print(f"✅ wrote {PDF} ({os.path.getsize(PDF)/1e6:.1f} MB)")

if __name__ == "__main__":
    main()
