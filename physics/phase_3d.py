# physics/phase_3d.py
import numpy as np
import json
import os
from physics import grid as grid_module
from physics import state as state_module
from physics import loop
from physics.operators import coil

def find_closest_cell(grid, shape, p1, p2, z):
    if shape == "cylinder":
        xc = p1 * np.cos(np.deg2rad(p2)) if p1 > 0 else 0.0
        yc = p1 * np.sin(np.deg2rad(p2)) if p1 > 0 else 0.0
    else:
        xc = p1
        yc = p2
        
    dist_sq = (grid.xc - xc)**2 + (grid.yc - yc)**2 + (grid.zc - z)**2
    return int(np.argmin(dist_sq))

def run_simulation(cfg, mat, R_coil, n_turns, outdir, progress_cb=None, cancel_flag=None):
    print(f"Initializing 3D Grid (res={cfg['res']})...")
    grid = grid_module.Grid.build_3d(cfg)
    state = state_module.State(grid, mat, cfg)
    
    coil_segs = coil.build_coil_segments(grid, cfg, R_coil, n_turns)
    if coil_segs is None:
        raise ValueError("Coil radius is entirely outside the tank!")
        
    # --- DRAIN MAPPING ---
    drain_idx = -1
    if cfg.get("simulate_drain", False):
        shape = cfg.get("tank_shape", "cylinder")
        if shape == "cylinder":
            drain_idx = find_closest_cell(grid, shape, cfg["drain_r"], cfg["drain_theta"], cfg["drain_z"])
        else:
            drain_idx = find_closest_cell(grid, shape, cfg["drain_x"], cfg["drain_y"], cfg["drain_z"])
        print(f"  Drain mapped to cell {drain_idx}")
        
    # --- FILL MAPPING ---
    fill_idx = -1
    if cfg.get("simulate_fill", False):
        shape = cfg.get("tank_shape", "cylinder")
        if shape == "cylinder":
            fill_idx = find_closest_cell(grid, shape, cfg["fill_r"], cfg["fill_theta"], cfg["fill_z"])
        else:
            fill_idx = find_closest_cell(grid, shape, cfg["fill_x"], cfg["fill_y"], cfg["fill_z"])
        print(f"  Fill mapped to cell {fill_idx}")
        
    # --- SAVE RUN INFO FOR VIEWER ---
    run_info = {
        "drain_coords": grid.cell_coords[drain_idx].tolist() if drain_idx >= 0 else None,
        "fill_coords": grid.cell_coords[fill_idx].tolist() if fill_idx >= 0 else None,
        "res": cfg["res"]
    }
    with open(os.path.join(outdir, "run_info.json"), "w") as f:
        json.dump(run_info, f)
    # --------------------------------
    
    n_cycles = cfg.get("N_cycles", 1)
    results = {
        "cycle_metrics": [], "total_extracted_kg": 0.0, "total_filled_kg": 0.0,
        "final_mass": 0.0, "first_drain": -1.0, "last_drain": -1.0, "total_hr": 0.0,
        "snapshots": [], "status_log": [], "dt_sec": cfg["dt_sec"], "cfg_used": cfg, "cancelled": False
    }
    
    total_hr = 0.0
    for c in range(n_cycles):
        print(f"\n--- CYCLE {c+1}/{n_cycles} ---")
        
        # --- HEATING PHASE ---
        m_out_start = state.m_out_cum
        m_in_start = state.m_in_cum
        E_coil_start = state.E_coil_cum
        E_loss_start = state.E_loss_cum
        start_mass = state.total_mass()
        
        valid_cells = state.m > 1e-6
        start_temp = np.mean(state.T[valid_cells]) if np.any(valid_cells) else 0.0
        
        print("Starting Heating Phase...")
        snaps, status = loop.run_chunk(
            grid, state, mat, cfg, coil_segs, drain_idx, fill_idx, 
            cfg["t_window_hr"], outdir, total_hr, 
            progress_cb=progress_cb, cancel_flag=cancel_flag, is_heating=True
        )
        results["snapshots"].extend(snaps)
        results["status_log"].extend(status)
        total_hr += cfg["t_window_hr"]
        
        if cancel_flag and cancel_flag.is_set():
            results["cancelled"] = True
            break
            
        # --- COOLING PHASE ---
        print("Starting Cooling Phase...")
        snaps, status = loop.run_chunk(
            grid, state, mat, cfg, coil_segs, drain_idx, fill_idx, 
            cfg["t_cooldown_hr"], outdir, total_hr, 
            progress_cb=progress_cb, cancel_flag=cancel_flag, is_heating=False
        )
        results["snapshots"].extend(snaps)
        results["status_log"].extend(status)
        total_hr += cfg["t_cooldown_hr"]
        
        if cancel_flag and cancel_flag.is_set():
            results["cancelled"] = True
            break
            
        # --- CALCULATE CYCLE METRICS ---
        cycle_m_out = state.m_out_cum - m_out_start
        cycle_m_in = state.m_in_cum - m_in_start
        cycle_E_coil = state.E_coil_cum - E_coil_start
        cycle_E_loss = state.E_loss_cum - E_loss_start
        end_mass = state.total_mass()
        
        valid_cells = state.m > 1e-6
        end_temp = np.mean(state.T[valid_cells]) if np.any(valid_cells) else 0.0
        
        eff = (cycle_m_out / start_mass * 100.0) if start_mass > 0 else 0.0
        
        results["cycle_metrics"].append({
            "cycle": c + 1, 
            "start_mass": start_mass, 
            "remaining_mass": end_mass,
            "start_temp": start_temp,
            "end_temp": end_temp,
            "extracted_kg": cycle_m_out, 
            "filled_kg": cycle_m_in, 
            "extracted_temp_avg": state.T_coil_out,
            "efficiency_pct": eff,
            "E_coil_kwh": cycle_E_coil / 3.6e6,
            "E_loss_kwh": cycle_E_loss / 3.6e6,
            "utilisation_pct": 100.0, "fill_util_pct": 100.0,
            "heatmaps": [], "massmaps": [],
            "snapshot_times": [float(f.split('_')[-1].replace('.npz','')) for f in snaps]
        })
        
    results["total_hr"] = total_hr
    results["total_extracted_kg"] = state.m_out_cum
    results["total_filled_kg"] = state.m_in_cum
    results["final_mass"] = state.total_mass()
    print("\nSimulation Complete.")
    return results