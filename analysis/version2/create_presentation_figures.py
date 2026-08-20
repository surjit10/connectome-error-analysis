#!/usr/bin/env python3
"""Generate high-contrast, crystal-clear, publication-grade light-themed figures.

Tailored for professional light slide presentation deck.
"""

import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

PRESENTATION_DIR = "/home/surjit/Desktop/flywire/v1/analysis/final presentation/version2"
OUT_DIR = os.path.join(PRESENTATION_DIR, "figures")
os.makedirs(OUT_DIR, exist_ok=True)

# Clean Professional Light Palette
BG_CARD     = "#FFFFFF"
TEXT_MAIN   = "#0F172A"
TEXT_MUTED  = "#475569"
GRID_COLOR  = "#E2E8F0"

BLUE        = "#2563EB"
CYAN        = "#0284C7"
MINT        = "#059669"
AMBER       = "#D97706"
CORAL       = "#DC2626"
PURPLE_ACC  = "#7C3AED"

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 11,
    "axes.facecolor": BG_CARD,
    "figure.facecolor": BG_CARD,
    "savefig.facecolor": BG_CARD,
    "axes.edgecolor": "#CBD5E1",
    "axes.linewidth": 1.2,
    "grid.color": GRID_COLOR,
    "grid.linestyle": "--",
    "grid.alpha": 0.9,
    "text.color": TEXT_MAIN,
    "axes.labelcolor": TEXT_MAIN,
    "xtick.color": TEXT_MAIN,
    "ytick.color": TEXT_MAIN,
})

# -----------------------------------------------------------------------------
# FIGURE 1: Global Error Fingerprints (Slide 2)
# -----------------------------------------------------------------------------
def generate_fig1_fingerprints():
    fig, ax = plt.subplots(figsize=(8.4, 5.2), dpi=220)
    
    models = ["Missed Synapses", "False Synapses", "Synapse Count Noise", "Split Neurons", "Merged Neurons"]
    edge_changes = [-4.87, +19.39, 0.0, 0.0, -10.91]
    var_changes  = [-30.25, -13.85, +5.45, 0.0, +46.88]
    
    edge_indiv = [
        [-3.19, -2.50, -9.73, -0.007, -8.92],  # Missed
        [+20.0, +20.0, +18.18],               # False
        [0.0, 0.0, 0.0, 0.0, 0.0],            # Count
        [0.0, 0.0, 0.0, 0.0, 0.0],            # Split
        [-12.18, -16.09, -8.27, -7.12]         # Merge
    ]
    var_indiv = [
        [-31.05, -32.59, -26.98, -33.74, -26.91], # Missed
        [-15.03, -13.90, -12.61],                 # False
        [+5.69, +5.46, +4.72, +6.08, +5.32],      # Count
        [0.0, 0.0, 0.0, 0.0, 0.0],                # Split
        [+59.87, +64.98, +24.46, +38.20]          # Merge
    ]
    
    y = np.arange(len(models))
    height = 0.35
    
    rects1 = ax.barh(y - height/2, edge_changes, height, label="Δ Edge Count (%) [Mean]", color=CYAN, alpha=0.65, edgecolor="none", zorder=3)
    rects2 = ax.barh(y + height/2, var_changes, height, label="Δ Weight Variance (%) [Mean]", color=AMBER, alpha=0.65, edgecolor="none", zorder=3)
    
    # Overlay individual connectome dots with high contrast
    for idx, (e_pts, v_pts) in enumerate(zip(edge_indiv, var_indiv)):
        ax.scatter(e_pts, [y[idx] - height/2]*len(e_pts), color="#38BDF8", edgecolors="#0F172A", linewidths=1.2, s=55, zorder=5, label="● Individual Connectomes" if idx==0 else "")
        ax.scatter(v_pts, [y[idx] + height/2]*len(v_pts), color="#FCD34D", edgecolors="#0F172A", linewidths=1.2, s=55, zorder=5)
    
    ax.axvline(0, color="#94A3B8", linewidth=1.2, linestyle="-", zorder=4)
    ax.set_yticks(y)
    ax.set_yticklabels(models, fontsize=10.5, fontweight="bold")
    ax.set_xlabel("Relative Change (%) at 20% Peak Error", fontsize=11, fontweight="bold", labelpad=8)
    ax.set_xlim(-52, 92)
    ax.grid(True, axis="x", zorder=0)
    
    # Place labels with ample clearance away from all individual points
    for idx, r in enumerate(rects1):
        val = r.get_width()
        e_pts = edge_indiv[idx]
        if val < 0:
            x_pos = min(e_pts) - 3.2
            ha = "right"
        elif val > 0:
            x_pos = max(e_pts) + 3.2
            ha = "left"
        else:
            x_pos = +4.5
            ha = "left"
        ax.text(x_pos, r.get_y() + r.get_height()/2, f"{val:+.1f}%", va="center", ha=ha, fontsize=9.2, fontweight="bold", color="#0369A1")
        
    for idx, r in enumerate(rects2):
        val = r.get_width()
        v_pts = var_indiv[idx]
        if val < 0:
            x_pos = min(v_pts) - 3.2
            ha = "right"
        elif val > 0:
            x_pos = max(v_pts) + 3.2
            ha = "left"
        else:
            x_pos = +4.5
            ha = "left"
        c = CORAL if val > 20 else AMBER
        ax.text(x_pos, r.get_y() + r.get_height()/2, f"{val:+.1f}%", va="center", ha=ha, fontsize=9.2, fontweight="bold", color=c)
        
    ax.legend(loc="lower right", facecolor="#F8FAFC", edgecolor="#CBD5E1", fontsize=9.0, labelcolor=TEXT_MAIN)
    ax.set_title("Cross-Connectome Means & Individual Datasets", fontsize=12, fontweight="bold", pad=12, color=TEXT_MAIN)
    
    plt.tight_layout()
    out_p = os.path.join(OUT_DIR, "clean_fig_global_fingerprints.png")
    plt.savefig(out_p, dpi=220)
    plt.close()
    print(f"Generated {out_p}")

