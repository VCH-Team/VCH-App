# main.py
import os
import time
from datetime import datetime
import json
import numpy as np
import matplotlib.pyplot as plt
import materials
from physics import config
from physics import phase_design
from physics import phase_3d
import viewer  # <--- ADDED
import report  # <--- ADDED

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
    if category == "fluid": options = FLUIDS
    elif category == "metal": options = METALS
    elif category == "insulation": options = INSULATORS
    else: options = materials.list_available()

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
            if 0 <= idx < len(options): break
            else: print(f"  Invalid choice. Please enter 1-{len(options)}.")
        except ValueError: print("  Please enter a number.")
            
    name = options[idx]
    try:
        mat = materials.load(name)
    except FileNotFoundError:
        print(f"  [Error] '{name}' not found. Generating cache...")
        materials.check_cache()
        mat = materials.load(name)
    return mat, name

def save_combined_chart(cfg, mat_tank, min_R, max_R, num_R, max_turns, outdir):
    print(f"\n--- PHASE A: Generating Quadrilateral Design Charts ---")
    radii = np.linspace(min_R, max_R, num_R)
    colors = ['blue', 'red', 'green', 'purple', 'orange'][:num_R]

    fig, axes = plt.subplots(1, 3, figsize=(18, 6), sharey=True, sharex=True)
    titles = ["Solid Phase", "Slurry Phase", "Liquid Phase"]
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
        axes[j].set_title(titles[j]); axes[j].set_xlabel("Coil Length (m)")
        axes[j].set_xlim(0, max_L); axes[j].grid(True, alpha=0.3)
        if j == 0: axes[j].set_ylabel("Heat Rate (kW)")
    axes[0].legend(loc="upper left")
    plt.suptitle("Coil Heat Transfer Envelopes", fontsize=16)
    plt.tight_layout()
    
    chart_path = os.path.join(outdir, "design_charts_phases.png")
    plt.savefig(chart_path, dpi=150); plt.close()
    return radii

