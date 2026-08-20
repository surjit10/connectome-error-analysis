#!/usr/bin/env python3
"""Generate publication-grade 16:9 widescreen presentation PDF deck.

Theme: Professional Executive Light Mode
Topic: How Reconstruction Errors Affect the FlyWire Connectome
Author: Surjit Mandal
"""

import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.patches import FancyBboxPatch

PRESENTATION_DIR = "/home/surjit/Desktop/flywire/v1/analysis/final presentation/version2"
FIG_DIR = os.path.join(PRESENTATION_DIR, "figures")
OUT_PDF = os.path.join(PRESENTATION_DIR, "final_presentation_slides_v2.pdf")

# Visual Palette Tokens: Crisp Professional Executive Light Mode
W, H = 16.0, 9.0  # 16:9 Widescreen
BG_CANVAS    = "#F1F5F9"   # Clean light slate-gray canvas
CARD_BG      = "#FFFFFF"   # Pure crisp white card background
CARD_BORDER  = "#CBD5E1"   # Clean slate border
TEXT_MAIN    = "#0F172A"   # Deep rich slate (primary headers/titles)
TEXT_BODY    = "#1E293B"   # Slate body text (high readability)
TEXT_MUTED   = "#475569"   # Muted subtext & captions

# Professional Accent Tokens
BLUE_ACCENT  = "#2563EB"   # Royal Blue
CYAN_ACCENT  = "#0284C7"   # Sky Blue / Deep Cyan
MINT_GREEN   = "#059669"   # Emerald Green
CORAL_ALERT  = "#DC2626"   # Crimson Alert
ORANGE_WARN  = "#D97706"   # Amber Warning
PURPLE_ACC   = "#7C3AED"   # Violet Accent

TOTAL_SLIDES = 7

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "figure.facecolor": BG_CANVAS,
    "savefig.facecolor": BG_CANVAS,
    "pdf.fonttype": 42,
})

MX = 0.045

def wrap_text(text, fs, w_in, fig, weight="normal"):
    out = []
    r = fig.canvas.get_renderer()
    for seg in str(text).split("\n"):
        words, cur = seg.split(), []
        lim = w_in * 0.98
        for wd in words:
            trial = " ".join(cur + [wd]) if cur else wd
            t_obj = fig.text(0, 0, trial, fontsize=fs, weight=weight)
            box = t_obj.get_window_extent(renderer=r)
            t_obj.remove()
            if (box.width / 72.0) <= lim:
                cur.append(wd)
            else:
                if cur:
                    out.append(" ".join(cur))
                cur = [wd]
        if cur:
            out.append(" ".join(cur))
    return out

def draw_text(fig, x, y, text, fs=10, color=TEXT_BODY, weight="normal", width=6.0, line_sp=1.38):
    lines = wrap_text(text, fs, width, fig, weight)
    h_in = (fs * line_sp) / 72.0
    cy = y
    for line in lines:
        fig.text(x, cy, line, fontsize=fs, color=color, weight=weight, va="top")
        cy -= (h_in / H)
    return cy

def add_header(fig, title, subtitle, cat_text, slide_num):
    fig.text(MX, 0.948, f"●  {cat_text.upper()}", fontsize=9.5, color=CYAN_ACCENT, weight="bold")
    fig.text(MX, 0.912, title, fontsize=17, color=TEXT_MAIN, weight="bold")
    fig.text(MX, 0.875, subtitle, fontsize=10.0, color=TEXT_MUTED)
    fig.text(1.0 - MX, 0.938, f"Slide {slide_num} / {TOTAL_SLIDES}", fontsize=11, color=BLUE_ACCENT, weight="bold", ha="right")

def add_card(fig, rect, border=CARD_BORDER, fill=CARD_BG, top_bar_color=CYAN_ACCENT):
    x, y, w, h = rect
    ax = fig.add_axes([0, 0, 1, 1], facecolor="none")
    ax.axis("off")
    p = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.008",
                       facecolor=fill, edgecolor=border, lw=1.2, zorder=2)
    ax.add_patch(p)
    if top_bar_color:
        top_bar = FancyBboxPatch((x, y + h - 0.006), w, 0.006, boxstyle="round,pad=0.001",
                                facecolor=top_bar_color, edgecolor="none", zorder=3)
        ax.add_patch(top_bar)

def add_footer(fig):
    fig.text(MX, 0.028, "Surjit Mandal  |  How Reconstruction Errors Affect the FlyWire Connectome",
             fontsize=9.0, color=TEXT_MUTED, weight="bold")
    fig.text(1.0 - MX, 0.028, "Connectome Robustness Benchmark",
             fontsize=9.0, color=BLUE_ACCENT, weight="bold", ha="right")

