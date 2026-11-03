# physics/phase_3d.py
import numpy as np
import os
from physics import grid as grid_module
from physics import state as state_module
from physics import loop
from physics.operators import coil

def run_simulation(cfg, mat, R_coil, n_turns, outdir, progress_cb=None, cancel_flag=None):
    print(f"Initializing 3D Grid (res={cfg['res']})...")
    grid = grid_module.Grid.build_3d(cfg)
    state = state_module.State(grid, mat, cfg)
    
    coil_segs = coil.build_coil_segments(grid, cfg, R_coil, n_turns)
    if coil_segs is None:
        raise ValueError("Coil radius is entirely outside the tank!")
        
    drain_idx = np.argmin(grid.zc) if cfg.get("simulate_drain", False) else -1
    fill_idx = np.argmax(grid.zc) if cfg.get("simulate_fill", False) else -1
    
    n_cycles = cfg.get("N_cycles", 1)
    total_hr = 0.0
    all_snapshots = []
    all_status = []
    cycle_metrics = []
    
    for c in range(n_cycles):
        print(f"\n--- CYCLE {c+1}/{n_cycles} ---")
        
        # Heating
        t_window = cfg["t_window_hr"]
        start_m = state.total_mass()
        snaps, status = loop.run_chunk(grid, state, mat, cfg, coil_segs, drain_idx, fill_idx, t_window, outdir, total_hr, progress_cb, cancel_flag, is_heating=True)
        
        all_snapshots.extend(snaps)
        all_status.extend(status)
        total_hr += t_window
        
        ext_kg = state.m_out_cum
        fill_kg = state.m_in_cum
        cycle_metrics.append({
            "cycle": c + 1,
            "start_mass": start_m,
            "remaining_mass": state.total_mass(),
            "extracted_kg": ext_kg,
            "filled_kg": fill_kg,
            "efficiency_pct": (ext_kg / start_m * 100.0) if start_m > 0 else 0.0,
        })
        
        if cancel_flag and cancel_flag.is_set(): break
        
        # Cooling
        if c < n_cycles - 1 or cfg.get("cool_down_at_end", False):
            t_cool = cfg["t_cooldown_hr"]
            snaps, status = loop.run_chunk(grid, state, mat, cfg, coil_segs, drain_idx, fill_idx, t_cool, outdir, total_hr, progress_cb, cancel_flag, is_heating=False)
            all_snapshots.extend(snaps)
            all_status.extend(status)
            total_hr += t_cool
            
        if cancel_flag and cancel_flag.is_set(): break
            
    print("\nSimulation Complete.")
    
    return {
        "cycle_metrics": cycle_metrics,
        "total_extracted_kg": state.m_out_cum,
        "total_filled_kg": state.m_in_cum,
        "final_mass": state.total_mass(),
        "first_drain": 0.0, # Simplified for now
        "last_drain": total_hr, 
        "total_hr": total_hr,
        "snapshots": all_snapshots,
        "status_log": all_status,
        "dt_sec": cfg["dt_sec"],
        "cfg_used": cfg
    }