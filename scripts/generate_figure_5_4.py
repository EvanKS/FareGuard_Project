"""
Generate Figure 5.4: Inductive Clean-Reference Isolation Forest Anomaly Detection Process.
Clean title positioning, non-overlapping box headers, exact 6.0 x 3.5 in at 300 DPI.
"""
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as patches

def generate_figure():
    fig, ax = plt.subplots(figsize=(6.0, 3.5), dpi=300)

    fig.patch.set_facecolor('#ffffff')
    ax.set_facecolor('#ffffff')

    # Color palette
    c_phase1 = '#1e40af'   # Clean blue
    c_phase2 = '#0369a1'   # Vector cyan
    c_phase3 = '#b45309'   # iForest amber
    c_phase4 = '#b91c1c'   # Triage red
    c_guard  = '#15803d'   # Guard green

    # Helper function to draw rounded boxes
    def draw_box(x, y, w, h, step_num, title, subtitle, color, bg_color):
        rect = patches.FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.012,rounding_size=0.02",
                                      facecolor=bg_color, edgecolor=color, linewidth=1.1)
        ax.add_patch(rect)
        # Header inside box
        ax.text(x + w/2, y + h*0.82, step_num, ha='center', va='center', weight='bold', fontsize=5.8, color=color)
        ax.text(x + w/2, y + h*0.66, title, ha='center', va='center', weight='bold', fontsize=6.0, color='#0f172a')
        # Subtitle description
        ax.text(x + w/2, y + h*0.33, subtitle, ha='center', va='center', fontsize=5.2, color='#334155', linespacing=1.2)

    w = 0.185
    h = 0.29
    y_top = 0.53

    # 1. Nominal data
    draw_box(0.04, y_top, w, h, 
             "STEP 1",
             "Nominal Data", 
             "Historical D_clean\nNominal runs\nZero fraud labels", 
             c_phase1, "#eff6ff")

    # 2. Operational Vector
    draw_box(0.285, y_top, w, h, 
             "STEP 2",
             "Feature Vector", 
             "z_i = [y_hat, y, Δpax,\nR_hat, R, Δrev,\nrev_ratio, I(y==0)]", 
             c_phase2, "#f0f9ff")

    # 3. Isolation Forest
    draw_box(0.53, y_top, w, h, 
             "STEP 3",
             "Isolation Forest", 
             "Unsupervised fit\non clean subspace\nEnsemble iTrees", 
             c_phase3, "#fffbeb")

    # 4. Triage / Scoring
    draw_box(0.775, y_top, w, h, 
             "STEP 4",
             "Triage & Score", 
             "Anomaly Score s_i\nNORMAL (<0.55)\nSUSPICIOUS (0.55)\nHIGH RISK (>0.75)", 
             c_phase4, "#fef2f2")

    # Connecting arrows
    arrow_props = dict(arrowstyle='->', lw=1.3, color='#475569')
    ax.annotate('', xy=(0.285, y_top + h/2), xytext=(0.225, y_top + h/2), arrowprops=arrow_props)
    ax.annotate('', xy=(0.53, y_top + h/2), xytext=(0.47, y_top + h/2), arrowprops=arrow_props)
    ax.annotate('', xy=(0.775, y_top + h/2), xytext=(0.715, y_top + h/2), arrowprops=arrow_props)

    # Barrier callout box
    guard_rect = patches.FancyBboxPatch((0.04, 0.10), 0.92, 0.28, boxstyle="round,pad=0.012,rounding_size=0.02",
                                        facecolor='#f0fdf4', edgecolor=c_guard, linewidth=1.0)
    ax.add_patch(guard_rect)

    ax.text(0.50, 0.32, "STRICT INDUCTIVE INFERENCE & LEAKAGE PREVENTION BARRIER", 
            ha='center', va='center', weight='bold', fontsize=6.8, color=c_guard)

    barrier_desc = (
        "\u2022 Inductive Paradigm: Model isolates discrepancies without needing pre-labeled fraud examples.\n"
        "\u2022 Oracle Shield: Purges 'true_leakage', 'severity', and 'ground_truth' before feature vectorization.\n"
        "\u2022 Multi-Dimensional Ratios: Evaluates passenger deficit (y_hat - y) against revenue deficit (R_hat - R)."
    )
    ax.text(0.50, 0.20, barrier_desc, ha='center', va='center', fontsize=5.8, color='#166534', linespacing=1.3)

    # Arrow from barrier to vectorization step
    ax.annotate('', xy=(0.378, y_top), xytext=(0.378, 0.38), 
                arrowprops=dict(arrowstyle='->', lw=1.1, color=c_guard, linestyle='--'))
    ax.text(0.39, 0.46, "Purged Operational\nSignals Only", ha='left', va='center', fontsize=5.3, color=c_guard, weight='bold')

    ax.set_xlim(0, 1.0)
    ax.set_ylim(0, 1.0)
    ax.axis('off')

    plt.title('Figure 5.4: Inductive Clean-Reference Isolation Forest Anomaly Detection Process', 
              fontsize=9.2, weight='bold', pad=10, color='#0f172a')

    os.makedirs('docs/figures', exist_ok=True)
    out_file = os.path.join('docs', 'figures', 'figure_5_4_isolation_forest_process.png')
    plt.savefig(out_file, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"Saved: {out_file}")

if __name__ == '__main__':
    generate_figure()
