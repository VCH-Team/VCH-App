# setup/file_writer.py
import os
import json
import numpy as np

def save_snapshots_3d(outdir, snapshots_T, snapshots_m, snapshots_fill, actual_snaps, grid, res, dt_sec, snapshot_interval_hr):
    snap_dir = os.path.join(outdir, "snapshots")
    os.makedirs(snap_dir, exist_ok=True)
    snapshot_paths = []
    
    print(f"  Writing {actual_snaps} snapshots to disk...")
    for i in range(actual_snaps):
        T_3d = np.full((res, res, res), np.nan, dtype=np.float32)
        m_3d = np.full((res, res, res), np.nan, dtype=np.float32)
        fill_3d = np.full((res, res, res), np.nan, dtype=np.float32)
        
        for c in range(grid.N):
            idx = grid.cell_coords[c]
            T_3d[idx[0], idx[1], idx[2]] = snapshots_T[i, c]
            m_3d[idx[0], idx[1], idx[2]] = snapshots_m[i, c]
            fill_3d[idx[0], idx[1], idx[2]] = snapshots_fill[i, c]
            
        t_hr = i * snapshot_interval_hr
        filename = os.path.join(snap_dir, f"snap_{t_hr:06.2f}.npz")
        np.savez_compressed(filename, T=T_3d, m=m_3d, fill=fill_3d, t_hr=t_hr, res=res)
        snapshot_paths.append(filename)
    return snapshot_paths

def save_results_json(outdir, cycle_summaries, actual_cycles, ncfg, final_mass, total_m_out, total_m_in):
    cycle_metrics = []
    
    for c in range(actual_cycles):
        # Unpack all 12 metrics from the kernel
        cycle_metrics.append({
            "cycle": c + 1,
            "start_temp": float(cycle_summaries[c, 6]),
            "end_temp": float(cycle_summaries[c, 7]),
            "drained_kg": float(cycle_summaries[c, 10]),   # <--- NOW WRITTEN
            "filled_kg": float(cycle_summaries[c, 11]),    # <--- NOW WRITTEN
            "efficiency_pct": float(cycle_summaries[c, 5]),
            "E_coil_kwh": float(cycle_summaries[c, 8]),
            "E_loss_kwh": float(cycle_summaries[c, 9]),
            "phase_distribution": {
                "solid_pct": float(cycle_summaries[c, 0]),
                "slurry_pct": float(cycle_summaries[c, 1]),
                "liquid_pct": float(cycle_summaries[c, 2])
            },
            "avg_temp": float(cycle_summaries[c, 3]),
            "drain_temp": float(cycle_summaries[c, 4])
        })

    clean_results = {
        "total_extracted_kg": float(total_m_out),
        "total_filled_kg": float(total_m_in),
        "final_mass": float(final_mass),
        "total_hr": float((ncfg.t_window_hr + ncfg.t_cooldown_hr) * actual_cycles),
        "cycle_metrics": cycle_metrics
    }

    with open(os.path.join(outdir, "results.json"), "w") as f:
        json.dump(clean_results, f, indent=4)
        
    return clean_results