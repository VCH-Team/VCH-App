# physics/operators/settle.py
import numpy as np
from numba import njit, prange

@njit(parallel=True, cache=True)
def _settle_kernel(m, H, V, rho, mu, col_cells, col_start, col_len, dz, K_settle):
    n_cols = col_start.shape[0]
    
    for col in prange(n_cols):
        start = col_start[col]
        n = col_len[col]
        
        # 1. Find the surface (topmost non-empty cell) in this column
        surf = 0
        for q in range(n - 1, -1, -1):
            c = col_cells[start + q]
            if m[c] > 1e-9:
                surf = q
                break
                
        # If the whole column is empty, skip it
        if surf == 0 and m[col_cells[start]] <= 1e-9:
            continue
            
        # 2. Downward falling (gravity)
        # Look from the bottom up to the surface
        for q in range(surf): 
            c_bot = col_cells[start + q]
            c_top = col_cells[start + q + 1]
            
            if m[c_top] <= 1e-9:
                continue
                
            # Old physics: capacity uses the density of the falling fluid
            cap_bot = V[c_bot] * rho[c_top] 
            needed = cap_bot - m[c_bot]
            
            if needed <= 1e-9:
                continue
                
            h_head = (surf - q) * dz
            mobility = (K_settle * h_head) / max(1e-6, mu[c_top])
            mobility = min(1.0, max(0.01, mobility))
            
            moved = min(needed * mobility, m[c_top])
            if moved > 1e-9:
                h_spec = H[c_top] / m[c_top]
                m[c_bot] += moved
                H[c_bot] += moved * h_spec
                m[c_top] -= moved
                H[c_top] -= moved * h_spec
                
        # 3. Upward overflow (thermal expansion)
        # Look from the bottom to the top-1
        for q in range(n - 1):
            c_bot = col_cells[start + q]
            c_top = col_cells[start + q + 1]
            
            # Capacity uses the cell's own density
            cap_bot = V[c_bot] * rho[c_bot]
            excess = m[c_bot] - cap_bot
            
            if excess > 1e-9:
                h_spec = H[c_bot] / m[c_bot]
                m[c_top] += excess
                H[c_top] += excess * h_spec
                m[c_bot] -= excess
                H[c_bot] -= excess * h_spec

def apply(grid, state, mat, cfg):
    """
    Packs columns bottom-to-top (gravity + thermal expansion).
    """
    if grid.N == 0:
        return
        
    # Ensure rho and mu are up to date before packing
    state.update_derived(mat)
    
    dz = cfg["tank_height"] / cfg["res"]
    K_settle = cfg.get("K_settle", 1.0)
    
    _settle_kernel(
        state.m, state.H, state.V, state.rho, state.mu,
        grid.col_cells, grid.col_start, grid.col_len,
        dz, K_settle
    )
    
    # Update derived properties after moving mass
    state.update_derived(mat)