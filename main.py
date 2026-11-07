# main.py
import os
import time
from datetime import datetime
import numpy as np
import matplotlib.pyplot as plt
import materials
from physics import config
from physics import phase_design
from physics import phase_3d

# --- PRE-DEFINED LISTS (Matching your Excel) ---
FLUIDS = ["Water", "RBD Palm Oil", "30% Propylene Glycol"]
METALS = ["Copper", "Stailness Steel", "Mild Steel"]
INSULATORS = [
    "Polyisocyanurate (PIR)", "Polyurethane Foam (PUR)", "Extruded Polystyrene (XPS)",
    "Expanded Polystyrene (EPS)", "Cellular Glass (Foamglas)", "Mineral Wool (Rockwool)",
    "Glass Wool (Fiberglass)", "Calcium Silicate", "Expanded Perlite", "Flexible Aerogel Blanket"
]

def ask(prompt, default, cast=float):
    val = input(f"{prompt} [{default}]: ").strip()
    return cast(val) if val else default

def pick_material(title, category="fluid", default_idx=0):
    """Presents a numbered list of materials and returns the selected one."""
    if category == "fluid":
        options = FLUIDS
    elif category == "metal":
        options = METALS
    elif category == "insulation":
        options = INSULATORS
    else:
        options = materials.list_available()

    print(f"\n--- {title} ---")
    for i, name in enumerate(options):
        print(f"  [{i+1}] {name}")
        
    while True:
        user_in = input(f"Select material (1-{len(options)}) [{default_idx+1}]: ").strip()
        if not user_in:
            idx = default_idx
            break
        try:
            idx = int(user_in) - 1
            if 0 <= idx < len(options):
                break
            else:
                print(f"  Invalid choice. Please enter 1-{len(options)}.")
        except ValueError:
            print("  Please enter a number.")
            
    name = options[idx]
    try:
        mat = materials.load(name)
    except FileNotFoundError:
        print(f"  [Error] '{name}' not found in cache. Generating cache, please wait...")
        materials.check_cache()
        mat = materials.load(name)
        
    return mat, name

def save_combined_chart(cfg, mat_tank, min_R, max_R, num_R, max_turns, outdir):
    print(f"\n--- PHASE A: Generating Quadrilateral Design Charts ---")
    radii = np.linspace(min_R, max_R, num_R)
    colors = ['blue', 'red', 'green', 'purple', 'orange'][:num_R]

    fig, axes = plt.subplots(1, 3, figsize=(18, 6), sharey=True, sharex=True)
    titles = ["Solid Phase (Cold to Melt)", "Slurry Phase (Melting)", "Liquid Phase (Melt to Target)"]
    max_L = 0

    for i, R in enumerate(radii):
        res = phase_design.compute_ntu_curves(cfg, mat_tank, R, max_turns)
        L = res["L"]
        max_L = max(max_L, np.max(L))
        color = colors[i]
        curves = res["curves"]

        if len(curves) == 6:
            axes[0].fill_between(L, curves[0]["Q"]/1000.0, curves[1]["Q"]/1000.0, color=color, alpha=0.3, label=f"R={R:.2f}m")
            axes[0].plot(L, curves[0]["Q"]/1000.0, color=color, lw=1); axes[0].plot(L, curves[1]["Q"]/1000.0, color=color, lw=1)
            
            axes[1].fill_between(L, curves[2]["Q"]/1000.0, curves[3]["Q"]/1000.0, color=color, alpha=0.3)
            axes[1].plot(L, curves[2]["Q"]/1000.0, color=color, lw=1); axes[1].plot(L, curves[3]["Q"]/1000.0, color=color, lw=1)
            
            axes[2].fill_between(L, curves[4]["Q"]/1000.0, curves[5]["Q"]/1000.0, color=color, alpha=0.3)
            axes[2].plot(L, curves[4]["Q"]/1000.0, color=color, lw=1); axes[2].plot(L, curves[5]["Q"]/1000.0, color=color, lw=1)
        else:
            axes[2].fill_between(L, curves[0]["Q"]/1000.0, curves[1]["Q"]/1000.0, color=color, alpha=0.3, label=f"R={R:.2f}m")
            axes[2].plot(L, curves[0]["Q"]/1000.0, color=color, lw=1); axes[2].plot(L, curves[1]["Q"]/1000.0, color=color, lw=1)

    for j in range(3):
        axes[j].set_title(titles[j])
        axes[j].set_xlabel("Coil Length (m)")
        axes[j].set_xlim(0, max_L)
        axes[j].grid(True, alpha=0.3)
        if j == 0:
            axes[j].set_ylabel("Heat Rate (kW)")
    axes[0].legend(loc="upper left")
    plt.suptitle("Coil Heat Transfer Envelopes by Phase", fontsize=16)
    plt.tight_layout()
    
    chart_path = os.path.join(outdir, "design_charts_phases.png")
    plt.savefig(chart_path, dpi=150); plt.close()
    print(f"  >> Design Charts saved to: {chart_path}")
    return radii