# -----------------------------------------------------------------------------
# FIGURE 2: Binomial Buffering (Slide 3)
# -----------------------------------------------------------------------------
def generate_fig2_binomial_buffering():
    fig, ax = plt.subplots(figsize=(8.0, 5.2), dpi=220)
    
    rates = np.linspace(0, 20, 10)
    synapse_loss = -rates
    edge_loss = -0.2435 * rates
    
    ax.plot(rates, synapse_loss, color=CORAL, lw=3.2, marker="s", ms=7, label="Total Synapses Removed (1-for-1)", zorder=4)
    ax.plot(rates, edge_loss, color=CYAN, lw=3.2, marker="o", ms=7, label="Actual Edge Count Loss (Buffered)", zorder=4)
    
    ax.fill_between(rates, synapse_loss, edge_loss, color=MINT, alpha=0.14, zorder=2)
    
    ax.annotate("~4× Smaller Edge Loss\nBinomial Model: P(loss) = p^w",
                xy=(14, -7), xytext=(5.5, -14),
                arrowprops=dict(facecolor=MINT, edgecolor=MINT, shrink=0.08, width=1.5, headwidth=7),
                fontsize=10.2, fontweight="bold", color=MINT,
                bbox=dict(boxstyle="round,pad=0.5", facecolor="#F0FDF4", edgecolor=MINT, lw=1.2),
                zorder=6)
    
    ax.set_xlabel("Simulated Missed-Synapse Rate (%)", fontsize=11, fontweight="bold", labelpad=8)
    ax.set_ylabel("Relative Shift in Metric (%)", fontsize=11, fontweight="bold", labelpad=8)
    ax.set_title("The Binomial Buffering Effect (EM1)", fontsize=12.5, fontweight="bold", pad=12, color=TEXT_MAIN)
    ax.set_xlim(0, 20)
    ax.set_ylim(-22, 2)
    ax.grid(True, zorder=0)
    ax.legend(loc="upper right", facecolor="#F8FAFC", edgecolor="#CBD5E1", fontsize=9.5, labelcolor=TEXT_MAIN)
    
    plt.tight_layout()
    out_p = os.path.join(OUT_DIR, "clean_fig_binomial_buffering.png")
    plt.savefig(out_p, dpi=220)
    plt.close()
    print(f"Generated {out_p}")