# --- SLIDE 1: Title & Overview ---
def make_slide_1(pdf):
    fig = plt.figure(figsize=(W, H), facecolor=BG_CANVAS)
    fig.canvas.draw()
    add_header(fig, "How Reconstruction Errors Affect the FlyWire Connectome",
               "Measuring how wiring diagram errors change network structure across 5 fruit fly connectomes",
               "RESEARCH OVERVIEW & BENCHMARK DESIGN", 1)

    # Left Card: Core Investigation
    add_card(fig, (MX, 0.065, 0.44, 0.78), top_bar_color=BLUE_ACCENT)
    
    fig.text(MX + 0.02, 0.790, "Surjit Mandal", fontsize=17, color=TEXT_MAIN, weight="bold")

    fig.text(MX + 0.02, 0.715, "WHY THIS MATTERS", fontsize=10.5, color=CYAN_ACCENT, weight="bold")
    draw_text(fig, MX + 0.02, 0.680,
              "Automated AI tools make mistakes when mapping brain wiring diagrams from electron microscope images.\n\nThis benchmark tests how much these errors change network connections, brain components, and neuron importance rankings.",
              9.8, TEXT_BODY, width=0.40 * W)

    fig.text(MX + 0.02, 0.485, "DATASETS TESTED", fontsize=10.5, color=BLUE_ACCENT, weight="bold")
    draw_text(fig, MX + 0.02, 0.455,
              "• 5 Drosophila Connectomes: BANC (158k), FAFB (139k), MANC (24k), MCNS (167k), MAOL (52k neurons)\n"
              "• 1,030 independent simulation runs across 10 error levels (0% to 20%)\n"
              "• Tracked network connections, connected components, and PageRank rankings",
              9.2, TEXT_BODY, width=0.40 * W)

    fig.text(MX + 0.02, 0.250, "KEY PAPERS & REFERENCES", fontsize=9.6, color=TEXT_MUTED, weight="bold")
    draw_text(fig, MX + 0.02, 0.220,
              "• Dorkenwald et al. Nature 2024 (FlyWire Whole-Brain Connectome)\n"
              "• Buhmann et al. Nature Methods 2021 (Automated Synapse Detection)\n"
              "• Januszewski et al. Nature Methods 2018 (Flood-Filling Segmentation)\n"
              "• Takemura et al. Nature 2023  |  Scheffer et al. eLife 2020",
              8.5, TEXT_MUTED, width=0.40 * W)

    # Right Card: The 5 Real-World Reconstruction Errors
    add_card(fig, (0.515, 0.065, 0.44, 0.78), top_bar_color=MINT_GREEN)
    fig.text(0.535, 0.805, "THE FIVE ERROR TYPES TESTED", fontsize=11, color=MINT_GREEN, weight="bold")

    error_models = [
        ("1. Missed Synapses (EM1)", "The detector fails to spot a real synaptic connection.", ORANGE_WARN),
        ("2. False Synapses (EM2)", "The detector adds a fake connection where none exists.", BLUE_ACCENT),
        ("3. Synapse Count Jitter (EM3)", "Small counting errors in individual synapse numbers.", MINT_GREEN),
        ("4. Split Neurons (EM4)", "A single biological neuron gets broken into fragments.", PURPLE_ACC),
        ("5. Merged Neurons (EM5)", "Two distinct neurons get accidentally joined together.", CORAL_ALERT),
    ]

    y_pos = 0.755
    for name, desc, col in error_models:
        fig.text(0.535, y_pos, name, fontsize=10.0, color=TEXT_MAIN, weight="bold")
        draw_text(fig, 0.535, y_pos - 0.024, desc, 9.0, TEXT_MUTED, width=0.40 * W)
        y_pos -= 0.082

    fig.text(0.535, 0.270, "MAIN GOAL", fontsize=10.5, color=CYAN_ACCENT, weight="bold")
    draw_text(fig, 0.535, 0.240,
              "Provide clear sensitivity benchmarks showing how each error type affects brain graph measurements.",
              9.8, TEXT_BODY, width=0.40 * W)

    add_footer(fig)
    pdf.savefig(fig, dpi=150)
    plt.close(fig)

