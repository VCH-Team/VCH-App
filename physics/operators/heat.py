# physics/operators/heat.py
import numpy as np
from numba import njit
from physics.operators import coil
from physics.closures import nu_eff_buoyancy

@njit(cache=True)
def _heat_kernel(m, T, k, rho, nbr, A_face, d_face, wall_area, U_wall, T_amb, dt, dH):
    N = T.shape[0]
        
    for c in range(N):
        # Skip empty cells entirely
        if m[c] <= 1e-9:
            continue
            
        for f in (0, 2, 4):
            n = nbr[c, f]
            # Only conduct if BOTH cells have mass
            if n >= 0 and m[n] > 1e-9:
                k_c = k[c]
                k_n = k[n]
                k_avg = 2.0 * k_c * k_n / max(1e-9, (k_c + k_n))
                
                if f == 4 and T[c] > T[n]: # Z-face, cell below is hotter
                    dT = T[c] - T[n]
                    alpha = k_avg / max(1e-6, rho[c] * 1000.0) 
                    nu = max(1e-6, 1e-3 / rho[c])
                    Ra = 9.81 * 0.0007 * dT * (d_face[c,f]**3) / max(1e-9, nu * alpha)
                    
                    nu_eff = nu_eff_buoyancy(Ra)
                    k_avg *= nu_eff
                        
                q = k_avg * A_face[c, f] * (T[c] - T[n]) / d_face[c, f]
                
                dH[c] -= q * dt
                dH[n] += q * dt
                
        # Wall loss only for cells with mass
        if wall_area[c] > 0.0:
            q_wall = U_wall * wall_area[c] * (T[c] - T_amb)
            dH[c] -= q_wall * dt

def apply(grid, state, mat, coil_segs, cfg, dt, is_heating=True):
    # ... (coil part stays same) ...
    dH_coil, T_in, T_out = coil.march(grid, state, mat, cfg, dt, coil_segs, is_heating)
    state.E_coil_cum += np.sum(dH_coil)
    state.T_coil_out = T_out
    dH = np.copy(dH_coil)

    if cfg["h_air"] > 0:
        R_conv = 1.0 / cfg["h_air"]
        R_wall = cfg["t_wall"] / 16.0
        R_ins = (cfg["t_ins"] / cfg["k_ins"]) if cfg["t_ins"] > 0 else 0.0
        U_wall = 1.0 / (R_conv + R_wall + R_ins)
    else:
        U_wall = 0.0
    
    # Pass state.m into the kernel
    _heat_kernel(state.m, state.T, state.k, state.rho, grid.nbr, grid.A_face, grid.d_face, grid.wall_area, U_wall, cfg["T_amb_mid"], dt, dH)
    
    if U_wall > 0:
        # Need to mask the wall loss calculation to non-empty cells
        q_wall_total = np.sum(U_wall * grid.wall_area * (state.T - cfg["T_amb_mid"]) * (state.m > 1e-9))
        state.E_loss_cum += q_wall_total * dt
    
    state.H += dH
    state.update_derived(mat)