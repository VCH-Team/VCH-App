# engine/operators/drop.py
import numpy as np
from numba import njit
from engine.closures import is_flowable

@njit(cache=True)
def apply_drop(m, H, T, rho, mu, fs, mat, ncfg, ngrid, fall_state, dt):
    """
    fall_state: [m_block, H_block, z_block, v_block]
    """
    m_block = fall_state[0]
    H_block = fall_state[1]
    z_block = fall_state[2]
    v_block = fall_state[3]
    
    # If no mass is falling, we are done
    if m_block <= 1e-9:
        return
        
    # 1. Kinematics (Gravity Fall)
    v_block += 9.81 * dt
    z_block -= v_block * dt
    
    # 2. Find the fluid surface level in the nozzle column
    c_nozzle = ncfg.fill_cell_idx
    # Find the column for the nozzle
    col_start = ngrid.col_start[ncfg.drain_col_idx] # Need to pass fill_col_idx
    col_len = ngrid.col_len[ncfg.drain_col_idx]
    
    surf_z = 0.0
    for q in range(col_len - 1, -1, -1):
        cell = ngrid.col_cells[col_start + q]
        if m[cell] > 1e-6:
            surf_z = ngrid.zc[cell]
            break
            
    # 3. Collision / Deposition
    if z_block <= surf_z + 1e-3:
        # Block has hit the surface. 
        # Calculate impact spread based on velocity
        # Higher velocity -> higher Re -> wider spread
        D_hole = np.sqrt(4.0 * ncfg.fill_area / np.pi)
        rho_fill = np.interp(ncfg.fill_T, mat.T_grid, mat.rho_grid)
        mu_fill = np.interp(ncfg.fill_T, mat.T_grid, mat.mu_grid)
        
        Re_impact = rho_fill * v_block * D_hole / max(1e-6, mu_fill)
        
        # Fanning radius (empirical)
        # Low Re (laminar) -> stays narrow. High Re (turbulent) -> fans out.
        if Re_impact < 2000.0:
            spread_radius_m = D_hole * 1.5 # Narrow
        else:
            # Turbulent jet spreads at roughly 15 degrees
            spread_radius_m = D_hole * 1.5 + (v_block * 0.25) 
            
        # Convert to grid cells
        cell_size = (ngrid.V[0]) ** (1/3)
        r_cells = int(np.ceil(spread_radius_m / cell_size))
        if r_cells < 1: r_cells = 1
        
        # Find target cells on the surface
        # (Simplified: we just dump it into the nozzle cell and let settle/flatten handle the rest)
        target_c = c_nozzle
        
        # Add mass to the grid
        cap = ngrid.V[target_c] * rho_fill
        space = max(0.0, cap - m[target_c])
        actual_dm = min(m_block, space)
        
        if actual_dm > 0:
            m[target_c] += actual_dm
            H[target_c] += actual_dm * (H_block / m_block)
            m_block -= actual_dm
            H_block -= actual_dm * (H_block / m_block) # careful with div by zero if m_block goes to 0
            
        # If the block is fully deposited, reset it
        if m_block <= 1e-9:
            m_block = 0.0
            H_block = 0.0
            z_block = ncfg.tank_height
            v_block = 0.0
        else:
            # If it couldn't deposit everything, it sits on the surface
            z_block = surf_z
            v_block = 0.0
            
    # Update state
    fall_state[0] = m_block
    fall_state[1] = H_block
    fall_state[2] = z_block
    fall_state[3] = v_block