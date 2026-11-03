# physics/phase_3d.py
import numpy as np
from physics import grid as grid_module
from physics import state as state_module
from physics import loop
from physics.operators import coil

def run_simulation(cfg, mat, R_coil, n_turns, outdir):
    print(f"Initializing 3D Grid (res={cfg['res']})...")
    grid = grid_module.Grid.build_3d(cfg)
    state = state_module.State(grid, mat, cfg)
    
    coil_segs = coil.build_coil_segments(grid, cfg, R_coil, n_turns)
    if coil_segs is None:
        raise ValueError("Coil radius is entirely outside the tank!")
        
    drain_idx = np.argmin(grid.zc) if cfg.get("simulate_drain", False) else -1
    fill_idx = np.argmax(grid.zc) if cfg.get("simulate_fill", False) else -1
    
    n_cycles = cfg.get("N_cycles", 1)
    results = {
        "cycle_metrics": [],
        "total_extracted_kg": 0.0,
        "total_filled_kg": 0.0,
        "final_mass": 0.0,
        "first_drain": -1.0,
        "last_drain": -1.0,
        "total_hr": 0.0,
        "snapshots": [],
        "status_log": [],
        "dt_sec": cfg["dt_sec"],
        "cfg_used": cfg
    }
    
    total_hr = 0.0
    
    for c in range(n_cycles):
        print(f"\n--- CYCLE {c+1}/{n_cycles} ---")
        
        # Snapshot accumulators before this cycle starts
        m_out_start = state.m_out_cum
        m_in_start = state.m_in_cum
        E_coil_start = state.E_coil_cum
        
        start_mass = state.total_mass()
        
        # Heating
        print("Starting Heating Phase...")
        snaps, status = loop.run_chunk(
            grid, state, mat, cfg, coil_segs, drain_idx, fill_idx, 
            cfg["t_window_hr"], outdir, total_hr, is_heating=True
        )
        results["snapshots"].extend(snaps)
        results["status_log"].extend(status)
        total_hr += cfg["t_window_hr"]
        
        # Cooling
        if c < n_cycles - 1 or cfg.get("cool_down_at_end", False):
            print("Starting Cooling Phase...")
            snaps, status = loop.run_chunk(
                grid, state, mat, cfg, coil_segs, drain_idx, fill_idx, 
                cfg["t_cooldown_hr"], outdir, total_hr, is_heating=False
            )
            results["snapshots"].extend(snaps)
            results["status_log"].extend(status)
            total_hr += cfg["t_cooldown_hr"]
            
        # Calculate Cycle Metrics
        cycle_m_out = state.m_out_cum - m_out_start
        cycle_m_in = state.m_in_cum - m_in_start
        cycle_E_coil = state.E_coil_cum - E_coil_start
        end_mass = state.total_mass()
        
        eff = (cycle_m_out / start_mass * 100.0) if start_mass > 0 else 0.0
        
        results["cycle_metrics"].append({
            "cycle": c + 1,
            "start_mass": start_mass,
            "remaining_mass": end_mass,
            "extracted_kg": cycle_m_out,
            "filled_kg": cycle_m_in,
            "extracted_temp_avg": state.T_coil_out, # just a placeholder for now
            "efficiency_pct": eff,
            "utilisation_pct": 100.0,
            "fill_util_pct": 100.0,
            "heatmaps": [], # CE team will generate these later
            "massmaps": [],
            "snapshot_times": [float(f.split('_')[-1].replace('.npz','')) for f in snaps]
        })
        
    results["total_hr"] = total_hr
    results["total_extracted_kg"] = state.m_out_cum
    results["total_filled_kg"] = state.m_in_cum
    results["final_mass"] = state.total_mass()
    # TODO: Add logic for first_drain / last_drain tracking later
    
    print("\nSimulation Complete.")
    return results