# kernel/numba_kernel.py
import numpy as np
from numba import njit, prange

from engine.state import derive_properties_kernel
from engine.operators.fill import apply_fill
from engine.operators.drain import apply_drain
from engine.operators.settle import apply_settle
from engine.operators.flatten import apply_flatten
from engine.operators.heat import apply_heat

@njit(parallel=True, fastmath=True, cache=True, nogil=True)
def mega_kernel_cycle(ncfg, ngrid, mat, m, H, 
                      snapshots_T, snapshots_m, snapshots_fill, max_snaps,
                      cycle_summary_row, progress_tracker, cancel_flag):
    N = ngrid.N
    
    # Allocate temporary working arrays
    T = np.zeros(N)
    rho = np.zeros(N)
    k = np.zeros(N)
    mu = np.zeros(N)
    fs = np.zeros(N)
    cp_eff = np.zeros(N)
    cap = np.zeros(N)
    fill_frac = np.zeros(N)
    dH = np.zeros(N)
    
    h_start = np.interp(ncfg.T_start, mat.T_grid, mat.H_grid)
    
    # Initial derive for this cycle
    derive_properties_kernel(m, H, ngrid.V, h_start, mat, T, rho, k, mu, fs, cp_eff, cap, fill_frac)
    
    # Cumulative Trackers (local to this cycle)
    m_in_cum = 0.0; m_out_cum = 0.0
    H_in_cum = 0.0; H_out_cum = 0.0
    E_coil_cum = 0.0; E_loss_cum = 0.0
    
    # NEW: Track the true mass-weighted temperature of the drained fluid
    T_out_cum = 0.0 
    
    snap_idx = 0
    current_time_hr = 0.0
    cancelled = False
    
    # Cycle Start Metrics
    cycle_start_mass = 0.0
    cycle_start_T_avg = 0.0
    for i in range(N):
        if m[i] > 1e-6:
            cycle_start_mass += m[i]
            cycle_start_T_avg += T[i] * m[i]
            
    if cycle_start_mass > 1e-6:
        cycle_start_T_avg /= cycle_start_mass
    else:
        cycle_start_T_avg = ncfg.T_start
        
    cycle_m_out_start = m_out_cum
    cycle_H_out_start = H_out_cum
    cycle_m_in_start = m_in_cum
    cycle_E_coil_start = E_coil_cum
    cycle_E_loss_start = E_loss_cum
    
    total_expected_hr = ncfg.t_window_hr + ncfg.t_cooldown_hr
    
    # Run Heating & Cooling Phases
    for phase in range(2): 
        is_heating = (phase == 0)
        duration_hr = ncfg.t_window_hr if is_heating else ncfg.t_cooldown_hr
        
        t_phase_end = current_time_hr + duration_hr
        next_snap_time = current_time_hr + ncfg.snapshot_interval_hr
        
        dt = ncfg.dt_sec
        
        while current_time_hr < t_phase_end - 1e-6:
            
            if cancel_flag[0] == 1:
                cancelled = True
                break
            
            # A. Derive properties (Initial state for this dt)
            derive_properties_kernel(m, H, ngrid.V, h_start, mat, T, rho, k, mu, fs, cp_eff, cap, fill_frac)
            
            # B. Fill & Drain
            mass_moved = False
            
            if ncfg.simulate_fill:
                current_total_mass = 0.0
                for i in range(N):
                    current_total_mass += m[i]
                    
                if current_total_mass < ncfg.max_tank_mass:
                    dm_fill, dH_fill = apply_fill(m, H, mat, ncfg, ngrid)
                    if dm_fill > 0:
                        m_in_cum += dm_fill
                        H_in_cum += dH_fill
                        mass_moved = True
                        
            if ncfg.simulate_drain:
                # FIXED: Unpack 3 values and pass T array
                dm_drain, dH_drain, dT_drain = apply_drain(m, H, T, rho, mu, fs, mat, ncfg, ngrid)
                if dm_drain > 0:
                    m_out_cum += dm_drain
                    H_out_cum += dH_drain
                    T_out_cum += dT_drain # <--- Accumulate the true temperature sum
                    mass_moved = True
            
            # C. Re-derive properties (Handles mixing & thermal expansion BEFORE settling)
            if mass_moved:
                derive_properties_kernel(m, H, ngrid.V, h_start, mat, T, rho, k, mu, fs, cp_eff, cap, fill_frac)
                    
            # D. Settle & Flatten
            apply_settle(m, H, rho, fs, ncfg, ngrid)
            
            if mass_moved or (int(current_time_hr * 3600 / dt) % 10 == 0):
                apply_flatten(m, H, rho, mu, fs, ncfg, ngrid)
            
            # E. Thermal Physics
            T_out_coil, U_side, U_bottom = apply_heat(m, H, T, k, rho, ncfg, mat, ngrid, dH, is_heating)
            
            for i in prange(N):
                H[i] += dH[i]
                
            if is_heating:
                E_coil_cum += (ncfg.C_coil * (ncfg.T_water_in - T_out_coil) * dt)
                
            # Track wall loss using the new side and bottom areas
            q_loss = 0.0
            for i in range(N):
                if m[i] > 1e-9:
                    if ngrid.side_area[i] > 0:
                        q_loss += U_side * ngrid.side_area[i] * (T[i] - ncfg.T_amb_mid)
                    if ngrid.bottom_area[i] > 0:
                        q_loss += U_bottom * ngrid.bottom_area[i] * (T[i] - ncfg.T_amb_mid)
            E_loss_cum += q_loss * dt
            
            # F. RAM Snapshot
            if current_time_hr >= next_snap_time - 1e-6 and snap_idx < max_snaps:
                derive_properties_kernel(m, H, ngrid.V, h_start, mat, T, rho, k, mu, fs, cp_eff, cap, fill_frac)
                
                for i in prange(N):
                    snapshots_T[snap_idx, i] = T[i]
                    snapshots_m[snap_idx, i] = m[i]
                    snapshots_fill[snap_idx, i] = fill_frac[i]
                snap_idx += 1
                next_snap_time += ncfg.snapshot_interval_hr
                
            progress_tracker[0] = (current_time_hr / total_expected_hr) * 100.0
            progress_tracker[1] = float(snap_idx)
                
            # G. Adaptive Timestep
            max_dT = 0.0
            for i in range(N):
                if m[i] > 1e-6:
                    local_dT = abs(dH[i] / max(1e-6, m[i] * cp_eff[i]))
                    if local_dT > max_dT:
                        max_dT = local_dT
                        
            T_tol = 2.0
            if max_dT > T_tol:
                dt = max(ncfg.dt_sec * 0.5, 0.1)
            elif max_dT < T_tol * 0.5:
                dt = min(ncfg.dt_sec * 1.2, ncfg.dt_sec)
                
            current_time_hr += dt / 3600.0
            
        if cancelled: break

    # Calculate cycle summaries
    if not cancelled:
        solid_mass = 0.0; slurry_mass = 0.0; liquid_mass = 0.0; total_mass = 0.0; weighted_temp = 0.0
        for i in range(N):
            if m[i] > 1e-6:
                total_mass += m[i]
                weighted_temp += m[i] * T[i]
                if fs[i] >= 0.99: solid_mass += m[i]
                elif fs[i] >= 0.01: slurry_mass += m[i]
                else: liquid_mass += m[i]
                    
        avg_T = weighted_temp / max(1e-6, total_mass)
        
        cycle_m_out = m_out_cum - cycle_m_out_start
        cycle_m_in = m_in_cum - cycle_m_in_start
        
        # FIXED: Calculate drain temperature using the true T_out_cum sum
        drain_fluid_T = (T_out_cum / cycle_m_out) if cycle_m_out > 1e-6 else 0.0
        
        drain_util = (cycle_m_out / max(1e-6, cycle_start_mass)) * 100.0
        
        cycle_summary_row[0] = (solid_mass / max(1e-6, total_mass)) * 100.0
        cycle_summary_row[1] = (slurry_mass / max(1e-6, total_mass)) * 100.0
        cycle_summary_row[2] = (liquid_mass / max(1e-6, total_mass)) * 100.0
        cycle_summary_row[3] = avg_T
        cycle_summary_row[4] = drain_fluid_T
        cycle_summary_row[5] = drain_util
        cycle_summary_row[6] = cycle_start_T_avg
        cycle_summary_row[7] = avg_T
        cycle_summary_row[8] = (E_coil_cum - cycle_E_coil_start) / 3.6e6
        cycle_summary_row[9] = (E_loss_cum - cycle_E_loss_start) / 3.6e6
        cycle_summary_row[10] = cycle_m_out
        cycle_summary_row[11] = cycle_m_in
        
    progress_tracker[0] = 100.0
    progress_tracker[1] = float(snap_idx)
    
    return snap_idx, m_in_cum, m_out_cum