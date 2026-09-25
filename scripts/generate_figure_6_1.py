"""
Generate Figure 6.1: Microservices Container Interaction and Communication Flowchart.
Dimensions: 6.0 in x 3.5 in at 300 DPI.
Clean layout, straight orthogonal connecting lines, clear labels.
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

    # Draw Outer Docker Network Container
    net_box = patches.FancyBboxPatch((0.02, 0.04), 0.96, 0.88, boxstyle="round,pad=0.015,rounding_size=0.025",
                                     facecolor='#f8fafc', edgecolor='#94a3b8', linewidth=1.1, linestyle='--')
    ax.add_patch(net_box)
    ax.text(0.05, 0.88, "Docker Compose Network: fareguard_default (Bridge)", fontsize=6.5, weight='bold', color='#475569')

    # Service Boxes
    def draw_service(x, y, w, h, name, tech, ports, color_theme, bg):
        box = patches.FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.012,rounding_size=0.018",
                                     facecolor=bg, edgecolor=color_theme, linewidth=1.2)
        ax.add_patch(box)
        ax.text(x + w/2, y + h*0.75, name, ha='center', va='center', weight='bold', fontsize=6.2, color=color_theme)
        ax.text(x + w/2, y + h*0.48, tech, ha='center', va='center', fontsize=5.3, color='#1e293b', linespacing=1.2)
        ax.text(x + w/2, y + h*0.20, ports, ha='center', va='center', fontsize=4.9, color='#64748b', family='monospace')

    # Coordinates
    w = 0.20
    h = 0.31

    # 1. Telemetry Producer
    draw_service(0.05, 0.51, w, h, 
                 "ETM / Telemetry", 
                 "Transit Bus ETMs\n& Synthetic Feeds", 
                 "Port: Stream", 
                 '#0f766e', '#f0fdfa')

    # 2. Redis Message Broker
    draw_service(0.36, 0.51, w, h, 
                 "Message Broker", 
                 "Redis 7.2 Alpine\nStreams & DLQ", 
                 "Port: 6379", 
                 '#b91c1c', '#fef2f2')

    # 3. FastAPI Core Backend
    draw_service(0.67, 0.51, 0.28, h, 
                 "FastAPI Core API", 
                 "Uvicorn ASGI Service\n14 REST Endpoints", 
                 "Port: 8000", 
                 '#7c3aed', '#f5f3ff')

    # 4. PostgreSQL Database
    draw_service(0.36, 0.10, w, h, 
                 "Persistence Layer", 
                 "PostgreSQL 16 / SQLite\nACID Audit Ledger", 
                 "Port: 5432", 
                 '#1d4ed8', '#eff6ff')

    # 5. Streamlit Operations UI
    draw_service(0.67, 0.10, 0.28, h, 
                 "Operations Center", 
                 "Streamlit UI v2\nSignal Ledger Surface", 
                 "Port: 8501", 
                 '#c2410c', '#fff7ed')

    # Flow arrows
    arrow_props = dict(arrowstyle='->', lw=1.2, color='#334155')
    bi_arrow_props = dict(arrowstyle='<->', lw=1.2, color='#334155')

    # ETM -> Redis
    ax.annotate('', xy=(0.36, 0.665), xytext=(0.25, 0.665), arrowprops=arrow_props)
    ax.text(0.305, 0.69, "Events", ha='center', va='bottom', fontsize=5.2, color='#334155', weight='bold')

    # Redis <-> FastAPI
    ax.annotate('', xy=(0.67, 0.665), xytext=(0.56, 0.665), arrowprops=bi_arrow_props)
    ax.text(0.615, 0.69, "Stream/DLQ", ha='center', va='bottom', fontsize=5.2, color='#334155', weight='bold')

    # FastAPI <-> Postgres (Down then Left)
    ax.annotate('', xy=(0.56, 0.255), xytext=(0.67, 0.255), arrowprops=bi_arrow_props)
    ax.text(0.615, 0.28, "SQLAlchemy", ha='center', va='bottom', fontsize=5.2, color='#334155', weight='bold')

    # FastAPI <-> Streamlit (Vertical)
    ax.annotate('', xy=(0.81, 0.41), xytext=(0.81, 0.51), arrowprops=bi_arrow_props)
    ax.text(0.825, 0.46, "HTTP / REST", ha='left', va='center', fontsize=5.2, color='#334155', weight='bold')

    ax.set_xlim(0, 1.0)
    ax.set_ylim(0, 1.0)
    ax.axis('off')

    plt.title('Figure 6.1: Microservices Container Interaction and Communication Flowchart', 
              fontsize=9.2, weight='bold', pad=10, color='#0f172a')

    os.makedirs('docs/figures', exist_ok=True)
    out_file = os.path.join('docs', 'figures', 'figure_6_1_microservices_flowchart.png')
    plt.savefig(out_file, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"Saved: {out_file}")

if __name__ == '__main__':
    generate_figure()