# --- SLIDE 2: Global Results Heatmap ---
def make_slide_2(pdf):
    fig = plt.figure(figsize=(W, H), facecolor=BG_CANVAS)
    fig.canvas.draw()
    add_header(fig, "How Each Error Type Changes the Graph",
               "Comparing cross-dataset averages and individual connectome ranges",
               "GLOBAL ERROR COMPARISON", 2)

    # Left: Summary Table & Insights
    add_card(fig, (MX, 0.065, 0.44, 0.78), top_bar_color=CYAN_ACCENT)
    fig.text(MX + 0.02, 0.805, "OVERALL ERROR IMPACT (AT 20% ERROR)", fontsize=10.5, color=CYAN_ACCENT, weight="bold")
    draw_text(fig, MX + 0.02, 0.770,
              "Each error type produces a distinct pattern of change across the connectome.",
              9.6, TEXT_BODY, width=0.40 * W)

    fig.text(MX + 0.02, 0.680, "RESULTS AT HIGHEST TESTED ERROR LEVEL (20%)", fontsize=9.2, color=BLUE_ACCENT, weight="bold")
    headers = ["Error Model", "Δ Edge Count", "Δ Synapses", "Δ Var"]
    col_x = [MX + 0.02, MX + 0.170, MX + 0.295, MX + 0.365]
    for x, h in zip(col_x, headers):
        fig.text(x, 0.645, h, fontsize=8.0, color=CYAN_ACCENT, weight="bold")

    table_data = [
        ("Missed Synapses (n=5)", "-4.9%", "-20.0%", "-30.3%"),
        ("False Synapses (n=3)", "+19.4%", "+7.6%", "-13.8%"),
        ("Synapse Count Noise (n=5)", "0.0%", "+0.03%", "+5.5%"),
        ("Split Neurons (n=5)", "0.0%", "0.0%", "0.0%"),
        ("Merged Neurons (n=4)", "-10.9%", "-0.1%", "+46.9%"),
    ]
    y = 0.610
    for row in table_data:
        c = CORAL_ALERT if "Merge" in row[0] or "-" in row[1] else (MINT_GREEN if "0.0%" in row[1] else BLUE_ACCENT)
        fig.text(col_x[0], y, row[0], fontsize=8.2, color=TEXT_MAIN, weight="bold")
        fig.text(col_x[1], y, row[1], fontsize=8.6, color=c, weight="bold")
        fig.text(col_x[2], y, row[2], fontsize=8.4, color=TEXT_BODY)
        fig.text(col_x[3], y, row[3], fontsize=8.4, color=TEXT_BODY)
        y -= 0.040

    fig.text(MX + 0.02, 0.380, "INDIVIDUAL CONNECTOME RANGES", fontsize=9.5, color=CYAN_ACCENT, weight="bold")
    draw_text(fig, MX + 0.02, 0.350,
              "• Missed Synapses: MCNS (-0.007%) to MANC (-9.7%)\n"
              "• Merged Neurons: MCNS (-7.1%) to FAFB (-16.1%)\n"
              "• Splits & Noise: 0.0% edge loss across all 5 datasets",
              8.8, TEXT_BODY, width=0.40 * W)

    fig.text(MX + 0.02, 0.200, "MAIN TAKEAWAY", fontsize=10.0, color=MINT_GREEN, weight="bold")
    draw_text(fig, MX + 0.02, 0.170,
              "Merged neurons caused the largest structural damage (-10.9% mean edge loss, +46.9% variance surge). Splits and noise preserve total connections.",
              8.8, TEXT_BODY, width=0.40 * W)

    fig.text(MX + 0.02, 0.090, "Note: n varies by model (n=3 to 5). At typical error levels (2-5%), metrics shift by <1%.", fontsize=7.6, color=TEXT_MUTED)

    # Right: Embedded Clean Figure
    add_card(fig, (0.515, 0.065, 0.44, 0.78), top_bar_color=BLUE_ACCENT)
    img_p = os.path.join(FIG_DIR, "clean_fig_global_fingerprints.png")
    if os.path.exists(img_p):
        im = plt.imread(img_p)
        ax_img = fig.add_axes([0.520, 0.080, 0.430, 0.750])
        ax_img.imshow(im)
        ax_img.axis("off")

    add_footer(fig)
    pdf.savefig(fig, dpi=150)
    plt.close(fig)

