# physics/operators/heat.py
import numpy as np
from numba import njit
from physics.operators import coil

@njit(cache=True)
def _heat_kernel(T, k, nbr, A_face, d_face, wall_area, U_wall, T_amb, dt, dH):
    """
    Calculates conduction and wall loss from a frozen T snapshot.
    """
    N = T.shape[0]
        
    # 1. Conduction & Convection Hack
    for c in range(N):
        for f in (0, 2, 4):
            n = nbr[c, f]
            if n >= 0:
                k_c = k[c]
                k_n = k[n]
                k_avg = 2.0 * k_c * k_n / max(1e-9, (k_c + k_n))
                
                if f == 4: # Z-direction face
                    if T[c] > T[n]:
                        k_avg *= 50.0
                        
                q = k_avg * A_face[c, f] * (T[c] - T[n]) / d_face[c, f]
                
                dH[c] -= q * dt
                dH[n] += q * dt
                
    # 2. Wall Loss
    for c in range(N):
        if wall_area[c] > 0.0:
            q_wall = U_wall * wall_area[c] * (T[c] - T_amb)
            dH[c] -= q_wall * dt

def apply(grid, state, mat, coil_segs, cfg, dt, is_heating=True):
    """
    Combined heat-flux pass: Coil + Conduction + Wall Loss.
    """
    # 1. Calculate Coil Heat
    dH_coil, T_in, T_out = coil.march(grid, state, mat, cfg, dt, coil_segs, is_heating)
    
    state.E_coil_cum += np.sum(dH_coil)
    state.T_coil_out = T_out

    # Start with the coil heat
    dH = np.copy(dH_coil)

    # 2. Wall U-value
    if cfg["h_air"] > 0:
        R_conv = 1.0 / cfg["h_air"]
        R_wall = cfg["t_wall"] / 16.0
        R_ins = (cfg["t_ins"] / cfg["k_ins"]) if cfg["t_ins"] > 0 else 0.0
        U_wall = 1.0 / (R_conv + R_wall + R_ins)
    else:
        U_wall = 0.0
    
    # 3. Add Conduction and Wall Loss
    _heat_kernel(state.T, state.k, grid.nbr, grid.A_face, grid.d_face, grid.wall_area, U_wall, cfg["T_amb_mid"], dt, dH)
    
    # 4. Track wall loss for audit
    if U_wall > 0:
        q_wall_total = np.sum(U_wall * grid.wall_area * (state.T - cfg["T_amb_mid"]))
        state.E_loss_cum += q_wall_total * dt
    
    # 5. Apply energy change and update properties
    state.H += dH
    state.update_derived(mat)