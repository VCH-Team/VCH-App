# physics/operators/settle.py
import numpy as np
from numba import njit, prange

@njit(parallel=True, cache=True)
def _settle_kernel(m, H, V, rho, col_cells, col_start, col_len):
    n_cols = col_start.shape[0]
    
    for col in prange(n_cols):
        start = col_start[col]
        n = col_len[col]
        
        # PASS 1: Downward (Gravity)
        # Start from the bottom and pull mass down from the cell above
        for q in range(n - 1):
            c_bot = col_cells[start + q]
            c_top = col_cells[start + q + 1]
            
            if m[c_top] <= 1e-9:
                continue
                
            cap_bot = V[c_bot] * rho[c_bot]
            space = cap_bot - m[c_bot]
            
            if space > 1e-9:
                moved = min(space, m[c_top])
                h_spec = H[c_top] / m[c_top]
                m[c_bot] += moved
                H[c_bot] += moved * h_spec
                m[c_top] -= moved
                H[c_top] -= moved * h_spec
                
        # PASS 2: Upward (Thermal Expansion)
        # If the cell expanded, push the excess mass up
        for q in range(n - 1):
            c_bot = col_cells[start + q]
            c_top = col_cells[start + q + 1]
            
            if m[c_bot] <= 1e-9:
                continue
                
            cap_bot = V[c_bot] * rho[c_bot]
            excess = m[c_bot] - cap_bot
            
            if excess > 1e-9:
                h_spec = H[c_bot] / m[c_bot]
                m[c_bot] -= excess
                H[c_bot] -= excess * h_spec
                m[c_top] += excess
                H[c_top] += excess * h_spec

def apply(grid, state, mat, cfg):
    """
    Packs columns bottom-to-top (gravity + thermal expansion).
    """
    if grid.N == 0:
        return
        
    state.update_derived(mat)
    
    _settle_kernel(
        state.m, state.H, state.V, state.rho,
        grid.col_cells, grid.col_start, grid.col_len
    )
    
    state.update_derived(mat)