# --- SLIDE 3: Finding 1: Missed Synapses & Binomial Buffering ---
def make_slide_3(pdf):
    fig = plt.figure(figsize=(W, H), facecolor=BG_CANVAS)
    fig.canvas.draw()
    add_header(fig, "Why Missed Synapses Do Not Proportionally Eliminate Connections",
               "Connections with multiple synapses provide built-in protection against loss",
               "MISSED SYNAPSE ANALYSIS", 3)

    # Left: Logic & Formula Card
    add_card(fig, (MX, 0.065, 0.44, 0.78), top_bar_color=CYAN_ACCENT)
    fig.text(MX + 0.02, 0.805, "SYNAPSE LOSS VS CONNECTION LOSS", fontsize=10.5, color=CYAN_ACCENT, weight="bold")
    draw_text(fig, MX + 0.02, 0.770,
              "Evaluating whether losing 20% of synapses removes 20% of graph connections.",
              9.8, TEXT_BODY, width=0.40 * W)

    fig.text(MX + 0.02, 0.675, "MAIN RESULTS", fontsize=10.5, color=BLUE_ACCENT, weight="bold")
    draw_text(fig, MX + 0.02, 0.645,
              "• Total synapses drop by ~20.0%\n"
              "• Connection count drops by only -4.87% (~4x smaller than synapse loss)\n"
              "• Largest Connected Core (SCC) shrinks by only -0.04%",
              9.2, TEXT_BODY, width=0.40 * W)

    fig.text(MX + 0.02, 0.470, "WHY THIS HAPPENS", fontsize=10.5, color=MINT_GREEN, weight="bold")
    draw_text(fig, MX + 0.02, 0.440,
              "In real connectomes, many connections have multiple synapses. A connection is only lost if every single synapse on it is missed (P = p^w).\n\n"
              "Under a 20% miss rate (illustrative example):\n"
              "• 1-synapse edge: 20.0% chance of loss\n"
              "• 5-synapse edge: 0.03% chance of loss\n\n"
              "Connections with more synapses are strongly protected from disappearing.",
              8.8, TEXT_BODY, width=0.40 * W)

    fig.text(MX + 0.02, 0.105, "Error model rates are motivated by automated synapse detection studies (Buhmann et al. 2021).", fontsize=7.6, color=TEXT_MUTED)

    # Right: Embedded Clean Figure
    add_card(fig, (0.515, 0.065, 0.44, 0.78), top_bar_color=BLUE_ACCENT)
    img_p = os.path.join(FIG_DIR, "clean_fig_binomial_buffering.png")
    if os.path.exists(img_p):
        im = plt.imread(img_p)
        ax_img = fig.add_axes([0.520, 0.080, 0.430, 0.750])
        ax_img.imshow(im)
        ax_img.axis("off")

    add_footer(fig)
    pdf.savefig(fig, dpi=150)
    plt.close(fig)

# --- SLIDE 4: Finding 2: Split vs Merge Asymmetry ---
def make_slide_4(pdf):
    fig = plt.figure(figsize=(W, H), facecolor=BG_CANVAS)
    fig.canvas.draw()
    add_header(fig, "Merging Neurons Produces Larger Changes in Edge Count and Weight Variance",
               "Neuron merges reduce edge count and strongly increase connection-weight variance",
               "SPLIT VS MERGE COMPARISON", 4)

    # Left: Head-to-Head Comparison Card
    add_card(fig, (MX, 0.065, 0.44, 0.78), top_bar_color=CORAL_ALERT)
    fig.text(MX + 0.02, 0.805, "SPLITS VS MERGES", fontsize=10.5, color=CYAN_ACCENT, weight="bold")
    draw_text(fig, MX + 0.02, 0.770,
              "Comparing what happens when neurons are split into pieces versus when separate neurons are accidentally merged.",
              9.8, TEXT_BODY, width=0.40 * W)

    fig.text(MX + 0.02, 0.675, "HEAD-TO-HEAD COMPARISON (AT 20% ERROR)", fontsize=9.0, color=ORANGE_WARN, weight="bold")
    col_x = [MX + 0.015, MX + 0.250, MX + 0.355]
    fig.text(col_x[0], 0.640, "Metric", fontsize=8.5, color=CYAN_ACCENT, weight="bold")
    fig.text(col_x[1], 0.640, "Split Neurons (n=5)", fontsize=8.2, color=MINT_GREEN, weight="bold")
    fig.text(col_x[2], 0.640, "Merged Neurons (n=4)", fontsize=8.2, color=CORAL_ALERT, weight="bold")

    comp_rows = [
        ("Edge Count Change", "0.0%", "-10.9%"),
        ("Total Synapse Change", "0.0%", "-0.1%"),
        ("Mean Degree", "-14.9%", "-2.6%"),
        ("Largest Strongly Connected Component (SCC)", "+17.6%", "-9.0%"),
        ("Weight Variance", "0.0%", "+46.9%"),
    ]
    y = 0.605
    for row in comp_rows:
        fs = 7.7 if "Strongly" in row[0] else 8.2
        fig.text(col_x[0], y, row[0], fontsize=fs, color=TEXT_MAIN, weight="bold")
        fig.text(col_x[1], y, row[1], fontsize=8.4, color=MINT_GREEN, weight="bold")
        fig.text(col_x[2], y, row[2], fontsize=8.4, color=CORAL_ALERT, weight="bold")
        y -= 0.042

    fig.text(MX + 0.02, 0.350, "KEY TAKEAWAY", fontsize=10.2, color=CORAL_ALERT, weight="bold")
    draw_text(fig, MX + 0.02, 0.320,
              "Splitting redistributes existing connections across fragments while preserving total edge and synapse counts. Merging combines neurons, reducing edge count by 10.9% and increasing weight variance by 46.9%.",
              9.0, TEXT_BODY, width=0.40 * W)

    fig.text(MX + 0.02, 0.105, "Splits and merges are important reconstruction error types in automated EM segmentation (Dorkenwald et al., 2024; Januszewski et al., 2018).", fontsize=7.4, color=TEXT_MUTED)

    # Right: Embedded Clean Figure
    add_card(fig, (0.515, 0.065, 0.44, 0.78), top_bar_color=CORAL_ALERT)
    img_p = os.path.join(FIG_DIR, "clean_fig_split_vs_merge.png")
    if os.path.exists(img_p):
        im = plt.imread(img_p)
        ax_img = fig.add_axes([0.520, 0.080, 0.430, 0.750])
        ax_img.imshow(im)
        ax_img.axis("off")

    add_footer(fig)
    pdf.savefig(fig, dpi=150)
    plt.close(fig)

