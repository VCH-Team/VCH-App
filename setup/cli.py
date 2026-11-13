# setup/cli.py
import os
import numpy as np
import matplotlib.pyplot as plt

from setup import db_loader, config, phase_design

FLUIDS = ["Water", "RBD Palm Oil", "30% Propylene Glycol"]
METALS = ["Copper", "Stailness Steel", "Mild Steel"]
INSULATORS = ["Polyisocyanurate (PIR)", "Polyurethane Foam (PUR)", "Extruded Polystyrene (XPS)", "Expanded Polystyrene (EPS)", "Cellular Glass (Foamglas)", "Mineral Wool (Rockwool)", "Glass Wool (Fiberglass)", "Calcium Silicate", "Expanded Perlite", "Flexible Aerogel Blanket"]

GROUND_MATERIALS = {
    "Concrete": 1.7,
    "Soil": 0.5,
    "Sand": 0.3,
    "Wood": 0.15,
    "Gravel": 0.7
}

def ask(prompt, default, cast=float):
    val = input(f"{prompt} [{default}]: ").strip()
    return cast(val) if val else default

def pick_material(title, category="fluid", default_idx=0):
    options = FLUIDS if category == "fluid" else METALS if category == "metal" else INSULATORS
    print(f"\n--- {title} ---")
    for i, name in enumerate(options): print(f"  [{i+1}] {name}")
    while True:
        user_in = input(f"Select material (1-{len(options)}) [{default_idx+1}]: ").strip()
        if not user_in: idx = default_idx; break
        try:
            idx = int(user_in) - 1
            if 0 <= idx < len(options): break
            else: print(f"  Invalid choice.")
        except ValueError: print("  Please enter a number.")
    return db_loader.load(options[idx]), options[idx]

def save_combined_chart(cfg, mat_tank, min_R, max_R, num_R, max_turns, outdir):
    print(f"\n--- PHASE A: Generating Charts ---")
    radii = np.linspace(min_R, max_R, num_R)
    colors = ['blue', 'red', 'green', 'purple', 'orange'][:num_R]
    fig, axes = plt.subplots(1, 3, figsize=(18, 6), sharey=True, sharex=True)
    titles = ["Solid Phase", "Slurry Phase", "Liquid Phase"]
    max_L = 0
    for i, R in enumerate(radii):
        res = phase_design.compute_ntu_curves(cfg, mat_tank, R, max_turns)
        L = res["L"]; max_L = max(max_L, np.max(L)); color = colors[i]; curves = res["curves"]
        if len(curves) == 6:
            axes[0].fill_between(L, curves[0]["Q"]/1000.0, curves[1]["Q"]/1000.0, color=color, alpha=0.3, label=f"R={R:.2f}m")
            axes[1].fill_between(L, curves[2]["Q"]/1000.0, curves[3]["Q"]/1000.0, color=color, alpha=0.3)
            axes[2].fill_between(L, curves[4]["Q"]/1000.0, curves[5]["Q"]/1000.0, color=color, alpha=0.3)
        else:
            axes[2].fill_between(L, curves[0]["Q"]/1000.0, curves[1]["Q"]/1000.0, color=color, alpha=0.3, label=f"R={R:.2f}m")
    for j in range(3):
        axes[j].set_title(titles[j]); axes[j].set_xlabel("Coil Length (m)"); axes[j].set_xlim(0, max_L); axes[j].grid(True, alpha=0.3)
    plt.suptitle("Coil Heat Transfer Envelopes"); plt.tight_layout()
    plt.savefig(os.path.join(outdir, "design_charts_phases.png"), dpi=150); plt.close()
    return radii