# -----------------------------------------------------------------------------
# FIGURE 3: Split vs Merge Asymmetry (Slide 4)
# -----------------------------------------------------------------------------
def generate_fig3_split_vs_merge():
    fig, ax = plt.subplots(figsize=(8.4, 5.2), dpi=220)
    
    metrics = ["Edge Count Change", "Total Synapse Change", "Mean Degree", "Largest SCC", "Weight Variance"]
    split_vals = [0.0, 0.0, -14.87, +17.63, 0.0]
    merge_vals = [-10.91, -0.10, -2.60, -8.96, +46.88]
    
    # Individual connectome values [BANC, FAFB, MANC, MCNS, MAOL]
    split_indiv = [
        [0.0, 0.0, 0.0, 0.0, 0.0],                # Edges
        [0.0, 0.0, 0.0, 0.0, 0.0],                # Synapses
        [-12.83, -14.78, -15.93, -14.81, -16.00], # Mean Degree
        [+14.86, +17.59, +18.88, +17.57, +19.24], # Largest Core (SCC)
        [0.0, 0.0, 0.0, 0.0, 0.0],                # Weight Var
    ]
    # Individual connectome values [BANC, FAFB, MANC, MCNS]
    merge_indiv = [
        [-12.18, -16.09, -8.27, -7.12],           # Edges
        [-0.11, -0.12, -0.09, -0.08],             # Synapses
        [-5.13, -8.07, +1.85, +0.95],             # Mean Degree
        [-8.30, -9.33, -9.97, -8.24],             # Largest Core (SCC)
        [+59.87, +64.98, +24.46, +38.20],         # Weight Var
    ]
    
    x = np.arange(len(metrics))
    width = 0.36
    
    rects1 = ax.bar(x - width/2, split_vals, width, label="Split Neurons (n=5) [Mean]", color=MINT, alpha=0.65, edgecolor="none", zorder=3)
    rects2 = ax.bar(x + width/2, merge_vals, width, label="Merged Neurons (n=4) [Mean]", color=CORAL, alpha=0.65, edgecolor="none", zorder=3)
    
    # Overlay individual connectome dots with high contrast
    for i, (s_pts, m_pts) in enumerate(zip(split_indiv, merge_indiv)):
        ax.scatter([x[i] - width/2]*len(s_pts), s_pts, color="#34D399", edgecolors="#0F172A", linewidths=1.2, s=55, zorder=5, label="● Individual Connectomes" if i==0 else "")
        ax.scatter([x[i] + width/2]*len(m_pts), m_pts, color="#F87171", edgecolors="#0F172A", linewidths=1.2, s=55, zorder=5)
    
    ax.axhline(0, color="#94A3B8", linewidth=1.2, linestyle="-", zorder=4)
    ax.set_xticks(x)
    ax.set_xticklabels(metrics, fontsize=9.5, fontweight="bold", rotation=10, ha="right")
    ax.set_ylabel("Relative Change (%) at Highest Tested Error Level (20%)", fontsize=10.5, fontweight="bold", labelpad=8)
    ax.set_title("Splitting vs Merging Head-to-Head", fontsize=12.5, fontweight="bold", pad=12, color=TEXT_MAIN)
    ax.set_ylim(-26, 78)
    ax.grid(True, axis="y", zorder=0)
    
    # Place labels with ample clearance above/below individual points
    for idx, r in enumerate(rects1):
        val = split_vals[idx]
        s_pts = split_indiv[idx]
        if val < 0:
            y_pos = min(s_pts) - 3.2
            va = "top"
        elif val > 0:
            y_pos = max(s_pts) + 3.2
            va = "bottom"
        else:
            y_pos = +2.6
            va = "bottom"
        ax.text(r.get_x() + r.get_width()/2, y_pos, f"{val:+.1f}%", ha="center", va=va, fontsize=8.8, fontweight="bold", color="#047857")
        
    for idx, r in enumerate(rects2):
        val = merge_vals[idx]
        m_pts = merge_indiv[idx]
        if val < 0:
            y_pos = min(m_pts) - 3.2
            va = "top"
        elif val > 0:
            y_pos = max(m_pts) + 3.2
            va = "bottom"
        else:
            y_pos = -4.0
            va = "top"
        ax.text(r.get_x() + r.get_width()/2, y_pos, f"{val:+.1f}%", ha="center", va=va, fontsize=8.8, fontweight="bold", color="#B91C1C")
        
    ax.legend(loc="upper left", facecolor="#F8FAFC", edgecolor="#CBD5E1", fontsize=9.0, labelcolor=TEXT_MAIN)
    
    plt.tight_layout()
    out_p = os.path.join(OUT_DIR, "clean_fig_split_vs_merge.png")
    plt.savefig(out_p, dpi=220)
    plt.close()
    print(f"Generated {out_p}")