# --- SLIDE 5: Finding 3: PageRank & Median Weight Association ---
def make_slide_5(pdf):
    fig = plt.figure(figsize=(W, H), facecolor=BG_CANVAS)
    fig.canvas.draw()
    add_header(fig, "PageRank Remains Stable; Higher Connection Strength Is Associated With Lower Edge Loss",
               "PageRank similarity to baseline remains high (r ≥ 0.977); edge loss varies with median connection weight",
               "CENTRALITY & CONNECTOME COMPARISON", 5)

    # Left: PageRank & Median Weight Data
    add_card(fig, (MX, 0.065, 0.44, 0.78), top_bar_color=CYAN_ACCENT)
    fig.text(MX + 0.02, 0.805, "1. PAGERANK SIMILARITY TO BASELINE REMAINS HIGH", fontsize=10.0, color=CYAN_ACCENT, weight="bold")
    draw_text(fig, MX + 0.02, 0.770,
              "• PageRank remains highly correlated with the unperturbed baseline across the tested error models.\n"
              "• Pearson correlations range from approximately 0.977 to 1.000 (mean r = 0.999 under missed synapses).\n"
              "• PageRank rankings remain highly similar to the baseline under the tested perturbations.",
              9.0, TEXT_BODY, width=0.40 * W)

    fig.text(MX + 0.02, 0.605, "2. HIGHER CONNECTION STRENGTH IS ASSOCIATED WITH LOWER EDGE LOSS", fontsize=9.6, color=MINT_GREEN, weight="bold")
    draw_text(fig, MX + 0.02, 0.575,
              "Under the 20% missed-synapse perturbation, observed edge loss varies across connectomes with different median connection weights:\n"
              "• MCNS (median weight 9.0): -0.007% edge count change\n"
              "• FAFB (median weight 6.0): -2.50% edge count change\n"
              "• BANC (median weight 4.0): -3.19% edge count change\n"
              "• MAOL (median weight 2.0): -8.92% edge count change\n"
              "• MANC (median weight 2.0): -9.73% edge count change",
              8.8, TEXT_BODY, width=0.40 * W)

    fig.text(MX + 0.02, 0.280, "MAIN TAKEAWAY", fontsize=10.0, color=MINT_GREEN, weight="bold")
    draw_text(fig, MX + 0.02, 0.250,
              "PageRank remains highly similar to baseline under the tested perturbations, while connectomes with higher median connection weights show lower observed edge loss under the missed-synapse model.",
              9.0, TEXT_BODY, width=0.40 * W)

    fig.text(MX + 0.02, 0.105, "Note: Observations reflect cross-connectome associations across the 5 tested datasets (Scheffer et al. eLife 2020).", fontsize=7.4, color=TEXT_MUTED)

    # Right: Embedded Clean Figure
    add_card(fig, (0.515, 0.065, 0.44, 0.78), top_bar_color=BLUE_ACCENT)
    img_p = os.path.join(FIG_DIR, "clean_fig_pagerank_and_median_law.png")
    if os.path.exists(img_p):
        im = plt.imread(img_p)
        ax_img = fig.add_axes([0.520, 0.080, 0.430, 0.750])
        ax_img.imshow(im)
        ax_img.axis("off")

    add_footer(fig)
    pdf.savefig(fig, dpi=150)
    plt.close(fig)

