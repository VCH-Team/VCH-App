# physics/loop.py
import numpy as np
import os
import sys
import concurrent.futures
from physics.operators import fill, drain, settle, flatten, heat, audit

_io_executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)

def save_snapshot_async(T_copy, m_copy, fill_copy, cell_coords, res, outdir, time_hr):
    def worker():
        snap_dir = os.path.join(outdir, "snapshots")
        os.makedirs(snap_dir, exist_ok=True)
        
        T_3d = np.full((res, res, res), np.nan, dtype=np.float32)
        m_3d = np.full((res, res, res), np.nan, dtype=np.float32)
        fill_3d = np.full((res, res, res), np.nan, dtype=np.float32)
        
        for c in range(len(m_copy)):
            if m_copy[c] > 1e-6:
                i, j, k = cell_coords[c]
                T_3d[i, j, k] = T_copy[c]
                m_3d[i, j, k] = m_copy[c]
                fill_3d[i, j, k] = fill_copy[c]
                
        filename = os.path.join(snap_dir, f"snap_{time_hr:06.2f}.npz")
        np.savez_compressed(filename, T=T_3d, m=m_3d, fill=fill_3d, t_hr=time_hr, res=res)
        return filename
    return _io_executor.submit(worker)

def run_chunk(grid, state, mat, cfg, coil_segs, drain_cell_idx, fill_cell_idx, t_window_hr, outdir, t_start_hr, progress_cb=None, cancel_flag=None, is_heating=True):
    dt = cfg["dt_sec"]
    n_steps = int(t_window_hr * 3600.0 / dt)
    
    drain_area = np.pi * (cfg.get("drain_diameter", 0.0) / 2.0)**2
    fill_mdot = cfg.get("fill_flow_m3h", 0.0) * 1000.0 / 3600.0
    fill_T = cfg.get("fill_T", cfg["T_amb_mid"])
    
    snap_interval_sec = cfg.get("snapshot_interval_hr", 0.5) * 3600.0
    next_snap_time = (t_start_hr * 3600.0) + snap_interval_sec
    t_end = (t_start_hr + t_window_hr) * 3600.0
    
    snapshots = []
    status_log = []
    
    for step in range(n_steps):
        t_current = (t_start_hr * 3600.0) + (step * dt)
        
        if cancel_flag and cancel_flag.is_set():
            print("\nSimulation cancelled.")
            break
            
        mass_moved = False
        
        if cfg.get("simulate_fill", False) and fill_cell_idx >= 0 and fill_mdot > 0:
            m_before = state.m_in_cum
            fill.apply(grid, state, mat, cfg, dt, fill_cell_idx, fill_mdot, fill_T)
            if state.m_in_cum > m_before: mass_moved = True
            
        if cfg.get("simulate_drain", False) and drain_cell_idx >= 0 and drain_area > 0:
            m_before = state.m_out_cum
            drain.apply(grid, state, mat, cfg, dt, drain_cell_idx, drain_area)
            if state.m_out_cum > m_before: mass_moved = True
                
        settle.apply(grid, state, mat, cfg)
        
        if mass_moved or step % 10 == 0:
            flatten.apply(grid, state, mat, cfg)
        
        heat.apply(grid, state, mat, coil_segs, cfg, dt, is_heating=is_heating)
        
        if t_current >= next_snap_time - 1e-3:
            res = int(np.max(grid.cell_coords)) + 1
            future = save_snapshot_async(
                state.T.copy(), state.m.copy(), state.fill.copy(), 
                grid.cell_coords, res, outdir, t_current / 3600.0
            )
            snapshots.append(future) 
            next_snap_time += snap_interval_sec
            
        # --- SINGLE LINE PROGRESS BAR ---
        if step % 10 == 0 or step == n_steps - 1:
            pct = (step + 1) / n_steps * 100
            sys.stdout.write(f"\r  Progress: {pct:5.1f}% | Step {step+1}/{n_steps} ")
            sys.stdout.flush()
            
        if progress_cb and step % 50 == 0:
            progress_cb({"t_hr": t_current/3600.0, "pct": (step/n_steps)*100.0})
            
        status_log.append(1 if is_heating else -1)

    sys.stdout.write("\n") # Move to a new line after the progress bar finishes

    if snapshots:
        print("  Waiting for background snapshots to finish writing...")
        snapshot_paths = [f.result() for f in snapshots]
    else:
        snapshot_paths = []

    print("Chunk complete.")
    return snapshot_paths, status_log