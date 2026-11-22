# engine/operators/fill.py
import numpy as np
from numba import njit
from engine.closures import is_flowable

@njit(cache=True)
def apply_fill(m, H, mat, ncfg, ngrid, fall_state, dt):
    if not ncfg.simulate_fill or ncfg.fill_cell_idx < 0 or ncfg.fill_mdot <= 0.0:
        return 0.0, 0.0
        
    c = ncfg.fill_cell_idx
    
    rho_fill = np.interp(ncfg.fill_T, mat.T_grid, mat.rho_grid)
    h_fill = np.interp(ncfg.fill_T, mat.T_grid, mat.H_grid)
    mu_fill = np.interp(ncfg.fill_T, mat.T_grid, mat.mu_grid)
    
    flowable = is_flowable(h_fill, mat.H_solid, mat.H_liquid, mat.has_melt, mu_fill, ncfg.thresh_liq, ncfg.thresh_visc)
    if not flowable:
        return 0.0, 0.0
    
    # Calculate mass entering in this dt
    dm = ncfg.fill_mdot * rho_fill * dt
    
    if ncfg.fill_max_flow_m3h > 0:
        max_vol_m3s = ncfg.fill_max_flow_m3h / 3600.0
        max_dm = max_vol_m3s * rho_fill * dt
        dm = min(dm, max_dm)
        
    if dm <= 0.0:
        return 0.0, 0.0
        
    dH = dm * h_fill
    
    # Instead of dumping into the grid, add to the falling block
    fall_state[0] += dm
    fall_state[1] += dH
    
    # If the block was at rest, give it the nozzle exit velocity
    if fall_state[3] == 0.0:
        # Use the fill_area we added to NumbaConfig
        v_exit = ncfg.fill_mdot / max(1e-6, ncfg.fill_area)
        fall_state[3] = v_exit
        
    return dm, dH