def main():
    print("=== 3D TANK SIMULATION WIZARD ===")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    outdir = os.path.join("testout", f"run_{timestamp}")
    os.makedirs(outdir, exist_ok=True)
    
    # 1. MATERIALS (Using the numbered lists)
    mat_tank, name_tank = pick_material("Tank Fluid", "fluid", default_idx=1) # Default Palm Oil
    mat_coil, name_coil = pick_material("Coil Fluid", "fluid", default_idx=0) # Default Water
    mat_tube, name_tube = pick_material("Coil Tube Metal", "metal", default_idx=0) # Default Copper
    mat_wall, name_wall = pick_material("Tank Wall Metal", "metal", default_idx=1) # Default SS
    
    # 2. GEOMETRY
    print("\n--- Tank Geometry & Walls ---")
    shape = input("Tank shape (cylinder/cuboid) [cylinder]: ").strip().lower() or "cylinder"
    r_inner = ask("Tank Radius (m)", 0.5)
    tank_height = ask("Tank Height (m)", 1.0)
    res = ask("Grid Resolution (10-50)", 20, int)
    t_wall = ask("Wall Thickness (m)", 0.005)
    
    has_ins = input("Add Insulation? (y/n) [n]: ").strip().lower() == 'y'
    t_ins = 0.0
    k_ins = 0.04
    if has_ins:
        t_ins = ask("  Insulation Thickness (m)", 0.05)
        mat_ins, name_ins = pick_material("Insulation Material", "insulation", default_idx=0)
        k_ins = mat_ins["k_grid"][0]
        print(f"  [Info] Using {name_ins} (k={k_ins:.3f} W/mK)")
        
    h_air = ask("Ambient Air Convection (W/m2K)", 10.0)
    
    # 3. OPERATING CONDITIONS
    print("\n--- Operating Conditions ---")
    T_amb_low = ask("Lowest Site Temperature / Solid Start (°C)", 5.0)
    T_start = ask("Tank Starting Temperature (°C)", 20.0)
    T_target = ask("Target Liquid Temperature (°C)", 60.0)
    T_amb_mid = ask("Ambient Environment Temperature (°C)", 25.0)
    T_water_in = ask("Coil Inlet Temperature (°C)", 80.0)
    flow_m3h = ask("Coil Flow Rate (m3/h)", 1.0)
    
    # Capacity Check
    if shape == "cylinder":
        V_tank = np.pi * r_inner**2 * tank_height
    else:
        L = ask("Tank Length (m)", 1.0)
        W = ask("Tank Width (m)", 1.0)
        V_tank = L * W * tank_height
        
    rho_start = np.interp(T_start, mat_tank["T_grid"], mat_tank["rho_grid"])
    max_mass = V_tank * rho_start
    print(f"  [Info] Maximum capacity at {T_start}°C is ~{max_mass:.1f} kg.")
    M_fluid = ask(f"Tank Fluid Mass (0-{max_mass:.0f} kg)", max_mass)
    
    # 4. COIL PLACEMENT
    print("\n--- Coil Dimensions & Placement ---")
    d_in = ask("Coil Inner Diameter (m)", 0.0409)
    d_out = ask("Coil Outer Diameter (m)", 0.04826)
    bottom_clearance = ask("Clearance from bottom (m)", 0.05)
    top_clearance = ask("Clearance from top (m)", 0.05)
    L_avail = tank_height - bottom_clearance - top_clearance
    max_possible_turns = int(L_avail / d_out)
    print(f"  [Info] Max turns based on pitch ({d_out}m) is {max_possible_turns}.")
    
    # 5. TIME SETTINGS
    print("\n--- Simulation Time Settings ---")
    t_window_hr = ask("Simulation Duration (hours)", 1.0)
    dt_sec = ask("Time Step Size (seconds)", 1.0)
    snapshot_interval_hr = ask("Snapshot Interval (hours)", 0.1)
    
    # 6. BUILD CONFIG
    cfg = config.with_defaults({
        "tank_shape": shape, "r_inner": r_inner, "tank_height": tank_height, "res": res,
        "d_in": d_in, "d_out": d_out, "t_wall": t_wall, "t_ins": t_ins, "k_ins": k_ins, "h_air": h_air,
        "M_fluid": M_fluid, "T_start": T_start, "T_amb_low": T_amb_low, "T_target": T_target, "T_amb_mid": T_amb_mid,
        "T_water_in": T_water_in, "flow_m3h": flow_m3h,
        "dt_sec": dt_sec, "t_window_hr": t_window_hr, "snapshot_interval_hr": snapshot_interval_hr,
        "coil_clearance_bottom": bottom_clearance, "L_avail": L_avail,
        "simulate_drain": False, "simulate_fill": False,
    })
    
    cfg["T_water_arr"] = mat_coil["T_grid"]; cfg["rho_water_arr"] = mat_coil["rho_grid"]
    cfg["cp_water_arr"] = mat_coil["cp_sens_grid"]; cfg["mu_water_arr"] = mat_coil["mu_grid"]; cfg["k_water_arr"] = mat_coil["k_grid"]
    cfg["T_tube_arr"] = mat_tube["T_grid"]; cfg["k_tube_arr"] = mat_tube["k_grid"]
    cfg["T_wall_arr"] = mat_wall["T_grid"]; cfg["k_wall_arr"] = mat_wall["k_grid"]
    cfg["rho_wall_arr"] = mat_wall["rho_grid"]; cfg["cp_wall_arr"] = mat_wall["cp_sens_grid"]

    # 7. PHASE A
    print("\n--- Phase A Setup ---")
    num_R = ask("How many coil radii to compare? (1-5)", 3, int)
    min_R = ask("Minimum Radius to test (m)", r_inner * 0.3)
    max_R = ask("Maximum Radius to test (m)", r_inner * 0.9)
    max_turns = ask(f"Maximum turns to test (1-{max_possible_turns})", max_possible_turns, int)
    
    radii_tested = save_combined_chart(cfg, mat_tank, min_R, max_R, num_R, max_turns, outdir)
    
    # 8. SELECT COIL & RUN
    print("\n--- Coil Selection ---")
    R_coil = ask("Chosen Coil Radius (m)", radii_tested[-1])
    n_turns = ask("Chosen Coil Turns", max_turns // 2, int)

    print(f"\n--- Running 3D Simulation ---")
    t0 = time.time()
    results = phase_3d.run_simulation(cfg, mat_tank, R_coil, n_turns, outdir)
    print(f"Time taken: {time.time() - t0:.1f} seconds")
    print(f"\nRun complete! Open {outdir} to see your data.")
    print("To view the dashboard, run: python viewer.py")

if __name__ == "__main__":
    main()