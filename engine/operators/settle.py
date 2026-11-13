# engine/operators/settle.py
import numpy as np
from numba import njit, prange

@njit(parallel=True, fastmath=True, cache=True)
def settle_kernel(m, H, V, rho, fs, col_cells, col_start, col_len, fs_lock, dt, dz):
    n_cols = col_start.shape[0]
    g = 9.81
    fall_dist = 0.5 * g * dt**2
    
    for col in prange(n_cols):
        start = col_start[col]
        n = col_len[col]
        
        # PASS 1: Downward (Gravity Cascade with Speed Limit)
        for q in range(n - 2, -1, -1):
            c_bot = col_cells[start + q]
            c_top = col_cells[start + q + 1]
            
            if fs[c_bot] >= fs_lock or fs[c_top] >= fs_lock:
                continue
                
            if m[c_top] <= 1e-9:
                continue
                
            cap_bot = V[c_bot] * rho[c_bot]
            space = cap_bot - m[c_bot]
            
            if space > 1e-9:
                # Limit how much mass can fall based on gravity speed
                max_fraction = fall_dist / dz
                if max_fraction > 1.0: max_fraction = 1.0
                max_mass_fall = m[c_top] * max_fraction
                
                moved = min(space, max_mass_fall)
                
                h_spec = H[c_top] / m[c_top]
                m[c_bot] += moved
                H[c_bot] += moved * h_spec
                m[c_top] -= moved
                H[c_top] -= moved * h_spec
                
        # PASS 2: Upward (Thermal Expansion)
        for q in range(n - 1):
            c_bot = col_cells[start + q]
            c_top = col_cells[start + q + 1]
            
            if fs[c_bot] >= fs_lock or fs[c_top] >= fs_lock:
                continue
                
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

@njit(cache=True)
def apply_settle(m, H, rho, fs, ncfg, ngrid):
    settle_kernel(
        m, H, ngrid.V, rho, fs, 
        ngrid.col_cells, ngrid.col_start, ngrid.col_len, 
        ncfg.fs_lock, ncfg.dt_sec, ncfg.dz
    )