# physics/operators/drain.py
import numpy as np
from physics import closures

def apply(grid, state, mat, cfg, dt, drain_cell_idx, drain_area):
    if drain_area <= 0.0 or drain_cell_idx < 0:
        return
        
    m_drain = state.m[drain_cell_idx]
    if m_drain <= 1e-6:
        return

    T_d = state.T[drain_cell_idx]
    h_d = state.H[drain_cell_idx] / m_drain
    flowable = closures.is_flowable(
        T_d, h_d, mat["T_grid"], mat["H_grid"], mat["mu_grid"], 
        mat["T_ms"], mat["T_me"], cfg["thresh_liq"], cfg["thresh_visc"]
    )
    if not flowable:
        return

    # Find the surface
    surf_z = grid.zc[drain_cell_idx]
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
        for q in range(length - 1, -1, -1):
            c = grid.col_cells[start + q]
            if state.m[c] > 1e-6:
                surf_z = grid.zc[c]
                break

    h_head = max(surf_z - grid.zc[drain_cell_idx], 0.01) 
    rho_d = state.rho[drain_cell_idx]
    
    # --- NEW PHYSICS: Cd depends on Reynolds number ---
    # First, guess the velocity with Cd=0.6 to get a rough Re
    v_guess = 0.6 * np.sqrt(2.0 * 9.81 * h_head)
    D_hole = np.sqrt(4.0 * drain_area / np.pi)
    Re = rho_d * v_guess * D_hole / max(1e-6, state.mu[drain_cell_idx])
    
    Cd = closures.cd_reynolds(Re)
    v = Cd * np.sqrt(2.0 * 9.81 * h_head)
    
    target_dm = rho_d * v * drain_area * dt
    actual_dm = min(target_dm, m_drain)
    
    if actual_dm > 0.0:
        h_spec = state.H[drain_cell_idx] / m_drain
        state.m[drain_cell_idx] -= actual_dm
        state.H[drain_cell_idx] -= actual_dm * h_spec
        
        state.m_out_cum += actual_dm
        state.H_out_cum += actual_dm * h_spec
        
        state.update_derived(mat)