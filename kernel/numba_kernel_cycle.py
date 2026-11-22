# kernel/numba_kernel_cycle.py
import numpy as np
from numba import njit, prange

from engine.state import derive_properties_kernel
from engine.operators.fill import apply_fill
from engine.operators.drop import apply_drop     # <--- IMPORT DROP
from engine.operators.drain import apply_drain
from engine.operators.settle import apply_settle
from engine.operators.flatten import apply_flatten
from engine.operators.heat import apply_heat
from engine.operators.audit import audit_kernel

@njit(parallel=True, fastmath=True, cache=True, nogil=True)
def mega_kernel_cycle(ncfg, ngrid, mat, m, H, fall_state, # <--- ADD fall_state
                      snapshots_T, snapshots_m, snapshots_fill, max_snaps,
                      cycle_summary_row, progress_tracker, cancel_flag):
    N = ngrid.N
    
    T = np.zeros(N); rho = np.zeros(N); k = np.zeros(N); mu = np.zeros(N)
    fs = np.zeros(N); cp_eff = np.zeros(N); cp_sens = np.zeros(N)
    cap = np.zeros(N); fill_frac = np.zeros(N); dH = np.zeros(N)
    
    h_start = np.interp(ncfg.T_start, mat.T_grid, mat.H_grid)
    derive_properties_kernel(m, H, ngrid.V, h_start, mat, T, rho, k, mu, fs, cp_eff, cp_sens, cap, fill_frac)
    
    m_in_cum = 0.0; m_out_cum = 0.0; H_in_cum = 0.0; H_out_cum = 0.0
    E_coil_cum = 0.0; E_loss_cum = 0.0; T_out_cum = 0.0 
    
    snap_idx = 0; current_time_hr = 0.0; cancelled = False
    
    cycle_start_mass = 0.0; cycle_start_H = 0.0; cycle_start_T_avg = 0.0
    for i in range(N):
        cycle_start_H += H[i]
        if m[i] > 1e-6:
            cycle_start_mass += m[i]
            cycle_start_T_avg += T[i] * m[i]
            
    cycle_start_mass += fall_state[0] # Include any initial falling mass
    cycle_start_H += fall_state[1]
    
    if cycle_start_mass > 1e-6:
        cycle_start_T_avg = (cycle_start_T_avg + fall_state[0] * ncfg.fill_T) / cycle_start_mass
    else:
        cycle_start_T_avg = ncfg.T_start
        
    cycle_m_out_start = m_out_cum; cycle_H_out_start = H_out_cum; cycle_m_in_start = m_in_cum
    cycle_E_coil_start = E_coil_cum; cycle_E_loss_start = E_loss_cum
    
    total_expected_hr = ncfg.t_window_hr + ncfg.t_cooldown_hr
    time_since_flatten = 0.0
    flatten_interval_sec = 10.0 * ncfg.dt_sec

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
            
            derive_properties_kernel(m, H, ngrid.V, h_start, mat, T, rho, k, mu, fs, cp_eff, cp_sens, cap, fill_frac)
            
            mass_moved = False
            
            # 1. FILL (Adds to fall_state)
            if ncfg.simulate_fill:
                current_total_mass = fall_state[0]
                for i in range(N): current_total_mass += m[i]
                    
                if current_total_mass < ncfg.max_tank_mass:
                    dm_fill, dH_fill = apply_fill(m, H, mat, ncfg, ngrid, fall_state, dt)
                    if dm_fill > 0:
                        m_in_cum += dm_fill; H_in_cum += dH_fill; mass_moved = True
                        
            # 2. DROP (Falls and impacts)
            if fall_state[0] > 1e-9:
                apply_drop(m, H, T, rho, mu, fs, mat, ncfg, ngrid, fall_state, dt)
                mass_moved = True # Trigger a re-derive if mass was deposited

            # 3. DRAIN
            if ncfg.simulate_drain:
                dm_drain, dH_drain, dT_drain = apply_drain(m, H, T, rho, mu, fs, mat, ncfg, ngrid)
                if dm_drain > 0:
                    m_out_cum += dm_drain; H_out_cum += dH_drain; T_out_cum += dT_drain; mass_moved = True
            
            if mass_moved:
                derive_properties_kernel(m, H, ngrid.V, h_start, mat, T, rho, k, mu, fs, cp_eff, cp_sens, cap, fill_frac)
                    
            # 4. SETTLE & FLATTEN
            apply_settle(m, H, rho, fs, ncfg, ngrid)
            
            time_since_flatten += dt
            if mass_moved or time_since_flatten >= flatten_interval_sec:
                apply_flatten(m, H, rho, mu, fs, ncfg, ngrid, time_since_flatten)
                time_since_flatten = 0.0
            
            # 5. HEAT
            T_out_coil, U_side, U_bottom = apply_heat(m, H, T, k, rho, mu, cp_sens, ncfg, mat, ngrid, dH, is_heating, dt)
            
            for i in prange(N): H[i] += dH[i]
                
            if is_heating:
                E_coil_cum += (ncfg.C_coil * (ncfg.T_water_in - T_out_coil) * dt)
                
            q_loss = 0.0
            for i in range(N):
                if m[i] > 1e-9:
                    if ngrid.side_area[i] > 0: q_loss += U_side * ngrid.side_area[i] * (T[i] - ncfg.T_amb_mid)
                    if ngrid.bottom_area[i] > 0: q_loss += U_bottom * ngrid.bottom_area[i] * (T[i] - ncfg.T_amb_mid)
            E_loss_cum += q_loss * dt
            
            # 6. SNAPSHOT
            if current_time_hr >= next_snap_time - 1e-6 and snap_idx < max_snaps:
                derive_properties_kernel(m, H, ngrid.V, h_start, mat, T, rho, k, mu, fs, cp_eff, cp_sens, cap, fill_frac)
                for i in prange(N):
                    snapshots_T[snap_idx, i] = T[i]
                    snapshots_m[snap_idx, i] = m[i]
                    snapshots_fill[snap_idx, i] = fill_frac[i]
                snap_idx += 1
                next_snap_time += ncfg.snapshot_interval_hr
                
            progress_tracker[0] = (current_time_hr / total_expected_hr) * 100.0
            progress_tracker[1] = float(snap_idx)
                
            max_dT = 0.0
            for i in range(N):
                if m[i] > 1e-6:
                    local_dT = abs(dH[i] / max(1e-6, m[i] * cp_eff[i]))
                    if local_dT > max_dT: max_dT = local_dT
                        
            T_tol = 2.0
            if max_dT > T_tol: dt = max(ncfg.dt_sec * 0.5, 0.1)
            elif max_dT < T_tol * 0.5: dt = min(ncfg.dt_sec * 1.2, ncfg.dt_sec)
                
            current_time_hr += dt / 3600.0
            
        if cancelled: break

    # --- CYCLE SUMMARY ---
    total_mass = 0.0; weighted_temp = 0.0
    solid_mass = 0.0; slurry_mass = 0.0; liquid_mass = 0.0
    
    if not cancelled:
        for i in range(N):
            if m[i] > 1e-6:
                total_mass += m[i]
                weighted_temp += m[i] * T[i]
                if fs[i] >= 0.99: solid_mass += m[i]
                elif fs[i] >= 0.01: slurry_mass += m[i]
                else: liquid_mass += m[i]
                    
        # Include falling mass in the total
        total_mass_with_falling = total_mass + fall_state[0]
        weighted_temp += fall_state[0] * ncfg.fill_T
        avg_T = weighted_temp / max(1e-6, total_mass_with_falling)
        
        cycle_m_out = m_out_cum - cycle_m_out_start
        cycle_m_in = m_in_cum - cycle_m_in_start
        drain_fluid_T = (T_out_cum / cycle_m_out) if cycle_m_out > 1e-6 else 0.0
        drain_util = (cycle_m_out / max(1e-6, cycle_start_mass)) * 100.0
        
        cycle_summary_row[0] = (solid_mass / max(1e-6, total_mass_with_falling)) * 100.0
        cycle_summary_row[1] = (slurry_mass / max(1e-6, total_mass_with_falling)) * 100.0
        cycle_summary_row[2] = (liquid_mass / max(1e-6, total_mass_with_falling)) * 100.0
        cycle_summary_row[3] = avg_T
        cycle_summary_row[4] = drain_fluid_T
        cycle_summary_row[5] = drain_util
        cycle_summary_row[6] = cycle_start_T_avg
        cycle_summary_row[7] = avg_T
        cycle_summary_row[8] = (E_coil_cum - cycle_E_coil_start) / 3.6e6
        cycle_summary_row[9] = (E_loss_cum - cycle_E_loss_start) / 3.6e6
        cycle_summary_row[10] = cycle_m_out
        cycle_summary_row[11] = cycle_m_in
        cycle_summary_row[12] = cycle_start_mass
        cycle_summary_row[13] = total_mass_with_falling
        
    progress_tracker[0] = 100.0
    progress_tracker[1] = float(snap_idx)
    
    # --- AUDIT ---
    # Temporarily inject falling mass so the audit is perfectly balanced
    if fall_state[0] > 1e-9 and ncfg.fill_cell_idx >= 0:
        m[ncfg.fill_cell_idx] += fall_state[0]
        H[ncfg.fill_cell_idx] += fall_state[1]
        
    m_resid, H_resid, final_m, expected_m = audit_kernel(
        m, H, cycle_start_mass, cycle_start_H, m_in_cum, m_out_cum, H_in_cum, H_out_cum, E_coil_cum, E_loss_cum
    )
    
    # Remove the temporary mass
    if fall_state[0] > 1e-9 and ncfg.fill_cell_idx >= 0:
        m[ncfg.fill_cell_idx] -= fall_state[0]
        H[ncfg.fill_cell_idx] -= fall_state[1]
        

    return snap_idx, m_in_cum, m_out_cum, final_m, m_resid, H_resid