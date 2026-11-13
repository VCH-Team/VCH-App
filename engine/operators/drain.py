# engine/operators/drain.py
import numpy as np
from numba import njit
from engine.closures import is_flowable, cd_reynolds

@njit(cache=True)
def apply_drain(m, H, T, rho, mu, fs, mat, ncfg, ngrid):
    if not ncfg.simulate_drain or ncfg.drain_cell_idx < 0 or ncfg.drain_area <= 0.0:
        return 0.0, 0.0, 0.0
        
    c = ncfg.drain_cell_idx
    if m[c] <= 1e-6:
        return 0.0, 0.0, 0.0
        
    h_d = H[c] / m[c]
    flowable = is_flowable(h_d, mat.H_solid, mat.H_liquid, mat.has_melt, mu[c], ncfg.thresh_liq, ncfg.thresh_visc)
    if not flowable:
        return 0.0, 0.0, 0.0

    # Find surface height above drain
    surf_z = 0.0
    start = ngrid.col_start[ncfg.drain_col_idx]
    length = ngrid.col_len[ncfg.drain_col_idx]
    
    for q in range(length - 1, -1, -1):
        cell = ngrid.col_cells[start + q]
        if m[cell] > 1e-6:
            surf_z = ngrid.zc[cell]
            break

    # FIX: If the fluid level is below the drain, the pump does nothing
    h_head = surf_z - ngrid.zc[c]
    if h_head <= 1e-6:
        return 0.0, 0.0, 0.0

    rho_d = rho[c]
    
    # --- PUMP HEAD & PRESSURE ---
    total_head_m = h_head + ncfg.pump_head_m
    v_guess = 0.6 * np.sqrt(2.0 * 9.81 * total_head_m)
    D_hole = np.sqrt(4.0 * ncfg.drain_area / np.pi)
    
    Re = rho_d * v_guess * D_hole / max(1e-6, mu[c])
    Cd = cd_reynolds(Re)
    
    v = Cd * np.sqrt(2.0 * 9.81 * total_head_m)
    mdot_ideal = rho_d * v * ncfg.drain_area
    target_dm = mdot_ideal * ncfg.dt_sec
    
    # --- MOTOR POWER LIMITING ---
    max_motor_power_w = ncfg.motor_power_kw * 1000.0 * 0.70
    if total_head_m > 0.01:
        mdot_max_power = max_motor_power_w / (9.81 * total_head_m)
        if mdot_ideal > mdot_max_power:
            target_dm = mdot_max_power * ncfg.dt_sec
            
    if ncfg.drain_max_flow_m3h > 0:
        max_mdot = ncfg.drain_max_flow_m3h * rho_d / 3600.0
        target_dm = min(target_dm, max_mdot * ncfg.dt_sec)

    # --- SPHERE OF INFLUENCE ---
    R_inf = total_head_m * 0.5
    if R_inf < D_hole * 2.0: 
        R_inf = D_hole * 2.0
        
    sum_w = 0.0
    sum_m = 0.0
    sum_mu_m = 0.0       
    sum_m_solid = 0.0    
    
    for i in range(ngrid.N):
        if m[i] <= 1e-6: continue
        
        # FIX: Strictly enforce that we only pull from between drain height and fluid surface
        dz = ngrid.zc[i] - ngrid.zc[c]
        if dz < 0 or ngrid.zc[i] > surf_z + 1e-6: 
            continue
            
        dist = np.sqrt((ngrid.xc[i] - ngrid.xc[c])**2 + (ngrid.yc[i] - ngrid.yc[c])**2)
        if dist < R_inf:
            w = 1.0 - (dist / R_inf)**2
            sum_w += w
            sum_m += m[i]
            sum_mu_m += mu[i] * m[i]
            if fs[i] >= ncfg.fs_lock:
                sum_m_solid += m[i]
            
    if sum_w <= 1e-6 or sum_m <= 1e-6:
        return 0.0, 0.0, 0.0
        
    # --- PUMP CHOKING CHECK ---
    avg_mu = sum_mu_m / sum_m
    solid_frac_pct = (sum_m_solid / sum_m) * 100.0
    
    if avg_mu > ncfg.pump_max_visc or solid_frac_pct > ncfg.pump_chunk_tol_pct:
        return 0.0, 0.0, 0.0 
        
    actual_dm_total = 0.0
    actual_dH_total = 0.0
    actual_T_total = 0.0
    
    for i in range(ngrid.N):
        if m[i] <= 1e-6: continue
        
        # FIX: Re-apply the strict bounds for the removal loop
        dz = ngrid.zc[i] - ngrid.zc[c]
        if dz < 0 or ngrid.zc[i] > surf_z + 1e-6:
            continue
            
        dist = np.sqrt((ngrid.xc[i] - ngrid.xc[c])**2 + (ngrid.yc[i] - ngrid.yc[c])**2)
        if dist < R_inf:
            w = 1.0 - (dist / R_inf)**2
            dm_remove = target_dm * (w / sum_w)
            actual_dm = min(dm_remove, m[i])
            
            if actual_dm > 0:
                T_cell = T[i] 
                h_spec = H[i] / m[i]
                m[i] -= actual_dm
                H[i] -= actual_dm * h_spec
                
                actual_dm_total += actual_dm
                actual_dH_total += actual_dm * h_spec
                actual_T_total += actual_dm * T_cell
                
    return actual_dm_total, actual_dH_total, actual_T_total