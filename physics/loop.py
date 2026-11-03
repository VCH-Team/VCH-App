# physics/loop.py
import numpy as np
from physics.operators import fill, drain, settle, flatten, heat, audit

def run_chunk(grid, state, mat, cfg, coil_segs, drain_cell_idx, fill_cell_idx, t_window_hr, outdir, t_start_hr, progress_cb=None, cancel_flag=None, is_heating=True):
    dt_sec = cfg["dt_sec"]
    n_steps = int(t_window_hr * 3600.0 / dt_sec)
    
    drain_area = np.pi * (cfg.get("drain_diameter", 0.0) / 2.0)**2
    fill_mdot = cfg.get("fill_flow_m3h", 0.0) * 1000.0 / 3600.0
    fill_T = cfg.get("fill_T", cfg["T_amb_mid"])
    
    snap_interval_steps = int(cfg["snapshot_interval_hr"] * 3600.0 / dt_sec)
    
    snapshots = []
    status_log = []
    
    for step in range(n_steps):
        if cancel_flag and cancel_flag.is_set():
            print("Simulation cancelled by user.")
            break
            
        # 1. Mass moving
        if cfg.get("simulate_fill", False) and fill_cell_idx >= 0 and fill_mdot > 0:
            fill.apply(grid, state, mat, cfg, dt_sec, fill_cell_idx, fill_mdot, fill_T)
        if cfg.get("simulate_drain", False) and drain_cell_idx >= 0 and drain_area > 0:
            drain.apply(grid, state, mat, cfg, dt_sec, drain_cell_idx, drain_area)
            
        # 2. Repack and level
        settle.apply(grid, state, mat, cfg)
        flatten.apply(grid, state, mat, cfg)
        
        # 3. Heat
        heat.apply(grid, state, mat, coil_segs, cfg, dt_sec, is_heating=is_heating)
        
        # 4. Logging & Snapshots
        current_hr = t_start_hr + (step * dt_sec / 3600.0)
        status_log.append(1 if is_heating else -1)
        
        if step % snap_interval_steps == 0 or step == n_steps - 1:
            snap_path = state.save_snapshot(outdir, current_hr, cfg["res"])
            snapshots.append(snap_path)
            
        if progress_cb and step % 100 == 0:
            progress_cb({"t_hr": current_hr, "phase": "Heating" if is_heating else "Cooling", "pct": (step / n_steps) * 100.0})
            
        if step % 500 == 0:
            res = audit.evaluate(state)
            if abs(res["m_resid"]) > 1e-8 or abs(res["H_resid"]) > 1e-8:
                print(f"WARNING: Audit drift at step {step}! {res}")

    return snapshots, status_log