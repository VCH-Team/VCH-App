# engine/operators/heat.py
import numpy as np
from numba import njit, prange
from engine.closures import h_internal, h_external, nu_eff_buoyancy, calc_U_side, calc_U_bottom

@njit(cache=True)
def march_coil(T, m, H, ncfg, mat, ngrid, dH_coil, dt):
    T_fluid = ncfg.T_water_in
    C_coil = ncfg.C_coil
    
    for i in range(ngrid.coil_cells.shape[0]):
        c = ngrid.coil_cells[i]
        if m[c] <= 1e-6:
            continue
            
        T_cell = T[c]
        
        # B6 Fix: Use continue instead of break so downstream segments still exchange heat
        if T_fluid <= T_cell + 1e-3:
            continue 
            
        H_cell = H[c] / m[c]
        
        h_in = h_internal(ncfg.m_dot_coil, ncfg.d_in, 2.0*ngrid.coil_R_coil, ncfg.rho_c, ncfg.cp_c, ncfg.mu_c, ncfg.k_c)
        
        dT_drive = max(0.1, T_fluid - T_cell)
        h_out = h_external(T_cell, H_cell, mat, ncfg.thresh_liq, ncfg.thresh_visc, ncfg.beta_liq, dT_drive, ncfg.d_out)
        
        R_in = 1.0 / max(1e-6, h_in)
        R_wall = (ncfg.d_out * np.log(ncfg.d_out/ncfg.d_in)) / (2.0 * ncfg.k_tube)
        U = 1.0 / (R_in + R_wall + ncfg.R_f_out + 1.0 / max(1e-6, h_out))
        
        NTU = U * ngrid.coil_A_seg / max(1e-6, C_coil)
        eps = 1.0 - np.exp(-NTU)
        
        Q = eps * C_coil * (T_fluid - T_cell)
        
        # B1 Fix: Use the dynamic dt
        dH_coil[c] += Q * dt
        T_fluid -= Q / max(1e-6, C_coil)
        
    return T_fluid

@njit(parallel=True, fastmath=True, cache=True)
def conduction_and_wall_kernel(m, T, k, rho, mu, cp_sens, nbr, A_face, d_face, side_area, bottom_area, 
                               U_side, U_bottom, T_amb, dt, ncfg, mat, dH):
    
    for c in prange(m.shape[0]):
        if m[c] <= 1e-9:
            continue
            
        q_net = 0.0
        
        for f in range(6):
            n = nbr[c, f]
            if n >= 0 and m[n] > 1e-9:
                k_c = k[c]
                k_n = k[n]
                k_avg = 2.0 * k_c * k_n / max(1e-9, (k_c + k_n))
                
                # B3 Fix: Buoyancy sign
                # f == 4 is BOTTOM neighbor. f == 5 is TOP neighbor.
                # Unstable if bottom is HOTTER than top.
                unstable = False
                if f == 4 and T[n] > T[c] + 1e-3: # Neighbor (below) is hotter than cell (above)
                    unstable = True
                elif f == 5 and T[c] > T[n] + 1e-3: # Cell (below) is hotter than neighbor (above)
                    unstable = True
                    
                if unstable:
                    dT = np.abs(T[c] - T[n])
                    rho_avg = 0.5 * (rho[c] + rho[n])
                    mu_avg = 0.5 * (mu[c] + mu[n])
                    cp_avg = 0.5 * (cp_sens[c] + cp_sens[n])
                    
                    # B4 Fix: Real properties
                    nu = mu_avg / max(1e-6, rho_avg)
                    alpha = k_avg / max(1e-6, rho_avg * cp_avg)
                    Pr = nu / max(1e-9, alpha)
                    
                    T_avg = 0.5 * (T[c] + T[n])
                    beta_avg = np.interp(T_avg, mat.T_grid, mat.beta_grid) # Dynamic Beta
                    
                    Ra = 9.81 * beta_avg * dT * (d_face[c,f]**3) / max(1e-9, nu * alpha)
                    k_avg *= nu_eff_buoyancy(Ra, Pr)
                    
                q_net += k_avg * A_face[c, f] * (T[n] - T[c]) / d_face[c, f]
        
        if side_area[c] > 0.0:
            q_net -= U_side * side_area[c] * (T[c] - T_amb)
            
        if bottom_area[c] > 0.0:
            q_net -= U_bottom * bottom_area[c] * (T[c] - T_amb)
            
        dH[c] += q_net * dt # B1 Fix: Use dynamic dt

@njit(cache=True)
def apply_heat(m, H, T, k, rho, mu, cp_sens, ncfg, mat, ngrid, dH, is_heating, dt):
    for i in range(dH.shape[0]):
        dH[i] = 0.0
        
    T_out = ncfg.T_water_in
    if is_heating:
        T_out = march_coil(T, m, H, ncfg, mat, ngrid, dH, dt)
        
    sum_T_side = 0.0; count_side = 0
    sum_T_bot = 0.0; count_bot = 0
    
    for c in range(m.shape[0]):
        if m[c] > 1e-9:
            if ngrid.side_area[c] > 0.0:
                sum_T_side += T[c]
                count_side += 1
            if ngrid.bottom_area[c] > 0.0:
                sum_T_bot += T[c]
                count_bot += 1
                
    avg_T_side = (sum_T_side / count_side) if count_side > 0 else ncfg.T_amb_mid
    avg_T_bot = (sum_T_bot / count_bot) if count_bot > 0 else ncfg.T_amb_mid
    
    U_side = calc_U_side(avg_T_side, ncfg.T_wall_arr, ncfg.k_wall_arr, ncfg.h_air, ncfg.t_wall, ncfg.t_ins, ncfg.k_ins)
    U_bottom = calc_U_bottom(avg_T_bot, ncfg.T_wall_arr, ncfg.k_wall_arr, ncfg.h_air, ncfg.t_wall, 
                             ncfg.t_ins_bottom, ncfg.k_ins, ncfg.grounded, ncfg.k_ground, ncfg.L_ground)
    
    conduction_and_wall_kernel(
        m, T, k, rho, mu, cp_sens, 
        ngrid.nbr, ngrid.A_face, ngrid.d_face, ngrid.side_area, ngrid.bottom_area,
        U_side, U_bottom, ncfg.T_amb_mid, dt, ncfg, mat, dH
    )
        
    return T_out, U_side, U_bottom