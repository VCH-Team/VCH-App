# engine/operators/heat.py
import numpy as np
from numba import njit, prange
from engine.closures import h_internal, h_external, nu_eff_buoyancy, calc_U_side, calc_U_bottom

@njit(cache=True)
def march_coil(T, m, H, ncfg, mat, ngrid, dH_coil):
    """
    Sequential coil march. Iterates through coil segments, cooling the fluid
    and adding heat to the tank cells. Strictly serial.
    """
    T_fluid = ncfg.T_water_in
    C_coil = ncfg.C_coil
    
    for i in range(ngrid.coil_cells.shape[0]):
        c = ngrid.coil_cells[i]
        if m[c] <= 1e-6:
            continue
            
        T_cell = T[c]
        if T_fluid <= T_cell + 1e-3:
            break # Fluid has cooled below tank temp, no more heat transfer
            
        H_cell = H[c] / m[c]
        
        # 1. Internal convection (Constant fluid properties pre-calculated)
        h_in = h_internal(ncfg.m_dot_coil, ncfg.d_in, 2.0*ngrid.coil_R_coil, ncfg.rho_c, ncfg.cp_c, ncfg.mu_c, ncfg.k_c)
        
        # 2. External convection (Dynamic, depends on cell state)
        dT_drive = max(0.1, T_fluid - T_cell)
        h_out = h_external(T_cell, H_cell, mat, ncfg.thresh_liq, ncfg.thresh_visc, ncfg.beta_liq, dT_drive, ncfg.d_out)
        
        # 3. Overall U-value
        R_in = 1.0 / max(1e-6, h_in)
        R_wall = (ncfg.d_out * np.log(ncfg.d_out/ncfg.d_in)) / (2.0 * ncfg.k_tube)
        U = 1.0 / (R_in + R_wall + ncfg.R_f_out + 1.0 / max(1e-6, h_out))
        
        # 4. Effectiveness-NTU
        NTU = U * ngrid.coil_A_seg / max(1e-6, C_coil)
        eps = 1.0 - np.exp(-NTU)
        
        Q = eps * C_coil * (T_fluid - T_cell)
        
        # Add to the tank cell and cool the fluid
        dH_coil[c] += Q * ncfg.dt_sec
        T_fluid -= Q / max(1e-6, C_coil)
        
    return T_fluid

@njit(parallel=True, fastmath=True, cache=True)
def conduction_and_wall_kernel(m, T, k, rho, nbr, A_face, d_face, side_area, bottom_area, 
                               U_side, U_bottom, T_amb, dt, ncfg, dH):
    """
    Calculates conduction from all 6 neighbors and wall losses in parallel.
    """
    for c in prange(m.shape[0]):
        if m[c] <= 1e-9:
            continue
            
        q_net = 0.0
        
        # Loop over all 6 faces for conduction. (0=-x, 1=+x, 2=-y, 3=+y, 4=-z, 5=+z)
        for f in range(6):
            n = nbr[c, f]
            if n >= 0 and m[n] > 1e-9:
                k_c = k[c]
                k_n = k[n]
                # Harmonic mean of conductivity
                k_avg = 2.0 * k_c * k_n / max(1e-9, (k_c + k_n))
                
                # Vertical buoyancy (f=4 is bottom, f=5 is top)
                if (f == 4 and T[c] > T[n]) or (f == 5 and T[c] > T[n]):
                    dT = T[c] - T[n]
                    alpha = k_avg / max(1e-6, rho[c] * 1000.0) 
                    nu = max(1e-6, 1e-3 / rho[c])
                    Ra = 9.81 * 0.0007 * dT * (d_face[c,f]**3) / max(1e-9, nu * alpha)
                    k_avg *= nu_eff_buoyancy(Ra)
                    
                # Heat flowing INTO cell c from cell n
                q_net += k_avg * A_face[c, f] * (T[n] - T[c]) / d_face[c, f]
        
        # Wall losses (Side and Bottom)
        if side_area[c] > 0.0:
            q_net -= U_side * side_area[c] * (T[c] - T_amb)
            
        if bottom_area[c] > 0.0:
            q_net -= U_bottom * bottom_area[c] * (T[c] - T_amb)
            
        dH[c] += q_net * dt

@njit(cache=True)
def apply_heat(m, H, T, k, rho, ncfg, mat, ngrid, dH, is_heating):
    """
    Main entry point for the heat operator.
    """
    # 1. Zero out the enthalpy change array
    for i in range(dH.shape[0]):
        dH[i] = 0.0
        
    # 2. Sequential Coil March (if heating)
    T_out = ncfg.T_water_in
    if is_heating:
        T_out = march_coil(T, m, H, ncfg, mat, ngrid, dH)
        
    # 3. Calculate Wall U-Values
    # Separate averages for side and bottom walls
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
    
    # 4. Parallel Conduction and Wall Loss
    conduction_and_wall_kernel(
        m, T, k, rho, 
        ngrid.nbr, ngrid.A_face, ngrid.d_face, ngrid.side_area, ngrid.bottom_area,
        U_side, U_bottom, ncfg.T_amb_mid, ncfg.dt_sec, ncfg, dH
    )
        
    return T_out, U_side, U_bottom