# --- SLIDE 6: Secondary Effects of Reconstruction Errors ---
def make_slide_6(pdf):
    fig = plt.figure(figsize=(W, H), facecolor=BG_CANVAS)
    fig.canvas.draw()
    add_header(fig, "Secondary Effects of Reconstruction Errors",
               "Different reconstruction errors leave different fingerprints beyond the quantity directly perturbed.",
               "SECONDARY ERROR FINGERPRINTS", 6)

    # Helper to draw a standard secondary-effect card
    def draw_sec_card(box, title, direct, sec_text, metrics, accent_color):
        bx, by, bw, bh = box
        add_card(fig, box, top_bar_color=accent_color)
        fig.text(bx + 0.015, by + bh - 0.038, title, fontsize=9.6, color=accent_color, weight="bold")
        fig.text(bx + 0.165, by + bh - 0.038, f"Direct: {direct}", fontsize=7.6, color=TEXT_MUTED)
        
        fig.text(bx + 0.015, by + bh - 0.075, "SECONDARY EFFECT:", fontsize=7.2, color=MINT_GREEN, weight="bold")
        draw_text(fig, bx + 0.015, by + bh - 0.098, sec_text, 8.2, TEXT_MAIN, weight="bold", width=bw * W - 0.3)
        
        fig.text(bx + 0.015, by + 0.022, f"Evidence: {metrics}", fontsize=7.8, color=BLUE_ACCENT, weight="bold")

    # Left Column (X = MX = 0.045, width = 0.440)
    # Card 1: Missed Synapses
    draw_sec_card(
        (MX, 0.585, 0.440, 0.235),
        "1. MISSED SYNAPSES",
        "20% of synapses are removed",
        "Many individual synapses can be lost while most neuron-to-neuron connections remain.",
        "−20.0% synapses  |  −4.9% connections  |  PageRank r = 0.999",
        CYAN_ACCENT
    )

    # Card 2: False Synapses
    draw_sec_card(
        (MX, 0.330, 0.440, 0.235),
        "2. FALSE SYNAPSES",
        "New false connections are added",
        "Many new connections are added, but they are relatively weak, so connection count grows much faster than total synaptic strength.",
        "+19.4% connections  |  +7.6% synapses  |  −13.8% weight variance",
        BLUE_ACCENT
    )

    # Card 3: Count Noise
    draw_sec_card(
        (MX, 0.075, 0.440, 0.235),
        "3. SYNAPSE-COUNT NOISE",
        "Connection weights changed; graph unchanged",
        "The network structure stays the same, but connection strengths become less reliable.",
        "0.0% connection change  |  0.0% degree/SCC  |  +5.5% weight variance",
        MINT_GREEN
    )

    # Right Column (X = 0.515, width = 0.440)
    # Card 4: Split Errors
    draw_sec_card(
        (0.515, 0.585, 0.440, 0.235),
        "4. SPLIT ERRORS",
        "Neurons split into multiple neuron pieces",
        "Connections are kept, but they are spread across more neurons. This lowers connections per neuron and changes the largest connected group.",
        "+17.5% neurons  |  0.0% connection loss  |  −14.9% mean degree  |  +17.6% largest SCC",
        PURPLE_ACC
    )

    # Card 5: Merge Errors
    draw_sec_card(
        (0.515, 0.330, 0.440, 0.235),
        "5. MERGE ERRORS",
        "Multiple neurons combined into one",
        "Most synapses remain, but merging neurons combines separate connections into fewer and much stronger-looking connections.",
        "−0.1% synapses  |  −10.9% connections  |  +46.9% weight variance  |  −9.0% largest SCC",
        CORAL_ALERT
    )

    # Card 6: QC Synthesis & Takeaway
    add_card(fig, (0.515, 0.075, 0.440, 0.235), top_bar_color=ORANGE_WARN)
    fig.text(0.530, 0.075 + 0.235 - 0.038, "KEY QUALITY-CONTROL TAKEAWAY", fontsize=9.6, color=ORANGE_WARN, weight="bold")
    
    draw_text(fig, 0.530, 0.075 + 0.235 - 0.072,
              "Each error changes the network in more ways than the direct error itself. Some errors mainly change connections, some change connection strength, and others change how connections are distributed across neurons.",
              7.8, TEXT_MAIN, weight="bold", width=0.440 * W - 0.3)
    
    draw_text(fig, 0.530, 0.075 + 0.235 - 0.142,
              "Reliable connectome quality checks therefore need to look at several network measurements, not just one.",
              7.8, BLUE_ACCENT, weight="bold", width=0.440 * W - 0.3)

    fig.text(0.530, 0.075 + 0.022,
             "BENCHMARK: 5 connectomes • 10 error levels • 1,030 runs  |  Surjit Mandal",
             fontsize=7.4, color=TEXT_MUTED, weight="bold")

    add_footer(fig)
    pdf.savefig(fig, dpi=150)
    plt.close(fig)

