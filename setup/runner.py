# setup/runner.py
import os
import time
import sys
import json
import numpy as np
import threading

from setup import payload, file_writer
from setup.grid_builder import Grid, build_coil_segments
from kernel.numba_kernel_cycle import mega_kernel_cycle
from engine.state import initial_fill_kernel, derive_properties_kernel
from engine.operators.settle import settle_kernel
from viz import viewer, report, dashboard

def find_closest_cell(grid, shape, r, theta, x, y, z):
    if shape == "cylinder":
        xc = r * np.cos(np.deg2rad(theta))
        yc = r * np.sin(np.deg2rad(theta))
    else:
        xc = x
        yc = y
    return int(np.argmin((grid.xc - xc)**2 + (grid.yc - yc)**2 + (grid.zc - z)**2))

def run_simulation(cfg, mat_tank, mat_coil, mat_tube, mat_wall, R_coil, n_turns, slice_angles, weight_tube, L_total, outdir):
    print("\n--- INITIALIZING SIMULATION ENGINE ---")
    
    # 1. Build Grid & Coil
    print(f"Building 3D Grid (res={cfg['res']})...")
    grid = Grid.build_3d(cfg)
    coil_segs = build_coil_segments(grid, cfg, R_coil, n_turns)
    
    # 2. Map Drain & Fill Locations
    drain_idx = -1
    drain_col_idx = -1
    fill_idx = -1
    
    if cfg["simulate_drain"]:
        drain_idx = find_closest_cell(grid, cfg["tank_shape"], cfg["drain_r"], cfg["drain_theta"], cfg["drain_x"], cfg["drain_y"], cfg["drain_z"])
        for i in range(len(grid.col_start)):
            start = grid.col_start[i]
            length = grid.col_len[i]
            if drain_idx in grid.col_cells[start:start+length]:
                drain_col_idx = i
                break
                
    if cfg["simulate_fill"]:
        fill_idx = find_closest_cell(grid, cfg["tank_shape"], cfg["fill_r"], cfg["fill_theta"], cfg["fill_x"], cfg["fill_y"], cfg["fill_z"])
        
    # 3. Build Payload
    ncfg, ngrid, nm = payload.build_payload(
        cfg, mat_tank, mat_coil, mat_tube, mat_wall, 
        grid, coil_segs, drain_idx, fill_idx, drain_col_idx
    )
    
    # 4. Initial State & Pre-Compaction
    N_cells = grid.N
    m = np.zeros(N_cells)
    H = np.zeros(N_cells)
    
    rho_start = np.interp(cfg["T_start"], mat_tank["T_grid"], mat_tank["rho_grid"])
    M_initial = cfg.get("M_fluid", rho_start * grid.V.sum())
    h_start = np.interp(ncfg.T_start, nm.T_grid, nm.H_grid)
    f = min(1.0, (M_initial / rho_start) / grid.V.sum())
    
    initial_fill_kernel(m, H, ngrid.V, ngrid.col_cells, ngrid.col_start, ngrid.col_len, f, rho_start, h_start)
    
    dummy_T = np.zeros(N_cells); dummy_rho = np.zeros(N_cells); dummy_k = np.zeros(N_cells)
    dummy_mu = np.zeros(N_cells); dummy_fs = np.zeros(N_cells); dummy_cp = np.zeros(N_cells)
    dummy_cap = np.zeros(N_cells); dummy_ff = np.zeros(N_cells)
    
    derive_properties_kernel(m, H, ngrid.V, h_start, nm, dummy_T, dummy_rho, dummy_k, dummy_mu, dummy_fs, dummy_cp, dummy_cap, dummy_ff)
    settle_kernel(m, H, ngrid.V, dummy_rho, dummy_fs, ngrid.col_cells, ngrid.col_start, ngrid.col_len, ncfg.fs_lock, 100.0, ncfg.dz)
    
    # 5. Save run_info.json
    dx = (2 * cfg["r_inner"]) / cfg["res"] if cfg["tank_shape"] == "cylinder" else cfg["tank_length"] / cfg["res"]
    dz = cfg["tank_height"] / cfg["res"]
    
    run_info = {
        "drain_coords": grid.cell_coords[drain_idx].tolist() if drain_idx >= 0 else None,
        "fill_coords": grid.cell_coords[fill_idx].tolist() if fill_idx >= 0 else None,
        "res": cfg["res"], "shape": cfg["tank_shape"], "r_inner": cfg["r_inner"], 
        "tank_length": cfg["tank_length"], "tank_width": cfg["tank_width"],
        "tank_height": cfg["tank_height"], "t_wall": cfg["t_wall"], "t_ins": cfg["t_ins"], 
        "max_tank_mass": ncfg.max_tank_mass,
        "slice_angles": slice_angles,
        "dx": dx, "dz": dz,
        "coil_weight_kg": weight_tube, "coil_length_m": L_total
    }
    with open(os.path.join(outdir, "run_info.json"), "w") as f_out:
        json.dump(run_info, f_out)

    # 6. Cycle Loop
    all_cycle_metrics = []
    cancelled_early = False

    for cycle in range(cfg["N_cycles"]):
        print(f"\n--- RUNNING CYCLE {cycle + 1} / {cfg['N_cycles']} ---")
        
        cycle_dir = os.path.join(outdir, f"cycle_{cycle + 1}")
        os.makedirs(cycle_dir, exist_ok=True)
        
        with open(os.path.join(cycle_dir, "run_info.json"), "w") as f_out:
            json.dump(run_info, f_out)
            
        total_hr_cycle = cfg["t_window_hr"] + cfg["t_cooldown_hr"]
        max_snaps = int(np.ceil(total_hr_cycle / cfg["snapshot_interval_hr"])) + 2
        
        dtype = np.float32
        snapshots_T = np.zeros((max_snaps, N_cells), dtype=dtype)
        snapshots_m = np.zeros((max_snaps, N_cells), dtype=dtype)
        snapshots_fill = np.zeros((max_snaps, N_cells), dtype=dtype)
        
        cycle_summary_row = np.zeros(12, dtype=np.float64)
        progress_tracker = np.zeros(2, dtype=np.float64)
        cancel_flag = np.zeros(1, dtype=np.int32)
        
        def monitor_progress():
            while progress_tracker[0] < 99.99:
                pct = progress_tracker[0]
                snaps = int(progress_tracker[1])
                sys.stdout.write(f"\r  Cycle {cycle+1} Progress: {pct:5.1f}% | Snapshots: {snaps}/{max_snaps} (Ctrl+C to abort)")
                sys.stdout.flush()
                if pct >= 100.0: break
                time.sleep(0.5)
            sys.stdout.write(f"\r  Cycle {cycle+1} Complete!                              \n")
            sys.stdout.flush()

        print("  Starting simulation...")
        t0 = time.time()
        
        monitor_thread = threading.Thread(target=monitor_progress, daemon=True)
        monitor_thread.start()
        
        try:
            actual_snaps, m_in, m_out = mega_kernel_cycle(
                ncfg, ngrid, nm, m, H,
                snapshots_T, snapshots_m, snapshots_fill, max_snaps,
                cycle_summary_row, progress_tracker, cancel_flag
            )
        except KeyboardInterrupt:
            print("\n\n  [Stop Requested] Saving state and aborting cycle...")
            cancel_flag[0] = 1
            actual_snaps, m_in, m_out = mega_kernel_cycle(
                ncfg, ngrid, nm, m, H,
                snapshots_T, snapshots_m, snapshots_fill, max_snaps,
                cycle_summary_row, progress_tracker, cancel_flag
            )
            cancelled_early = True
            
        finally:
            progress_tracker[0] = 100.0
            monitor_thread.join()
            
        print(f"  Cycle finished in {time.time() - t0:.1f} seconds.")
        
        # Save Data
        file_writer.save_snapshots_3d(cycle_dir, snapshots_T[:actual_snaps], snapshots_m[:actual_snaps], snapshots_fill[:actual_snaps], 
                                      actual_snaps, grid, cfg["res"], cfg["dt_sec"], cfg["snapshot_interval_hr"])
        
        file_writer.save_results_json(cycle_dir, np.array([cycle_summary_row]), 1, ncfg, np.sum(m), m_out, m_in)
        
        all_cycle_metrics.append(cycle_summary_row)
        
        # Generate Outputs
        print(f"  Generating outputs for Cycle {cycle+1}...")
        if actual_snaps > 0:
            viewer.create_interactive_viewer(cycle_dir)
        report.generate_report(cycle_dir)
        dashboard.create_dashboard(cycle_dir, f"Cycle {cycle + 1} of {cfg['N_cycles']}")
        
        if cancelled_early:
            print("Simulation aborted early by user.")
            break

    # 7. Final Summary
    if not cancelled_early and len(all_cycle_metrics) > 0:
        print(f"\n--- GENERATING FINAL SUMMARY ---")
        final_dir = os.path.join(outdir, "final_summary")
        os.makedirs(final_dir, exist_ok=True)
        
        all_cycle_metrics_np = np.array(all_cycle_metrics)
        total_m_out = np.sum(all_cycle_metrics_np[:, 10])
        total_m_in = np.sum(all_cycle_metrics_np[:, 11])
        
        file_writer.save_results_json(final_dir, all_cycle_metrics_np, len(all_cycle_metrics), ncfg, np.sum(m), total_m_out, total_m_in)
        
        # Copy run_info to final summary too
        with open(os.path.join(final_dir, "run_info.json"), "w") as f_out:
            json.dump(run_info, f_out)
            
        report.generate_report(final_dir)
        dashboard.create_dashboard(final_dir, "Final Multi-Cycle Summary")

    print(f"\nRun complete! Check the folders in: {outdir}")