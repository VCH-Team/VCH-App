# engine/operators/fill.py
import numpy as np
from numba import njit
from engine.closures import is_flowable

@njit(cache=True)
def apply_fill(m, H, mat, ncfg, ngrid):
    """
    Injects mass and enthalpy. 
    Chokes if the fill fluid is solid at the specified temperature.
    """
    if not ncfg.simulate_fill or ncfg.fill_cell_idx < 0 or ncfg.fill_mdot <= 0.0:
        return 0.0, 0.0
        
    c = ncfg.fill_cell_idx
    
    # 1. Interpolate fill properties at the specified fill temperature
    rho_fill = np.interp(ncfg.fill_T, mat.T_grid, mat.rho_grid)
    h_fill = np.interp(ncfg.fill_T, mat.T_grid, mat.H_grid)
    mu_fill = np.interp(ncfg.fill_T, mat.T_grid, mat.mu_grid)
    
    # 2. Check if the fluid is solid (Pump Choking)
    flowable = is_flowable(h_fill, mat.H_solid, mat.H_liquid, mat.has_melt, mu_fill, ncfg.thresh_liq, ncfg.thresh_visc)
    if not flowable:
        return 0.0, 0.0  # Fill pump chokes!
    
    # 3. Calculate exact mass entering this timestep
    dm = ncfg.fill_mdot * rho_fill * ncfg.dt_sec
    
    # 4. Cap by max volumetric flow rate if specified
    if ncfg.fill_max_flow_m3h > 0:
        max_vol_m3s = ncfg.fill_max_flow_m3h / 3600.0
        max_dm = max_vol_m3s * rho_fill * ncfg.dt_sec
        dm = min(dm, max_dm)
        
    if dm > 0.0:
        # 5. Capacity check (if fill_spread is False)
        if not ncfg.fill_spread:
            cap = ngrid.V[c] * rho_fill
            space = max(0.0, cap - m[c])
            dm = min(dm, space)
            
        if dm > 0.0:
            m[c] += dm
            H[c] += dm * h_fill
            return dm, dm * h_fill
            
    return 0.0, 0.0