# --- SLIDE 7: Appendix — Complete 5-Connectome Breakdown ---
def make_slide_7(pdf):
    fig = plt.figure(figsize=(W, H), facecolor=BG_CANVAS)
    fig.canvas.draw()
    add_header(fig, "Individual Connectome Breakdown Table",
               "Comparing exact Δ Edge Count and metrics across BANC, FAFB, MANC, MCNS, and MAOL (at 20% Peak Error)",
               "APPENDIX & FULL DATASET COMPARISON", 7)

    # Left Card: Missed Synapses & Merged Neurons Individual Breakdown
    add_card(fig, (MX, 0.065, 0.44, 0.78), top_bar_color=CYAN_ACCENT)
    fig.text(MX + 0.02, 0.805, "1. MISSED SYNAPSES (EM1) BREAKDOWN", fontsize=10.5, color=CYAN_ACCENT, weight="bold")
    
    col_x = [MX + 0.02, MX + 0.12, MX + 0.22, MX + 0.32]
    headers = ["Connectome", "Median W", "Δ Edge Count", "PageRank r"]
    for x, h in zip(col_x, headers):
        fig.text(x, 0.770, h, fontsize=8.0, color=CYAN_ACCENT, weight="bold")
        
    em1_data = [
        ("BANC", "4.0", "-3.19%", "0.998"),
        ("FAFB", "6.0", "-2.50%", "1.000"),
        ("MANC", "2.0", "-9.73%", "0.998"),
        ("MCNS", "9.0", "-0.007%", "1.000"),
        ("MAOL", "2.0", "-8.92%", "0.999"),
        ("MEAN (n=5)", "4.6", "-4.87%", "0.999"),
    ]
    y = 0.735
    for row in em1_data:
        is_mean = "MEAN" in row[0]
        c = BLUE_ACCENT if is_mean else TEXT_MAIN
        fig.text(col_x[0], y, row[0], fontsize=8.4, color=c, weight="bold" if is_mean else "normal")
        fig.text(col_x[1], y, row[1], fontsize=8.4, color=TEXT_BODY)
        fig.text(col_x[2], y, row[2], fontsize=8.6, color=CORAL_ALERT if "-" in row[2] else MINT_GREEN, weight="bold")
        fig.text(col_x[3], y, row[3], fontsize=8.4, color=MINT_GREEN, weight="bold")
        y -= 0.036

    fig.text(MX + 0.02, 0.470, "2. MERGED NEURONS (EM5) BREAKDOWN", fontsize=10.5, color=CORAL_ALERT, weight="bold")
    headers2 = ["Connectome", "Δ Edge Count", "Δ Weight Var", "Largest SCC"]
    col_x2 = [MX + 0.02, MX + 0.13, MX + 0.24, MX + 0.34]
    for x, h in zip(col_x2, headers2):
        fig.text(x, 0.435, h, fontsize=8.0, color=CORAL_ALERT, weight="bold")
        
    em5_data = [
        ("BANC", "-12.18%", "+59.87%", "-8.30%"),
        ("FAFB", "-16.09%", "+64.98%", "-9.33%"),
        ("MANC", "-8.27%", "+24.46%", "-9.98%"),
        ("MCNS", "-7.12%", "+38.20%", "-8.24%"),
        ("MEAN (n=4)", "-10.91%", "+46.88%", "-8.96%"),
    ]
    y = 0.400
    for row in em5_data:
        is_mean = "MEAN" in row[0]
        c = BLUE_ACCENT if is_mean else TEXT_MAIN
        fig.text(col_x2[0], y, row[0], fontsize=8.4, color=c, weight="bold" if is_mean else "normal")
        fig.text(col_x2[1], y, row[1], fontsize=8.6, color=CORAL_ALERT, weight="bold")
        fig.text(col_x2[2], y, row[2], fontsize=8.4, color=CORAL_ALERT, weight="bold")
        fig.text(col_x2[3], y, row[3], fontsize=8.4, color=TEXT_BODY)
        y -= 0.036

    fig.text(MX + 0.02, 0.160, "TAKEAWAY ACROSS CONNECTOMES", fontsize=9.6, color=MINT_GREEN, weight="bold")
    draw_text(fig, MX + 0.02, 0.130,
              "All individual connectomes exhibit the same core phenomenon: edge buffering under synapse loss, severe edge loss under merges, and 100% edge preservation under splits.",
              8.8, TEXT_BODY, width=0.40 * W)

    # Right Card: False Synapses, Splits, & Baseline Characteristics
    add_card(fig, (0.515, 0.065, 0.44, 0.78), top_bar_color=MINT_GREEN)
    fig.text(0.535, 0.805, "3. FALSE SYNAPSES (EM2) BREAKDOWN", fontsize=10.5, color=BLUE_ACCENT, weight="bold")
    
    col_x3 = [0.535, 0.640, 0.745, 0.845]
    headers3 = ["Connectome", "Δ Edge Count", "Δ Synapses", "Δ Weight Var"]
    for x, h in zip(col_x3, headers3):
        fig.text(x, 0.770, h, fontsize=8.0, color=BLUE_ACCENT, weight="bold")
        
    em2_data = [
        ("BANC", "+20.00%", "+10.02%", "-15.03%"),
        ("FAFB", "+20.00%", "+6.58%", "-13.90%"),
        ("MCNS", "+18.18%", "+6.32%", "-12.61%"),
        ("MEAN (n=3)", "+19.39%", "+7.64%", "-13.85%"),
    ]
    y = 0.735
    for row in em2_data:
        is_mean = "MEAN" in row[0]
        c = BLUE_ACCENT if is_mean else TEXT_MAIN
        fig.text(col_x3[0], y, row[0], fontsize=8.4, color=c, weight="bold" if is_mean else "normal")
        fig.text(col_x3[1], y, row[1], fontsize=8.6, color=BLUE_ACCENT, weight="bold")
        fig.text(col_x3[2], y, row[2], fontsize=8.4, color=TEXT_BODY)
        fig.text(col_x3[3], y, row[3], fontsize=8.4, color=TEXT_BODY)
        y -= 0.036

    fig.text(0.535, 0.540, "4. SPLIT NEURONS (EM4) ACROSS ALL 5 DATASETS", fontsize=10.5, color=MINT_GREEN, weight="bold")
    draw_text(fig, 0.535, 0.510,
              "Across BANC, FAFB, MANC, MCNS, and MAOL:\n"
              "• Δ Edge Count: 0.0% (100% preserved in all 5 datasets)\n"
              "• Δ Total Synapses: 0.0% (100% preserved in all 5 datasets)\n"
              "• Mean Degree: drops by -12.8% to -16.0% (mean -14.9%)\n"
              "• Largest Connected Core: shifts by +14.9% to +19.2% (mean +17.6%)",
              8.8, TEXT_BODY, width=0.40 * W)

    fig.text(0.535, 0.280, "5. BASELINE DATASET CHARACTERISTICS", fontsize=10.0, color=TEXT_MAIN, weight="bold")
    draw_text(fig, 0.535, 0.250,
              "• BANC: 158k nodes | 3.99M edges | 23.6M synapses (med wt: 4.0)\n"
              "• FAFB: 139k nodes | 5.34M edges | 50.7M synapses (med wt: 6.0)\n"
              "• MANC: 24k nodes  | 6.24M edges | 30.9M synapses (med wt: 2.0)\n"
              "• MCNS: 167k nodes | 6.24M edges | 89.8M synapses (med wt: 9.0)\n"
              "• MAOL: 52k nodes  | 6.74M edges | 26.5M synapses (med wt: 2.0)",
              8.5, TEXT_MUTED, width=0.40 * W)

    add_footer(fig)
    pdf.savefig(fig, dpi=150)
    plt.close(fig)

def main():
    print(f"Generating {TOTAL_SLIDES}-slide 16:9 light-themed PDF deck to: {OUT_PDF}")
    with PdfPages(OUT_PDF) as pdf:
        make_slide_1(pdf)
        make_slide_2(pdf)
        make_slide_3(pdf)
        make_slide_4(pdf)
        make_slide_5(pdf)
        make_slide_6(pdf)
        make_slide_7(pdf)
    print(f"Successfully generated {OUT_PDF}")

if __name__ == "__main__":
    main()
