# IO/pipeline_bridge.py
"""All non-GUI simulation logic — the same code your CLI main.py had,
minus the input() prompts. Called by IO/runner.py."""

import os
import subprocess
import sys
import numpy as np

import materials
from physics import config
from physics import phase_design
from physics import phase_3d

# The material lists that were hardcoded in your CLI.
# These become dropdown options in the GUI.
FLUIDS = ["Water", "RBD Palm Oil", "30% Propylene Glycol"]
METALS = ["Copper", "Stailness Steel", "Mild Steel"]
INSULATORS = [
    "Polyisocyanurate (PIR)", "Polyurethane Foam (PUR)",
    "Extruded Polystyrene (XPS)", "Expanded Polystyrene (EPS)",
    "Cellular Glass (Foamglas)", "Mineral Wool (Rockwool)",
    "Glass Wool (Fiberglass)", "Calcium Silicate",
    "Expanded Perlite", "Flexible Aerogel Blanket",
]

# Lookup table: role name → list of options. Used by the GUI dropdowns.
_ROLE_LISTS = {"fluid": FLUIDS, "metal": METALS, "insulation": INSULATORS}


def list_for_role(role):
    """Returns the dropdown options for a material field."""
    return list(_ROLE_LISTS.get(role, materials.list_available()))


def load_material(name):
    """Loads a material from cache, building the cache first if it's missing.
    This is the same pattern your CLI used inside pick_material()."""
    try:
        return materials.load(name)
    except FileNotFoundError:
        materials.check_cache()
        return materials.load(name)


def build_cfg(inputs, mat_coil, mat_tube, mat_wall):
    """Turns the flat dict the GUI returns into the cfg dict physics expects.

    `inputs` is what form_builder.get_values() returns — a flat dict of all
    user-facing values. `mat_coil`, `mat_tube`, `mat_wall` are loaded material
    dicts whose grids get injected as extra cfg arrays.
    """
    # Start with defaults, then override with user values.
    # config.with_defaults handles any keys the user didn't touch.
    cfg = config.with_defaults({
        "tank_shape": inputs["shape"],
        "r_inner": inputs["r_inner"],
        "tank_height": inputs["tank_height"],
        "res": int(inputs["res"]),
        "t_wall": inputs["t_wall"],
        # If "Add insulation" checkbox is off, force thickness to 0.
        "t_ins": inputs["t_ins"] if inputs["has_ins"] else 0.0,
        "k_ins": inputs["k_ins"],
        "h_air": inputs["h_air"],
        # M_fluid=0 means "fill tank to capacity" — pass None so State handles it.
        "M_fluid": inputs["M_fluid"] if inputs["M_fluid"] > 0 else None,
        "T_start": inputs["T_start"],
        "T_amb_low": inputs["T_amb_low"],
        "T_amb_mid": inputs["T_amb_mid"],
        "T_target": inputs["T_target"],
        "T_water_in": inputs["T_water_in"],
        "flow_m3h": inputs["flow_m3h"],
        "d_in": inputs["d_in"],
        "d_out": inputs["d_out"],
        "coil_clearance_bottom": inputs["bottom_clearance"],
        # Coil length = total height minus top and bottom clearances.
        "L_avail": inputs["tank_height"] - inputs["bottom_clearance"] - inputs["top_clearance"],
        "dt_sec": inputs["dt_sec"],
        "t_window_hr": inputs["t_window_hr"],
        "snapshot_interval_hr": inputs["snapshot_interval_hr"],
        # Drain / fill: only pass non-zero if the checkbox is on.
        "simulate_drain": inputs["sim_drain"],
        "drain_diameter": inputs["drain_d"] if inputs["sim_drain"] else 0.0,
        "simulate_fill": inputs["sim_fill"],
        "fill_diameter": inputs["fill_d"] if inputs["sim_fill"] else 0.0,
        "fill_flow_m3h": inputs["fill_flow"] if inputs["sim_fill"] else 0.0,
        "fill_T": inputs["fill_T"] if inputs["sim_fill"] else inputs["T_amb_mid"],
    })

    # Inject material property grids into cfg.
    # coil.march, phase_design._march_coil, and heat.py read these from cfg
    # (they're not in config.DEFAULTS because they depend on which material
    # the user picked at runtime).
    cfg["T_water_arr"]   = mat_coil["T_grid"]      # coil fluid
    cfg["rho_water_arr"] = mat_coil["rho_grid"]
    cfg["cp_water_arr"]  = mat_coil["cp_sens_grid"]
    cfg["mu_water_arr"]  = mat_coil["mu_grid"]
    cfg["k_water_arr"]   = mat_coil["k_grid"]
    cfg["T_tube_arr"]    = mat_tube["T_grid"]      # coil tube metal
    cfg["k_tube_arr"]    = mat_tube["k_grid"]
    cfg["T_wall_arr"]    = mat_wall["T_grid"]      # tank wall metal
    cfg["k_wall_arr"]    = mat_wall["k_grid"]
    cfg["rho_wall_arr"]  = mat_wall["rho_grid"]
    cfg["cp_wall_arr"]   = mat_wall["cp_sens_grid"]

    return cfg


