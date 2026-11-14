# engine/operators/fill.py
import numpy as np
from numba import njit
from engine.closures import is_flowable

@njit(cache=True)
def apply_fill(m, H, mat, ncfg, ngrid):
    if not ncfg.simulate_fill or ncfg.fill_cell_idx < 0 or ncfg.fill_mdot <= 0.0:
        return 0.0, 0.0
        
    c = ncfg.fill_cell_idx
    
    rho_fill = np.interp(ncfg.fill_T, mat.T_grid, mat.rho_grid)
    h_fill = np.interp(ncfg.fill_T, mat.T_grid, mat.H_grid)
    mu_fill = np.interp(ncfg.fill_T, mat.T_grid, mat.mu_grid)
    
    flowable = is_flowable(h_fill, mat.H_solid, mat.H_liquid, mat.has_melt, mu_fill, ncfg.thresh_liq, ncfg.thresh_visc)
    if not flowable:
        return 0.0, 0.0
    
    dm = ncfg.fill_mdot * rho_fill * ncfg.dt_sec
    
    if ncfg.fill_max_flow_m3h > 0:
        max_vol_m3s = ncfg.fill_max_flow_m3h / 3600.0
        max_dm = max_vol_m3s * rho_fill * ncfg.dt_sec
        dm = min(dm, max_dm)
        
    if dm <= 0.0:
        return 0.0, 0.0
        
    # Distribute across target cells
    target_cells = np.zeros(5, dtype=np.int32)
    num_targets = 0
    
    target_cells[num_targets] = c
    num_targets += 1
    
    if ncfg.fill_radius_cells >= 1:
        for f in range(4):
            n = ngrid.nbr[c, f]
            if n >= 0:
                target_cells[num_targets] = n
                num_targets += 1
                
    dm_per_cell = dm / num_targets
    actual_dm_total = 0.0
    actual_dH_total = 0.0
    
    for i in range(num_targets):
        target = target_cells[i]
        
        # FIX: Always check physical capacity, even if fill_spread is True
        cap = ngrid.V[target] * rho_fill
        space = max(0.0, cap - m[target])
        
        actual_dm = min(dm_per_cell, space)
        
        if actual_dm > 0.0:
            m[target] += actual_dm
            H[target] += actual_dm * h_fill
            actual_dm_total += actual_dm
            actual_dH_total += actual_dm * h_fill
            
    return actual_dm_total, actual_dH_total