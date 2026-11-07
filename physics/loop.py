# physics/loop.py
import numpy as np
import os
import concurrent.futures
from physics.operators import fill, drain, settle, flatten, heat, audit

# 1. THE BACKGROUND THREAD POOL
# We use 2 workers so if one snapshot is writing, a second can start immediately.
# This does not interfere with Numba's CPU threads.
_io_executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)

def save_snapshot_async(T_copy, m_copy, fill_copy, cell_coords, res, outdir, time_hr):
    """
    Saves the snapshot in a background thread so physics doesn't wait.
    We pass COPIES of the arrays, so the main loop can immediately update the real arrays.
    """
    def worker():
        snap_dir = os.path.join(outdir, "snapshots")
        os.makedirs(snap_dir, exist_ok=True)
        
        T_3d = np.full((res, res, res), np.nan, dtype=np.float32)
        m_3d = np.full((res, res, res), np.nan, dtype=np.float32)
        fill_3d = np.full((res, res, res), np.nan, dtype=np.float32)
        
        # Only save cells with mass (fixes the invisible air blocks in the viewer)
        for c in range(len(m_copy)):
            if m_copy[c] > 1e-6:
                i, j, k = cell_coords[c]
                T_3d[i, j, k] = T_copy[c]
                m_3d[i, j, k] = m_copy[c]
                fill_3d[i, j, k] = fill_copy[c]
                
        filename = os.path.join(snap_dir, f"snap_{time_hr:06.2f}.npz")
        np.savez_compressed(filename, T=T_3d, m=m_3d, fill=fill_3d, t_hr=time_hr, res=res)
        return filename

    # Submit the task to the background thread
    future = _io_executor.submit(worker)
    return future

def run_chunk(grid, state, mat, cfg, coil_segs, drain_cell_idx, fill_cell_idx, t_window_hr, outdir, t_start_hr, progress_cb=None, cancel_flag=None, is_heating=True):
    dt = cfg["dt_sec"]
    n_steps = int(t_window_hr * 3600.0 / dt)
    
    drain_area = np.pi * (cfg.get("drain_diameter", 0.0) / 2.0)**2
    fill_mdot = cfg.get("fill_flow_m3h", 0.0) * 1000.0 / 3600.0
    fill_T = cfg.get("fill_T", cfg["T_amb_mid"])
    
    snap_interval_sec = cfg.get("snapshot_interval_hr", 0.5) * 3600.0
    next_snap_time = (t_start_hr * 3600.0) + snap_interval_sec
    t_end = (t_start_hr + t_window_hr) * 3600.0
    
    snapshots = [] # Stores the 'Future' objects, not the paths yet
    status_log = []
    
    for step in range(n_steps):
        t_current = (t_start_hr * 3600.0) + (step * dt)
        
        if cancel_flag and cancel_flag.is_set():
            break
            
        # --- SMART SKIPPING LOGIC ---
        mass_moved = False
        
        # 1. Mass moving
        if cfg.get("simulate_fill", False) and fill_cell_idx >= 0 and fill_mdot > 0:
            m_before = state.m_in_cum
            fill.apply(grid, state, mat, cfg, dt, fill_cell_idx, fill_mdot, fill_T)
            if state.m_in_cum > m_before: mass_moved = True
            
        if cfg.get("simulate_drain", False) and drain_cell_idx >= 0 and drain_area > 0:
            m_before = state.m_out_cum
            drain.apply(grid, state, mat, cfg, dt, drain_cell_idx, drain_area)
            if state.m_out_cum > m_before: mass_moved = True
                
        # 2. Pack and Level
        settle.apply(grid, state, mat, cfg)
        
        # SKIP FLATTEN: If no mass was added/drained, and it's not a "check every 10 steps"
        # we skip the lateral leveling to save CPU.
        if mass_moved or step % 10 == 0:
            flatten.apply(grid, state, mat, cfg)
        
        # 3. Heat
        heat.apply(grid, state, mat, coil_segs, cfg, dt, is_heating=is_heating)
        
        # 4. Snapshots (ASYNC I/O)
        if t_current >= next_snap_time - 1e-3:
            # Take a fast snapshot (copies) and hand it to the background thread
            res = int(np.max(grid.cell_coords)) + 1
            future = save_snapshot_async(
                state.T.copy(), 
                state.m.copy(), 
                state.fill.copy(), 
                grid.cell_coords, 
                res, 
                outdir, 
                t_current / 3600.0
            )
            snapshots.append(future) 
            next_snap_time += snap_interval_sec
            
        # 5. Progress
        if step % 5 == 0:
            print(f"  Step {step}/{n_steps}...")
            
        if progress_cb and step % 50 == 0:
            progress_cb({"t_hr": t_current/3600.0, "pct": (step/n_steps)*100.0})
            
        status_log.append(1 if is_heating else -1)

    # --- THE UNITY BARRIER ---
    # Wait for all background hard drive saves to finish before closing the chunk
    if snapshots:
        print("  Waiting for background snapshots to finish writing...")
        snapshot_paths = [f.result() for f in snapshots]
    else:
        snapshot_paths = []

    print("Chunk complete.")
    return snapshot_paths, status_log