# physics/operators/drain.py
import numpy as np
from physics import closures

def apply(grid, state, mat, cfg, dt, drain_cell_idx, drain_area):
    """
    Removes mass and enthalpy from the drain cell.
    Uses Torricelli's law with a fixed Cd = 0.6 (old physics).
    """
    if drain_area <= 0.0 or drain_cell_idx < 0:
        return
        
    m_drain = state.m[drain_cell_idx]
    if m_drain <= 1e-6:
        return

    # 1. Check if the fluid is flowable (solid fraction / viscosity)
    T_d = state.T[drain_cell_idx]
    h_d = state.H[drain_cell_idx] / m_drain
    flowable = closures.is_flowable(
        T_d, h_d, mat["T_grid"], mat["H_grid"], mat["mu_grid"], 
        mat["T_ms"], mat["T_me"], cfg["thresh_liq"], cfg["thresh_visc"]
    )
    if not flowable:
        return

    # 2. Find the surface of the column above the drain
    # To do this efficiently, we look up the grid columns
    surf_z = grid.zc[drain_cell_idx] # default to drain height if tank is almost empty
    
    # Find which column this drain belongs to
    # (We can precompute this, but for one cell per step it's fast enough to search)
    col_idx = -1
    for i in range(len(grid.col_start)):
        start = grid.col_start[i]
        length = grid.col_len[i]
        if drain_cell_idx in grid.col_cells[start:start+length]:
            col_idx = i
            break
            
    if col_idx >= 0:
        start = grid.col_start[col_idx]
        length = grid.col_len[col_idx]
        # Search from top to bottom for the highest non-empty cell
        for q in range(length - 1, -1, -1):
            c = grid.col_cells[start + q]
            if state.m[c] > 1e-6:
                surf_z = grid.zc[c]
                break

    # 3. Torricelli
    h_head = max(surf_z - grid.zc[drain_cell_idx], 0.01) # Avoid zero head
    rho_d = state.rho[drain_cell_idx]
    v = 0.6 * np.sqrt(2.0 * 9.81 * h_head)
    
    # 4. Remove mass
    target_dm = rho_d * v * drain_area * dt
    actual_dm = min(target_dm, m_drain)
    
    if actual_dm > 0.0:
        h_spec = state.H[drain_cell_idx] / m_drain
        
        state.m[drain_cell_idx] -= actual_dm
        state.H[drain_cell_idx] -= actual_dm * h_spec
        
        # Track cumulative losses
        state.m_out_cum += actual_dm
        state.H_out_cum += actual_dm * h_spec
        
        # Update properties for the drained cell
        state.update_derived(mat)