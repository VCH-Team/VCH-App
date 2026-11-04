# physics/loop.py
import numpy as np
from physics.operators import fill, drain, settle, flatten, heat, audit

def run_chunk(grid, state, mat, cfg, coil_segs, drain_cell_idx, fill_cell_idx, t_window_hr, outdir, t_start_hr, progress_cb=None, cancel_flag=None, is_heating=True):
    
    dt = cfg["dt_sec"]
    n_steps = int(t_window_hr * 3600.0 / dt)
    
    drain_area = np.pi * (cfg.get("drain_diameter", 0.0) / 2.0)**2
    fill_mdot = cfg.get("fill_flow_m3h", 0.0) * 1000.0 / 3600.0
    fill_T = cfg.get("fill_T", cfg["T_amb_mid"])
    
    snap_interval_sec = cfg.get("snapshot_interval_hr", 0.5) * 3600.0
    next_snap_time = (t_start_hr * 3600.0) + snap_interval_sec
    
    print(f"Running {n_steps} fixed steps ({t_window_hr} hours)...")
    
    snapshots = []
    status_log = []
    
    for step in range(n_steps):
        t_current = (t_start_hr * 3600.0) + (step * dt)
        
        if cancel_flag and cancel_flag.is_set():
            break
            
        # 1. Mass moving
        if cfg.get("simulate_fill", False) and fill_cell_idx >= 0 and fill_mdot > 0:
            fill.apply(grid, state, mat, cfg, dt, fill_cell_idx, fill_mdot, fill_T)
        if cfg.get("simulate_drain", False) and drain_cell_idx >= 0 and drain_area > 0:
            drain.apply(grid, state, mat, cfg, dt, drain_cell_idx, drain_area)
            
        # 2. Pack and Level
        settle.apply(grid, state, mat, cfg)
        flatten.apply(grid, state, mat, cfg)
        
        # 3. Heat
        heat.apply(grid, state, mat, coil_segs, cfg, dt, is_heating=is_heating)
        
        # 4. Snapshots
        if t_current >= next_snap_time - 1e-3:
            snap_path = state.save_snapshot(grid, outdir, t_current / 3600.0)
            snapshots.append(snap_path)
            next_snap_time += snap_interval_sec
            
        # 5. Progress
        if step % 5 == 0:
            print(f"  Step {step}/{n_steps}...")
            
        if progress_cb and step % 50 == 0:
            progress_cb({"t_hr": t_current/3600.0, "pct": (step/n_steps)*100.0})
            
        status_log.append(1 if is_heating else -1)

    print("Chunk complete.")
    return snapshots, status_log