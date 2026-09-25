"""
Generate Figure 5.3: Temporal Train/Validation/Test Split for Zero Future-Data Leakage.
Dimensions: 6.0 in x 3.5 in at 300 DPI, clean spacing, perfect text centering and alignment.
"""
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as patches

def generate_figure():
    # 6.0 x 3.5 inches
    fig, ax = plt.subplots(figsize=(6.0, 3.5), dpi=300)

    c_train = '#1e40af'   # Deep Blue
    c_val   = '#ea580c'   # Vibrant Amber/Orange
    c_test  = '#16a34a'   # Green

    fig.patch.set_facecolor('#ffffff')
    ax.set_facecolor('#ffffff')

    # Main split bar coordinates
    y = 0.54
    h = 0.20

    # Draw segments
    ax.add_patch(patches.Rectangle((0, y), 0.70, h, facecolor=c_train, edgecolor='#0f172a', linewidth=1.2))
    ax.add_patch(patches.Rectangle((0.70, y), 0.15, h, facecolor=c_val, edgecolor='#0f172a', linewidth=1.2))
    ax.add_patch(patches.Rectangle((0.85, y), 0.15, h, facecolor=c_test, edgecolor='#0f172a', linewidth=1.2))

    # Internal labels
    ax.text(0.35, y + h/2, 'Training Set (70%)\nStrict Historical Baseline\n[Fit Demand Predictor]', 
            ha='center', va='center', color='white', weight='bold', fontsize=7.6)
    ax.text(0.775, y + h/2, 'Val (15%)\nTuning', 
            ha='center', va='center', color='white', weight='bold', fontsize=7.2)
    ax.text(0.925, y + h/2, 'Test (15%)\nEvaluation', 
            ha='center', va='center', color='white', weight='bold', fontsize=7.2)

    # Timeline Arrow
    ax.annotate('', xy=(1.02, 0.44), xytext=(-0.02, 0.44),
                arrowprops=dict(arrowstyle='->', lw=1.8, color='#334155'))
    ax.text(0.5, 0.38, 'Chronological Time Horizon (date + scheduled_start)  \u2192', 
            ha='center', va='center', fontsize=7.6, weight='bold', color='#1e293b')

    # Cutoff indicators
    ax.plot([0.70, 0.70], [0.44, 0.83], color='#dc2626', linestyle='--', linewidth=1.4)
    ax.plot([0.85, 0.85], [0.44, 0.83], color='#dc2626', linestyle='--', linewidth=1.4)

    # Offset labels so they don't overlap
    ax.text(0.67, 0.86, 'Split 1 (T_train)\nPast Horizon Frozen', ha='right', va='bottom', fontsize=6.8, color='#b91c1c', weight='bold')
    ax.text(0.88, 0.86, 'Split 2 (T_val)\nZero Future Leakage', ha='left', va='bottom', fontsize=6.8, color='#b91c1c', weight='bold')

    # Summary callout block
    bbox_props = dict(boxstyle='round,pad=0.45', facecolor='#f8fafc', edgecolor='#cbd5e1', lw=0.9)
    guarantee_text = (
        "Zero Future-Data Leakage Guarantees:\n"
        "\u2022 Strict Chronological Split: No random or shuffled cross-validation across time.\n"
        "\u2022 Windowed Feature Priors: Demand baselines computed exclusively on t < T_split.\n"
        "\u2022 Oracle Flag Isolation: Ground-truth leakage & fraud labels purged from inference."
    )
    ax.text(0.5, 0.16, guarantee_text, ha='center', va='center', fontsize=6.8, color='#334155', bbox=bbox_props, linespacing=1.35)

    ax.set_xlim(-0.04, 1.04)
    ax.set_ylim(0, 1.02)
    ax.axis('off')

    plt.title('Figure 5.3: Temporal Train / Validation / Test Split Strategy', 
              fontsize=9.5, weight='bold', pad=8, color='#0f172a')

    os.makedirs('docs/figures', exist_ok=True)
    out_file = os.path.join('docs', 'figures', 'figure_5_3_temporal_split.png')
    plt.savefig(out_file, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"Saved: {out_file}")

if __name__ == '__main__':
    generate_figure()
