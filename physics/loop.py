# physics/loop.py
import numpy as np
from physics.operators import fill, drain, settle, flatten, heat, audit

def run_chunk(grid, state, mat, cfg, coil_w, drain_cell_idx, fill_cell_idx, R_coil, n_turns, t_window_hr, is_heating=True):
    """
    Runs the simulation for one chunk of time (either a heating or cooling phase).
    """
    dt_sec = cfg["dt_sec"]
    n_steps = int(t_window_hr * 3600.0 / dt_sec)
    
    drain_area = np.pi * (cfg.get("drain_diameter", 0.0) / 2.0)**2
    fill_mdot = cfg.get("fill_flow_m3h", 0.0) * 1000.0 / 3600.0
    fill_T = cfg.get("fill_T", cfg["T_amb_mid"])
    
    print(f"Running {n_steps} steps ({t_window_hr} hours)...")
    
    for step in range(n_steps):
        # 1. Mass moving
        if cfg.get("simulate_fill", False) and fill_cell_idx >= 0 and fill_mdot > 0:
            fill.apply(grid, state, mat, cfg, dt_sec, fill_cell_idx, fill_mdot, fill_T)
            
        if cfg.get("simulate_drain", False) and drain_cell_idx >= 0 and drain_area > 0:
            drain.apply(grid, state, mat, cfg, dt_sec, drain_cell_idx, drain_area)
            
        # 2. Repack and level
        settle.apply(grid, state, mat, cfg)
        flatten.apply(grid, state, mat, cfg)
        
        # 3. Heat
        heat.apply(grid, state, mat, coil_w, cfg, dt_sec, R_coil, n_turns, is_heating=is_heating)
        
        # 4. Audit periodically
        if step % 100 == 0:
            res = audit.evaluate(state)
            if abs(res["m_resid"]) > 1e-8 or abs(res["H_resid"]) > 1e-8:
                print(f"WARNING: Audit drift at step {step}! {res}")
                
    print("Chunk complete.")