def get_user_inputs(outdir):
    """Runs the entire CLI and returns the finalized configuration and materials."""
    db_loader.check_and_build_cache()
    thresh_liq, thresh_visc = db_loader.load_settings()
    
    mat_tank, _ = pick_material("Tank Fluid", "fluid", default_idx=1)
    mat_coil, _ = pick_material("Coil Fluid", "fluid", default_idx=0)
    mat_tube, _ = pick_material("Coil Tube Metal", "metal", default_idx=0)
    mat_wall, _ = pick_material("Tank Wall Metal", "metal", default_idx=1)
    
    print("\n--- Tank Geometry ---")
    shape = input("Tank shape (cylinder/cuboid) [cylinder]: ").strip().lower() or "cylinder"
    r_inner = ask("Tank Radius (m)", 0.5) if shape == "cylinder" else 0.0
    L_tank = ask("Tank Length (m)", 1.0) if shape == "cuboid" else 0.0
    W_tank = ask("Tank Width (m)", 1.0) if shape == "cuboid" else 0.0
    tank_height = ask("Tank Height (m)", 1.0)
    res = ask("Grid Resolution (10-50)", 20, int)
    t_wall = ask("Wall Thickness (m)", 0.005)
    
    print("\n--- 2D Slice Visualization ---")
    slice_angles = []
    if shape == "cylinder":
        while True:
            try:
                s1 = ask("  Slice 1 Angle (0-360 deg)", 0.0)
                s2 = ask("  Slice 2 Angle (0-360 deg)", 90.0)
                diff = abs(s1 - s2)
                if 30 <= diff <= 180:
                    slice_angles = [s1, s2]
                    break
                else:
                    print(f"  [Invalid] Difference must be between 30° and 180°. (Current diff: {diff:.1f}°)")
            except ValueError:
                print("  Please enter valid numbers.")
    else:
        print("  Available planes for Cuboid:")
        print("    [1] X-Axis Plane (0°)")
        print("    [2] Y-Axis Plane (90°)")
        print("    [3] Diagonal Plane (45°)")
        while True:
            try:
                c1 = int(input("  Select first slice (1-3) [1]: ").strip() or "1")
                c2 = int(input("  Select second slice (1-3) [2]: ").strip() or "2")
                if c1 == c2 or c1 not in [1, 2, 3] or c2 not in [1, 2, 3]:
                    print("  [Invalid] Please select two different valid options.")
                    continue
                mapping = {1: 0.0, 2: 90.0, 3: 45.0}
                slice_angles = [mapping[c1], mapping[c2]]
                break
            except ValueError:
                print("  Please enter numbers 1-3.")

    has_ins = input("Add side insulation? (y/n) [n]: ").strip().lower() == 'y'
    t_ins, k_ins = (ask("  Side Insulation Thickness (m)", 0.05), 0.04)
    if has_ins: k_ins = pick_material("Insulation", "insulation")[0]["k_grid"][0]
    
    print("\n--- Tank Mounting ---")
    mount_choice = input("Mounting [1] Elevated on legs, [2] Directly on ground [1]: ").strip() or "1"
    grounded = (mount_choice == "2")
    
    has_ins_bottom = input("Add bottom insulation? (y/n) [n]: ").strip().lower() == 'y'
    t_ins_bottom = 0.0
    if has_ins_bottom:
        t_ins_bottom = ask("  Bottom Insulation Thickness (m)", 0.05)
        
    k_ground = 1.7
    L_ground = 1.0
    if grounded:
        print("\n--- Ground Material ---")
        g_mats = list(GROUND_MATERIALS.keys())
        for i, m in enumerate(g_mats): print(f"  [{i+1}] {m}")
        g_choice = input(f"Select ground material (1-{len(g_mats)}) [1]: ").strip() or "1"
        try:
            idx = int(g_choice) - 1
            k_ground = GROUND_MATERIALS[g_mats[idx]] if 0 <= idx < len(g_mats) else GROUND_MATERIALS[g_mats[0]]
        except:
            k_ground = GROUND_MATERIALS[g_mats[0]]
            
    h_air = ask("Ambient Air Convection (W/m2K)", 10.0)
    
    print("\n--- Operating Conditions ---")
    T_amb_low, T_start, T_target, T_amb_mid = ask("Lowest Temp (°C)", 5.0), ask("Starting Temp (°C)", 20.0), ask("Target Temp (°C)", 60.0), ask("Ambient Temp (°C)", 25.0)
    T_water_in, flow_m3h = ask("Coil Inlet Temp (°C)", 80.0), ask("Coil Flow Rate (m3/h)", 1.0)

    print("\n--- Drain Setup ---")
    sim_drain = input("Enable Drain? (y/n) [n]: ").strip().lower() == 'y'
    drain_r = drain_theta = drain_x = drain_y = drain_z = drain_d = 0.0
    drain_max_flow = 0.0
    pump_max_visc = 1e6
    pump_chunk_tol = 100.0
    pump_head = 0.0
    motor_power = 0.0
    
    if sim_drain:
        if shape == "cylinder":
            drain_r = ask("  Drain Radius from center (m)", 0.0)
            drain_theta = ask("  Drain Angle (degrees)", 0.0)
        else:
            drain_x = ask("  Drain X coordinate (m)", 0.0)
            drain_y = ask("  Drain Y coordinate (m)", 0.0)
        drain_z = ask("  Drain Height from bottom (m)", 0.01)
        drain_d = ask("  Drain Hole Diameter (m)", 0.05)
        
        print("  Select Drain Type:")
        print("    [1] Open Hole (Gravity)")
        print("    [2] Centrifugal Pump (Max 0.5 Pa.s, 0% solids)")
        print("    [3] Gear Pump (Max 5.0 Pa.s, 5% solids)")
        print("    [4] Progressive Cavity (Max 50 Pa.s, 15% solids)")
        print("    [5] Custom Pump")
        drain_type = input("  Drain Type [1]: ").strip() or "1"
        
        if drain_type in ["2", "3", "4", "5"]:
            pump_head = ask("  Pump Shutoff Head (m)", 10.0)
            motor_power = ask("  Motor Power Rating (kW)", 0.5)
            
        if drain_type == "2": pump_max_visc, pump_chunk_tol = 0.5, 0.0
        elif drain_type == "3": pump_max_visc, pump_chunk_tol = 5.0, 5.0
        elif drain_type == "4": pump_max_visc, pump_chunk_tol = 50.0, 15.0
        elif drain_type == "5":
            pump_max_visc = ask("  Max Viscosity (Pa.s)", 5.0)
            pump_chunk_tol = ask("  Max Solid Tolerance (%)", 5.0)
            
        drain_max_flow = ask("  Max Flow Rate (m3/h)", 0.0)
    
    print("\n--- Fill Setup ---")
    sim_fill = input("Enable Fill? (y/n) [n]: ").strip().lower() == 'y'
    fill_r = fill_theta = fill_x = fill_y = fill_z = fill_d = 0.0
    fill_flow = fill_T = fill_max_flow = 0.0
    
    if sim_fill:
        if shape == "cylinder":
            fill_r = ask("  Fill Radius from center (m)", 0.0)
            fill_theta = ask("  Fill Angle (degrees)", 0.0)
        else:
            fill_x = ask("  Fill X coordinate (m)", 0.0)
            fill_y = ask("  Fill Y coordinate (m)", 0.0)
        fill_z = ask("  Fill Height from bottom (m)", tank_height - 0.01)
        fill_d = ask("  Nozzle Diameter (m)", 0.05)
        fill_flow = ask("  Flow Rate (m3/h)", 0.5)
        fill_T = ask("  Fluid Temperature (°C)", 20.0)
        
        T_ms = mat_tank.get("T_ms", np.nan)
        if not np.isnan(T_ms) and fill_T < T_ms:
            print(f"  [WARNING] Fluid is solid at {fill_T}°C (Melt point is {T_ms:.1f}°C).")
            print("            The fill pump will choke and no mass will enter!")
            
        fill_max_flow = ask("  Max Flow Rate cap (m3/h)", 0.0)

    V_tank = np.pi * r_inner**2 * tank_height if shape == "cylinder" else L_tank * W_tank * tank_height
    rho_start = np.interp(T_start, mat_tank["T_grid"], mat_tank["rho_grid"])
    M_fluid = ask(f"Tank Fluid Mass (0-{V_tank * rho_start:.0f} kg)", V_tank * rho_start)
    
    print("\n--- Coil Placement & Time Settings ---")
    d_in, d_out = ask("Coil Inner Diameter (m)", 0.0409), ask("Coil Outer Diameter (m)", 0.04826)
    bottom_clearance, top_clearance = ask("Bottom Clearance (m)", 0.05), ask("Top Clearance (m)", 0.05)
    L_avail = tank_height - bottom_clearance - top_clearance
    t_window_hr, t_cooldown_hr = ask("Heating Phase (hrs)", 12.0), ask("Cooling Phase (hrs)", 12.0)
    N_cycles, dt_sec = ask("Number of Cycles", 1, int), ask("Time Step (s)", 1.0)
    
    # NEW: Snapshot interval in minutes
    max_snap_min = (t_window_hr + t_cooldown_hr) * 60.0
    snapshot_interval_min = ask("Snapshot Interval (minutes)", 10.0)
    snapshot_interval_hr = snapshot_interval_min / 60.0

    cfg = config.with_defaults({
        "tank_shape": shape, "r_inner": r_inner, "tank_height": tank_height, "res": res, "tank_length": L_tank, "tank_width": W_tank,
        "d_in": d_in, "d_out": d_out, "t_wall": t_wall, "t_ins": t_ins, "k_ins": k_ins, "h_air": h_air, "M_fluid": M_fluid,
        "T_start": T_start, "T_amb_low": T_amb_low, "T_target": T_target, "T_amb_mid": T_amb_mid, "T_water_in": T_water_in, "flow_m3h": flow_m3h,
        "dt_sec": dt_sec, "t_window_hr": t_window_hr, "t_cooldown_hr": t_cooldown_hr, "N_cycles": N_cycles,
        "snapshot_interval_hr": snapshot_interval_hr, "coil_clearance_bottom": bottom_clearance, "L_avail": L_avail,
        "thresh_liq": thresh_liq, "thresh_visc": thresh_visc,
        
        "grounded": grounded, "t_ins_bottom": t_ins_bottom, "k_ground": k_ground, "L_ground": L_ground,
        
        "simulate_drain": sim_drain, 
        "drain_r": drain_r, "drain_theta": drain_theta, "drain_x": drain_x, "drain_y": drain_y, 
        "drain_z": drain_z, "drain_diameter": drain_d, "drain_max_flow_m3h": drain_max_flow,
        "pump_head_m": pump_head, "motor_power_kw": motor_power,
        "pump_max_visc": pump_max_visc, "pump_chunk_tol_pct": pump_chunk_tol,
        
        "simulate_fill": sim_fill, 
        "fill_r": fill_r, "fill_theta": fill_theta, "fill_x": fill_x, "fill_y": fill_y, 
        "fill_z": fill_z, "fill_diameter": fill_d, "fill_flow_m3h": fill_flow, "fill_T": fill_T, "fill_max_flow_m3h": fill_max_flow,
    })
    
    cfg["T_water_arr"] = mat_coil["T_grid"]
    cfg["rho_water_arr"] = mat_coil["rho_grid"]
    cfg["cp_water_arr"] = mat_coil["cp_sens_grid"]
    cfg["mu_water_arr"] = mat_coil["mu_grid"]
    cfg["k_water_arr"] = mat_coil["k_grid"]
    cfg["T_tube_arr"] = mat_tube["T_grid"]
    cfg["k_tube_arr"] = mat_tube["k_grid"]
    
    # PHASE A
    print("\n--- Phase A Setup ---")
    num_R = ask("How many coil radii to compare? (1-5)", 3, int)
    min_R = ask("Minimum Radius to test (m)", r_inner * 0.3 if shape=="cylinder" else 0.1)
    max_R = ask("Maximum Radius to test (m)", r_inner * 0.9 if shape=="cylinder" else 0.4)
    max_turns = int(L_avail / d_out)
    max_turns = ask(f"Maximum turns to test (1-{max_turns})", max_turns, int)
    
    radii_tested = save_combined_chart(cfg, mat_tank, min_R, max_R, num_R, max_turns, outdir)
    
    print("\n--- Coil Selection ---")
    R_coil = ask("Chosen Coil Radius (m)", radii_tested[-1])
    n_turns = ask("Chosen Coil Turns", max_turns // 2, int)
    
    # NEW: Coil Metrics Calculation
    L_total = 2.0 * np.pi * R_coil * n_turns
    vol_tube = (np.pi / 4.0) * (d_out**2 - d_in**2) * L_total
    rho_tube = float(mat_tube["rho_grid"][0]) # Metal density
    weight_tube = vol_tube * rho_tube
    
    print(f"\n[Coil Metrics]")
    print(f"  Total Tube Length : {L_total:.1f} m")
    print(f"  Total Tube Weight : {weight_tube:.2f} kg")

    return cfg, mat_tank, mat_coil, mat_tube, mat_wall, R_coil, n_turns, slice_angles, weight_tube, L_total