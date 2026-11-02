# physics/operators/flatten.py
import numpy as np
from numba import njit

@njit(cache=True)
def _flatten_kernel(m, H, V, rho, mu, nbr, col_height, dz, K_settle):
    """
    Moves mass laterally between adjacent columns to level the surface.
    """
    N = m.shape[0]
    
    # Check all 4 lateral faces (-x, +x, -y, +y)
    for c in range(N):
        for f in (0, 1, 2, 3):
            n = nbr[c, f]
            if n < 0:
                continue
                
            # h_c is the effective height of the column containing cell c
            h_c = col_height[c]
            h_n = col_height[n]
            
            local_dh = h_c - h_n
            if local_dh <= 1e-4:
                continue
                
            # Only move fluid that is actually present
            if m[c] <= 1e-9:
                continue
                
            # Capacity of the receiving cell
            cap_n = V[n] * rho[c] # use donor's density
            needed = cap_n - m[n]
            if needed <= 1e-9:
                continue
                
            mobility = (K_settle * local_dh) / max(1e-6, mu[c])
            mobility = min(1.0, max(0.01, mobility))
            
            moved = min(m[c] * mobility * 0.5, needed)
            if moved > 1e-9:
                h_spec = H[c] / m[c]
                m[c] -= moved
                H[c] -= moved * h_spec
                m[n] += moved
                H[n] += moved * h_spec

def apply(grid, state, mat, cfg):
    """
    Python wrapper that calculates column heights and calls the kernel.
    """
    if grid.N == 0:
        return
        
    state.update_derived(mat)
    K_settle = cfg.get("K_settle", 1.0)
    dz = cfg["tank_height"] / cfg["res"]
    
    # 1. Calculate the effective height of every column
    col_height = np.zeros(grid.N)
    
    # We can compute the volume of each column, then divide by its base area
    # Since cells are cubic (dx=dy=dz), base area = V[c] / dz
    for i in range(len(grid.col_start)):
        start = grid.col_start[i]
        length = grid.col_len[i]
        
        vol_col = 0.0
        for q in range(length):
            c = grid.col_cells[start + q]
            if state.m[c] > 1e-9:
                vol_col += state.m[c] / max(1e-6, state.rho[c])
                
        # Area of the column is just the area of one cell in that column
        area_col = grid.V[grid.col_cells[start]] / dz
        eff_h = vol_col / max(1e-9, area_col)
        
        # Assign this height to all cells in the column
        for q in range(length):
            c = grid.col_cells[start + q]
            col_height[c] = eff_h

    # 2. Run the kernel
    _flatten_kernel(
        state.m, state.H, state.V, state.rho, state.mu, 
        grid.nbr, col_height, dz, K_settle
    )
    
    # 3. Update properties
    state.update_derived(mat)