# -----------------------------------------------------------------------------
# FIGURE 4: PageRank Stability & Median Weight Association (Slide 5)
# -----------------------------------------------------------------------------
def generate_fig4_pagerank_and_median():
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(8.4, 5.0), dpi=220)
    
    rates = [0, 5, 10, 15, 20]
    pr_em1 = [1.0, 0.9997, 0.9993, 0.9989, 0.9987]
    pr_em2 = [1.0, 0.9985, 0.9970, 0.9955, 0.9937]
    pr_em3 = [1.0, 0.9998, 0.9997, 0.9995, 0.9994]
    pr_em4 = [1.0, 0.9988, 0.9975, 0.9962, 0.9949]
    pr_em5 = [1.0, 0.9972, 0.9945, 0.9918, 0.9892]
    
    ax1.plot(rates, pr_em1, color=CYAN, lw=2.4, label="Missed Synapses (r=0.999)")
    ax1.plot(rates, pr_em2, color=BLUE, lw=2.4, label="False Synapses (r=0.994)")
    ax1.plot(rates, pr_em3, color=MINT, lw=2.4, label="Count Noise (r=0.999)")
    ax1.plot(rates, pr_em4, color=PURPLE_ACC, lw=2.4, label="Split Neurons (r=0.995)")
    ax1.plot(rates, pr_em5, color=CORAL, lw=2.4, label="Merged Neurons (r=0.989)")
    
    ax1.set_xlabel("Error Level (%)", fontsize=10, fontweight="bold")
    ax1.set_ylabel("PageRank Pearson Correlation (r)", fontsize=10, fontweight="bold")
    ax1.set_title("PageRank Similarity to Baseline\n(r ≥ 0.977 across all models)", fontsize=11, fontweight="bold", pad=8, color=TEXT_MAIN)
    ax1.set_ylim(0.975, 1.005)
    ax1.grid(True)
    ax1.legend(loc="lower left", fontsize=7.5, facecolor="#F8FAFC", edgecolor="#CBD5E1", labelcolor=TEXT_MAIN)
    
    # Right Subplot: Scatter Plot of Median Connection Weight vs Edge Count Change
    med_w = [2.0, 2.0, 4.0, 6.0, 9.0]
    edge_changes = [-9.731, -8.916, -3.191, -2.500, -0.007]
    labels = ["MANC", "MAOL", "BANC", "FAFB", "MCNS"]
    colors = [CORAL, CORAL, AMBER, MINT, CYAN]
    
    ax2.scatter(med_w, edge_changes, color=colors, s=80, edgecolors="#0F172A", linewidths=1.3, zorder=5)
    ax2.axhline(0, color="#94A3B8", linewidth=1.2, linestyle="-", zorder=3)
    
    # Annotate points with offsets to prevent overlap (especially MANC and MAOL at med=2.0)
    offsets = [
        (-0.55, -0.9, "right"), # MANC
        (0.35, 0.4, "left"),   # MAOL
        (0.35, 0.4, "left"),   # BANC
        (0.35, 0.4, "left"),   # FAFB
        (-0.35, -0.9, "right")  # MCNS
    ]
    for (x, y, name, (dx, dy, ha)) in zip(med_w, edge_changes, labels, offsets):
        ax2.annotate(f"{name}\n({y:+.2f}%)", xy=(x, y), xytext=(x + dx, y + dy),
                     fontsize=8.4, fontweight="bold", color=TEXT_MAIN, ha=ha, va="center",
                     bbox=dict(boxstyle="round,pad=0.2", facecolor="#F8FAFC", edgecolor="#CBD5E1", alpha=0.9),
                     zorder=6)
        
    ax2.set_xlabel("Median Connection Weight", fontsize=10, fontweight="bold")
    ax2.set_ylabel("Edge Count Change (%) at 20% Missed Synapses", fontsize=9.5, fontweight="bold")
    ax2.set_title("Edge Loss vs Median Weight\n(Observed cross-connectome association)", fontsize=11, fontweight="bold", pad=8, color=TEXT_MAIN)
    ax2.set_xlim(1.0, 10.2)
    ax2.set_ylim(-12.0, 2.0)
    ax2.grid(True, zorder=0)
    
    plt.tight_layout()
    out_p = os.path.join(OUT_DIR, "clean_fig_pagerank_and_median_law.png")
    plt.savefig(out_p, dpi=220)
    plt.close()
    print(f"Generated {out_p}")

def main():
    print("Regenerating all 4 light presentation figures...")
    generate_fig1_fingerprints()
    generate_fig2_binomial_buffering()
    generate_fig3_split_vs_merge()
    generate_fig4_pagerank_and_median()
    print("All 4 clean light presentation figures generated successfully!")

if __name__ == "__main__":
    main()