def run_phase_a(cfg, mat_tank, min_R, max_R, num_R, max_turns, outdir):
    """Builds the 3-panel design chart (Solid / Slurry / Liquid phases).

    This is a direct port of save_combined_chart() from your CLI main.py.
    """
    # Agg backend = no GUI window; we just save the file.
    # Needed because Tk owns the display and matplotlib shouldn't grab it.
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    # One curve per coil radius to compare.
    radii = np.linspace(min_R, max_R, int(num_R))
    colors = ['blue', 'red', 'green', 'purple', 'orange'][:len(radii)]

    # Three panels side by side: Solid phase | Slurry phase | Liquid phase.
    fig, axes = plt.subplots(1, 3, figsize=(18, 6), sharey=True, sharex=True)
    titles = ["Solid Phase", "Slurry Phase", "Liquid Phase"]
    max_L = 0.0

    for i, R in enumerate(radii):
        # Ask phase_design for Q vs L for this radius.
        # Returns 6 curves for a PCM (Solid-low/high, Slurry-low/high, Liquid-low/high)
        # or 2 curves for a single-phase fluid.
        res = phase_design.compute_ntu_curves(cfg, mat_tank, R, int(max_turns))
        L, curves, color = res["L"], res["curves"], colors[i]
        max_L = max(max_L, float(np.max(L)))

        if len(curves) == 6:
            # PCM: each panel shows a band between low and high temp limits.
            axes[0].fill_between(L, curves[0]["Q"]/1000, curves[1]["Q"]/1000,
                                 color=color, alpha=0.3, label=f"R={R:.2f}m")
            axes[0].plot(L, curves[0]["Q"]/1000, color=color, lw=1)
            axes[0].plot(L, curves[1]["Q"]/1000, color=color, lw=1)
            axes[1].fill_between(L, curves[2]["Q"]/1000, curves[3]["Q"]/1000,
                                 color=color, alpha=0.3)
            axes[1].plot(L, curves[2]["Q"]/1000, color=color, lw=1)
            axes[1].plot(L, curves[3]["Q"]/1000, color=color, lw=1)
            axes[2].fill_between(L, curves[4]["Q"]/1000, curves[5]["Q"]/1000,
                                 color=color, alpha=0.3)
            axes[2].plot(L, curves[4]["Q"]/1000, color=color, lw=1)
            axes[2].plot(L, curves[5]["Q"]/1000, color=color, lw=1)
        else:
            # Single-phase fluid: all curves on the Liquid panel only.
            axes[2].fill_between(L, curves[0]["Q"]/1000, curves[1]["Q"]/1000,
                                 color=color, alpha=0.3, label=f"R={R:.2f}m")
            axes[2].plot(L, curves[0]["Q"]/1000, color=color, lw=1)
            axes[2].plot(L, curves[1]["Q"]/1000, color=color, lw=1)

    # Cosmetics: titles, axes, grid, legend, ylabel on left panel only.
    for j in range(3):
        axes[j].set_title(titles[j])
        axes[j].set_xlabel("Coil Length (m)")
        axes[j].set_xlim(0, max_L)
        axes[j].grid(True, alpha=0.3)
        if j == 0:
            axes[j].set_ylabel("Heat Rate (kW)")
    axes[0].legend(loc="upper left")
    plt.suptitle("Coil Heat Transfer Envelopes", fontsize=16)
    plt.tight_layout()

    # Save the PNG into the run folder and hand the path back to the GUI.
    chart_path = os.path.join(outdir, "design_charts_phases.png")
    plt.savefig(chart_path, dpi=150)
    plt.close()
    return list(map(float, radii)), chart_path


def run_3d(cfg, mat_tank, R_coil, n_turns, outdir,
           progress_cb=None, cancel_flag=None):
    """Thin wrapper around phase_3d.run_simulation.
    progress_cb and cancel_flag are threaded through so the GUI can show
    progress and the user can hit Cancel."""
    return phase_3d.run_simulation(
        cfg, mat_tank, R_coil, n_turns, outdir,
        progress_cb=progress_cb, cancel_flag=cancel_flag,
    )


def open_path(path):
    """Cross-platform 'open this file with the default app'.
    Used by the dashboard's 'Open chart' button."""
    if not path or not os.path.exists(path):
        return
    if sys.platform.startswith("win"):
        os.startfile(path)
    elif sys.platform == "darwin":
        subprocess.call(["open", path])
    else:
        subprocess.call(["xdg-open", path])