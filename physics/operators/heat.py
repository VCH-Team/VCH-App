# physics/operators/heat.py
import numpy as np
from numba import njit
from physics import closures

@njit(cache=True)
def _heat_kernel(T, k, nbr, A_face, d_face, coil_w, wall_area, U_wall, T_amb, q_total, dt, dH):
    """
    Calculates conduction, coil heating, and wall loss from a frozen T snapshot.
    """
    N = T.shape[0]
    
    # 1. Coil Heat (distributed proportionally to coil_w)
    for c in range(N):
        dH[c] += q_total * coil_w[c] * dt
        
    # 2. Conduction & Convection Hack
    # We only look at -x (0), -y (2), and -z (4) faces to avoid double-counting.
    for c in range(N):
        for f in (0, 2, 4):
            n = nbr[c, f]
            if n >= 0:
                k_c = k[c]
                k_n = k[n]
                k_avg = 2.0 * k_c * k_n / max(1e-9, (k_c + k_n))
                
                # The old convection hack: if vertical face and unstable, boost k by 50
                if f == 4: # Z-direction face
                    # If the cell below (c) is hotter than the cell above (n)
                    if T[c] > T[n]:
                        k_avg *= 50.0
                        
                q = k_avg * A_face[c, f] * (T[c] - T[n]) / d_face[c, f]
                
                # Energy out of c, into n
                dH[c] -= q * dt
                dH[n] += q * dt
                
    # 3. Wall Loss
    for c in range(N):
        if wall_area[c] > 0.0:
            q_wall = U_wall * wall_area[c] * (T[c] - T_amb)
            dH[c] -= q_wall * dt

def apply(grid, state, mat, coil_w, cfg, dt, R_coil, n_turns):
    """
    Python wrapper that calculates the coil heat and calls the kernel.
    """
    # 1. Calculate the average tank temperature over the coil band
    weight_sum = 0.0
    T_coil_avg = 0.0
    for c in range(grid.N):
        if coil_w[c] > 1e-6 and state.m[c] > 1e-6:
            T_coil_avg += state.T[c] * coil_w[c]
            weight_sum += coil_w[c]
            
    q_total = 0.0
    if weight_sum > 0.0:
        T_coil_avg /= weight_sum
        H_coil_avg = np.interp(T_coil_avg, mat["T_grid"], mat["H_grid"])
        
        m_dot = cfg["flow_m3h"] * np.interp(cfg["T_water_in"], cfg["T_water_arr"], cfg["rho_water_arr"]) / 3600.0
        A_coil = 2.0 * np.pi * R_coil * n_turns * cfg["d_out"]
        
        q_total = closures.calc_Q(
            m_dot, T_coil_avg, H_coil_avg, cfg["T_water_in"], cfg["d_in"], cfg["d_out"], cfg["R_f_out"],
            A_coil, 2.0*R_coil,
            cfg["T_water_arr"], cfg["rho_water_arr"], cfg["cp_water_arr"], cfg["mu_water_arr"], cfg["k_water_arr"],
            cfg["T_tube_arr"], cfg["k_tube_arr"],
            mat["T_grid"], mat["H_grid"], mat["rho_grid"], mat["cp_sens_grid"], mat["k_grid"], mat["mu_grid"],
            mat["T_ms"], mat["T_me"], cfg["thresh_liq"], cfg["thresh_visc"],
            cfg["beta_liq"], cfg["dT_natural"]
        )
        
        # Track the cumulative energy added by the coil
        state.E_coil_cum += q_total * dt

        # 2. Wall U-value (simplified for Phase 3)
    if cfg["h_air"] > 0:
        R_conv = 1.0 / cfg["h_air"]
        R_wall = cfg["t_wall"] / 16.0
        R_ins = (cfg["t_ins"] / cfg["k_ins"]) if cfg["t_ins"] > 0 else 0.0
        U_wall = 1.0 / (R_conv + R_wall + R_ins)
    else:
        U_wall = 0.0
    
    # 3. Call the Numba kernel
    dH = np.zeros(grid.N)
    _heat_kernel(state.T, state.k, grid.nbr, grid.A_face, grid.d_face, coil_w, grid.wall_area, U_wall, cfg["T_amb_mid"], q_total, dt, dH)
    
    # 4. Track wall loss BEFORE modifying H (kernel used old T)
    if U_wall > 0:
        q_wall_total = np.sum(U_wall * grid.wall_area * (state.T - cfg["T_amb_mid"]))
        state.E_loss_cum += q_wall_total * dt
    
    # 5. Apply energy change and update properties
    state.H += dH
    state.update_derived(mat)