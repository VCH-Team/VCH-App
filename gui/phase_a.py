import numpy as np
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure

from physics import phase_design

_COLORS = ["blue", "red", "green", "purple", "orange"]


def render_design_chart(cfg, mat_tank, min_R, max_R, num_R, max_turns, out_path, progress=None):
    """Runs the Phase A sweep and saves the envelope chart as a PNG. Returns the tested radii."""
    radii = np.linspace(min_R, max_R, num_R)
    results = []
    for i, R in enumerate(radii):
        results.append(phase_design.compute_ntu_curves(cfg, mat_tank, float(R), int(max_turns)))
        if progress:
            progress(i + 1, num_R)

    is_pcm = len(results[0]["curves"]) == 6
    ncols = 3 if is_pcm else 1
    titles = ["Solid Phase", "Slurry Phase", "Liquid Phase"] if is_pcm else ["Single Phase"]

    fig = Figure(figsize=(6 * ncols, 5.5))
    FigureCanvasAgg(fig)
    axes = np.atleast_1d(fig.subplots(1, ncols, sharey=True, sharex=True))

    max_L = max(float(np.max(r["L"])) for r in results)
    for i, res in enumerate(results):
        L, curves, color = res["L"], res["curves"], _COLORS[i % len(_COLORS)]
        for p in range(ncols):
            lo, hi = curves[2 * p]["Q"] / 1000.0, curves[2 * p + 1]["Q"] / 1000.0
            axes[p].fill_between(L, lo, hi, color=color, alpha=0.3,
                                 label=f"R={radii[i]:.2f} m" if p == 0 else None)
            axes[p].plot(L, lo, color=color, lw=1)
            axes[p].plot(L, hi, color=color, lw=1)

    for j, ax in enumerate(axes):
        ax.set_title(titles[j])
        ax.set_xlabel("Coil Length (m)")
        ax.set_xlim(0, max_L)
        ax.grid(True, alpha=0.3)
    axes[0].set_ylabel("Heat Rate (kW)")
    axes[0].legend(loc="upper left")
    fig.suptitle("Coil Heat Transfer Envelopes", fontsize=16)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    return radii