# physics/loop.py
import numpy as np
from physics.operators import fill, drain, settle, flatten, heat, audit
from physics import timestep

def run_chunk(grid, state, mat, cfg, coil_segs, drain_cell_idx, fill_cell_idx, t_window_hr, outdir, t_start_hr, progress_cb=None, cancel_flag=None, is_heating=True):
    
    t_end = (t_start_hr + t_window_hr) * 3600.0
    t_current = t_start_hr * 3600.0
    
    drain_area = np.pi * (cfg.get("drain_diameter", 0.0) / 2.0)**2
    fill_mdot = cfg.get("fill_flow_m3h", 0.0) * 1000.0 / 3600.0
    fill_T = cfg.get("fill_T", cfg["T_amb_mid"])
    
    snap_interval_sec = cfg.get("snapshot_interval_hr", 0.5) * 3600.0
    next_snap_time = t_current + snap_interval_sec
    
    dt = cfg["dt_sec"] # Starting dt
    snapshots = []
    status_log = []
    step_counter = 0
    
    print(f"Running adaptive loop for {t_window_hr} hours...")
    
    while t_current < t_end:
        if cancel_flag and cancel_flag.is_set():
            print("Simulation cancelled by user.")
            break
            
        if (t_end - t_current) < 1e-3: # Snap to the finish line
            t_current = t_end
            break
            
        # 1. Save state for potential rejection
        T_prev = state.T.copy()
        state_backup = state.copy()
        
        # 2. Take a step
        if cfg.get("simulate_fill", False) and fill_cell_idx >= 0 and fill_mdot > 0:
            fill.apply(grid, state, mat, cfg, dt, fill_cell_idx, fill_mdot, fill_T)
        if cfg.get("simulate_drain", False) and drain_cell_idx >= 0 and drain_area > 0:
            drain.apply(grid, state, mat, cfg, dt, drain_cell_idx, drain_area)
            
        settle.apply(grid, state, mat, cfg)
        flatten.apply(grid, state, mat, cfg)
        heat.apply(grid, state, mat, coil_segs, cfg, dt, is_heating=is_heating)
        
        # 3. Choose next dt
        time_to_event = min(next_snap_time - t_current, t_end - t_current)
        dt_next, accept = timestep.choose(state, T_prev, cfg, dt, time_to_event)
        
        # 4. Rejection logic
        if not accept:
            state.restore(state_backup, mat)
            dt = dt_next
            # Safety catch: If dt shrinks to almost zero, force a break to prevent infinite hang
            if dt < 1e-6:
                print(f"WARNING: dt shrank to {dt:.2e}. Physics is unstable. Breaking to prevent hang.")
                break
            continue # Try again with a smaller dt
            
        # 5. Accept the step
        t_current += dt
        dt = dt_next
        step_counter += 1
        
        current_hr = t_current / 3600.0
        status_log.append(1 if is_heating else -1)
        
        # --- Print progress every 100 steps so we know it's alive ---
        if step_counter % 100 == 0:
            print(f"  Step {step_counter} | Sim Time: {current_hr:.3f} hr | dt: {dt:.3f} s")
        
        # 6. Handle Snapshots (Event limit lands us exactly on the boundary)
        if t_current >= next_snap_time - 1e-3:
            snap_path = state.save_snapshot(outdir, current_hr, cfg["res"])
            snapshots.append(snap_path)
            next_snap_time += snap_interval_sec
            
        # 7. Progress and Audit
        if progress_cb and step_counter % 50 == 0:
            progress_cb({"t_hr": current_hr, "phase": "Heating" if is_heating else "Cooling", "pct": (t_current / t_end) * 100.0})
            
        if step_counter % 500 == 0:
            res = audit.evaluate(state)
            if abs(res["m_resid"]) > 1e-8 or abs(res["H_resid"]) > 1e-8:
                print(f"WARNING: Audit drift! {res}")       

    print("Chunk complete.")
    return snapshots, status_log