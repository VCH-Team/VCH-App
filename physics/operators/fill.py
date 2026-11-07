# physics/operators/fill.py
import numpy as np

def apply(grid, state, mat, cfg, dt, fill_cell_idx, m_dot, T_fill):
    if m_dot <= 0.0 or fill_cell_idx < 0:
        return
        
    rho_fill = np.interp(T_fill, mat["T_grid"], mat["rho_grid"])
    h_fill = np.interp(T_fill, mat["T_grid"], mat["H_grid"])
    
    dm = m_dot * dt
    
    # Cap by max flow rate if specified
    max_flow = cfg.get("fill_max_flow_m3h", 0.0)
    if max_flow > 0:
        max_mdot = max_flow * rho_fill / 3600.0
        dm = min(dm, max_mdot * dt)
    
    if dm > 0.0:
        # If fill_spread is False, we only fill up to the cell's capacity
        if not cfg.get("fill_spread", True):
            cap = grid.V[fill_cell_idx] * rho_fill
            space = max(0.0, cap - state.m[fill_cell_idx])
            dm = min(dm, space)
            
        if dm > 0.0:
            state.m[fill_cell_idx] += dm
            state.H[fill_cell_idx] += dm * h_fill
            
            state.m_in_cum += dm
            state.H_in_cum += dm * h_fill
            
            state.update_derived(mat)