def main():
    print("=== 3D TANK SIMULATION WIZARD ===")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    outdir = os.path.join("testout", f"run_{timestamp}")
    os.makedirs(outdir, exist_ok=True)
    
    # 1. MATERIALS
    mat_tank, _ = pick_material("Tank Fluid", "fluid", default_idx=1)
    mat_coil, _ = pick_material("Coil Fluid", "fluid", default_idx=0)
    mat_tube, _ = pick_material("Coil Tube Metal", "metal", default_idx=0)
    mat_wall, _ = pick_material("Tank Wall Metal", "metal", default_idx=1)
    
    # 2. GEOMETRY
    print("\n--- Tank Geometry & Walls ---")
    shape = input("Tank shape (cylinder/cuboid) [cylinder]: ").strip().lower() or "cylinder"
    
    if shape == "cylinder":
        r_inner = ask("Tank Radius (m)", 0.5)
        L_tank, W_tank = 0.0, 0.0
    else:
        L_tank = ask("Tank Length (m)", 1.0)
        W_tank = ask("Tank Width (m)", 1.0)
        r_inner = 0.0
        
    tank_height = ask("Tank Height (m)", 1.0)
    res = ask("Grid Resolution (10-50)", 20, int)
    t_wall = ask("Wall Thickness (m)", 0.005)
    
    has_ins = input("Add Insulation? (y/n) [n]: ").strip().lower() == 'y'
    t_ins = 0.0; k_ins = 0.04
    if has_ins:
        t_ins = ask("  Insulation Thickness (m)", 0.05)
        mat_ins, _ = pick_material("Insulation Material", "insulation", default_idx=0)
        k_ins = mat_ins["k_grid"][0]
        
    h_air = ask("Ambient Air Convection (W/m2K)", 10.0)
    
    # 3. OPERATING CONDITIONS
    print("\n--- Operating Conditions ---")
    T_amb_low = ask("Lowest Site Temp / Solid Start (°C)", 5.0)
    T_start = ask("Tank Starting Temp (°C)", 20.0)
    T_target = ask("Target Liquid Temp (°C)", 60.0)
    T_amb_mid = ask("Ambient Environment Temp (°C)", 25.0)
    T_water_in = ask("Coil Inlet Temp (°C)", 80.0)
    flow_m3h = ask("Coil Flow Rate (m3/h)", 1.0)

    # 4. DRAIN & FILL
    print("\n--- Drain & Fill Setup ---")
    sim_drain = input("Enable Drain? (y/n) [n]: ").strip().lower() == 'y'
    drain_r=drain_th=drain_x=drain_y=drain_z=drain_d=drain_pressure=drain_max_flow=0.0
    if sim_drain:
        print("  Drain Location:")
        if shape == "cylinder":
            drain_r = ask("    Radius (m)", 0.0); drain_th = ask("    Angle (deg)", 0.0)
        else:
            drain_x = ask("    X coord (m)", 0.0); drain_y = ask("    Y coord (m)", 0.0)
        drain_z = ask("    Height (m)", 0.01)
        drain_d = ask("    Hole Diameter (m)", 0.05)
        drain_pressure = ask("  Controlled Pressure (Pa) [0 none]", 0.0)
        drain_max_flow = ask("  Max Flow Rate (m3/h) [0 unlimited]", 0.0)

    sim_fill = input("Enable Fill? (y/n) [n]: ").strip().lower() == 'y'
    fill_r=fill_th=fill_x=fill_y=fill_z=fill_d=fill_flow=fill_T=fill_max_flow=0.0
    fill_spread = True
    if sim_fill:
        print("  Fill Location:")
        if shape == "cylinder":
            fill_r = ask("    Radius (m)", 0.0); fill_th = ask("    Angle (deg)", 0.0)
        else:
            fill_x = ask("    X coord (m)", 0.0); fill_y = ask("    Y coord (m)", 0.0)
        fill_z = ask("    Height (m)", tank_height - 0.01)
        fill_d = ask("    Nozzle Diameter (m)", 0.05)
        fill_flow = ask("  Fill Flow Rate (m3/h)", 0.5)
        fill_T = ask("  Fill Temperature (°C)", 20.0)
        fill_max_flow = ask("  Max Flow Rate cap (m3/h) [0 unlimited]", 0.0)
        fill_spread = input("  Positive Pressure? (y/n) [y]: ").strip().lower() != 'n'
    
    # Capacity Check
    if shape == "cylinder": V_tank = np.pi * r_inner**2 * tank_height
    else: V_tank = L_tank * W_tank * tank_height
        
    rho_start = np.interp(T_start, mat_tank["T_grid"], mat_tank["rho_grid"])
    max_mass = V_tank * rho_start
    print(f"  [Info] Max capacity at {T_start}°C is ~{max_mass:.1f} kg.")
    M_fluid = ask(f"Tank Fluid Mass (0-{max_mass:.0f} kg)", max_mass)
    
    # 5. COIL PLACEMENT
    print("\n--- Coil Dimensions & Placement ---")
    d_in = ask("Coil Inner Diameter (m)", 0.0409)
    d_out = ask("Coil Outer Diameter (m)", 0.04826)
    bottom_clearance = ask("Clearance from bottom (m)", 0.05)
    top_clearance = ask("Clearance from top (m)", 0.05)
    L_avail = tank_height - bottom_clearance - top_clearance
    max_possible_turns = int(L_avail / d_out)
    
    # 6. TIME SETTINGS
    print("\n--- Simulation Schedule ---")
    t_window_hr = ask("Heating Phase Duration (hours)", 12.0)
    t_cooldown_hr = ask("Cooling Phase Duration (hours)", 12.0)
    N_cycles = ask("Number of Cycles (Heating + Cooling)", 1, int)
    dt_sec = ask("Time Step Size (seconds)", 1.0)
    snapshot_interval_hr = ask("Snapshot Interval (hours)", 0.1)
    
    # 7. BUILD CONFIG
    cfg = config.with_defaults({
        "tank_shape": shape, "r_inner": r_inner, "tank_height": tank_height, "res": res,
        "tank_length": L_tank, "tank_width": W_tank,
        "d_in": d_in, "d_out": d_out, "t_wall": t_wall, "t_ins": t_ins, "k_ins": k_ins, "h_air": h_air,
        "M_fluid": M_fluid, "T_start": T_start, "T_amb_low": T_amb_low, "T_target": T_target, "T_amb_mid": T_amb_mid,
        "T_water_in": T_water_in, "flow_m3h": flow_m3h,
        "dt_sec": dt_sec, "t_window_hr": t_window_hr, "t_cooldown_hr": t_cooldown_hr, "N_cycles": N_cycles,
        "snapshot_interval_hr": snapshot_interval_hr,
        "coil_clearance_bottom": bottom_clearance, "L_avail": L_avail,
        
        "simulate_drain": sim_drain, 
        "drain_r": drain_r, "drain_theta": drain_th, "drain_x": drain_x, "drain_y": drain_y,
        "drain_z": drain_z, "drain_diameter": drain_d,
        "drain_pressure_pa": drain_pressure, "drain_max_flow_m3h": drain_max_flow,
        
        "simulate_fill": sim_fill, 
        "fill_r": fill_r, "fill_theta": fill_th, "fill_x": fill_x, "fill_y": fill_y,
        "fill_z": fill_z, "fill_diameter": fill_d, "fill_flow_m3h": fill_flow, "fill_T": fill_T,
        "fill_max_flow_m3h": fill_max_flow, "fill_spread": fill_spread,
    })
    
    cfg["T_water_arr"] = mat_coil["T_grid"]; cfg["rho_water_arr"] = mat_coil["rho_grid"]
    cfg["cp_water_arr"] = mat_coil["cp_sens_grid"]; cfg["mu_water_arr"] = mat_coil["mu_grid"]; cfg["k_water_arr"] = mat_coil["k_grid"]
    cfg["T_tube_arr"] = mat_tube["T_grid"]; cfg["k_tube_arr"] = mat_tube["k_grid"]
    cfg["T_wall_arr"] = mat_wall["T_grid"]; cfg["k_wall_arr"] = mat_wall["k_grid"]
    cfg["rho_wall_arr"] = mat_wall["rho_grid"]; cfg["cp_wall_arr"] = mat_wall["cp_sens_grid"]

    # 8. PHASE A
    print("\n--- Phase A Setup ---")
    num_R = ask("How many coil radii to compare? (1-5)", 3, int)
    min_R = ask("Minimum Radius to test (m)", r_inner * 0.3 if shape=="cylinder" else 0.1)
    max_R = ask("Maximum Radius to test (m)", r_inner * 0.9 if shape=="cylinder" else 0.4)
    max_turns = ask(f"Maximum turns to test (1-{max_possible_turns})", max_possible_turns, int)
    
    radii_tested = save_combined_chart(cfg, mat_tank, min_R, max_R, num_R, max_turns, outdir)
    
    # 9. SELECT COIL & RUN
    print("\n--- Coil Selection ---")
    R_coil = ask("Chosen Coil Radius (m)", radii_tested[-1])
    n_turns = ask("Chosen Coil Turns", max_turns // 2, int)

    print(f"\n--- Running 3D Simulation ---")
    t0 = time.time()
    results = phase_3d.run_simulation(cfg, mat_tank, R_coil, n_turns, outdir)
    print(f"Time taken: {time.time() - t0:.1f} seconds")
    
    # 10. SAVE RESULTS FOR REPORT
    clean_results = {
        "total_extracted_kg": float(results["total_extracted_kg"]),
        "total_filled_kg": float(results["total_filled_kg"]),
        "final_mass": float(results["final_mass"]),
        "total_hr": float(results["total_hr"]),
        "cycle_metrics": []
    }
    for c in results["cycle_metrics"]:
        clean_c = {k: float(v) if isinstance(v, (np.floating, float)) else v for k, v in c.items() if k != "snapshot_times"}
        clean_results["cycle_metrics"].append(clean_c)
        
    with open(os.path.join(outdir, "results.json"), "w") as f:
        json.dump(clean_results, f, indent=4)

    # 11. AUTO-GENERATE OUTPUTS
    print(f"\nRun complete! Generating outputs...")
    
    if results["snapshots"]:
        print("  >> Opening 3D Dashboard...")
        try:
            viewer.create_interactive_viewer(outdir)
        except Exception as e:
            print(f"  [Error] Could not open 3D viewer: {e}")
            
    print("  >> Opening HTML Report...")
    try:
        report.generate_report(outdir)
    except Exception as e:
        print(f"  [Error] Could not open HTML report: {e}")

if __name__ == "__main__":
    main()