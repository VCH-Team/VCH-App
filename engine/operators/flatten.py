# engine/operators/flatten.py
import numpy as np
from numba import njit, prange

@njit(parallel=True, cache=True)
def _compute_column_heights(m, rho, V, dz, col_cells, col_start, col_len, col_height):
    n_cols = col_start.shape[0]
    for i in prange(n_cols):
        start = col_start[i]
        length = col_len[i]
        
        vol_col = 0.0
        for q in range(length):
            c = col_cells[start + q]
            if m[c] > 1e-9:
                vol_col += m[c] / max(1e-6, rho[c])
                
        area_col = V[col_cells[start]] / dz
        eff_h = vol_col / max(1e-9, area_col)
        
        for q in range(length):
            c = col_cells[start + q]
            col_height[c] = eff_h

@njit(parallel=True, fastmath=True, cache=True)
def _flatten_kernel(m, H, V, rho, mu, fs, nbr, col_height, dz, dt, fs_lock):
    N = m.shape[0]
    g = 9.81
    
    dm = np.zeros(N)
    dH = np.zeros(N)
    
    for c in prange(N):
        if fs[c] >= fs_lock:
            continue
            
        # Mid-air check: Don't flatten if fluid is falling
        if nbr[c, 4] >= 0 and m[nbr[c, 4]] <= 1e-9:
            continue
            
        for f in range(4):
            n = nbr[c, f]
            if n < 0 or fs[n] >= fs_lock:
                continue
                
            local_dh = col_height[c] - col_height[n]
            
            if local_dh > 1e-6:
                if m[c] <= 1e-9 or m[n] >= V[n] * rho[n] - 1e-9:
                    continue
                h_film = (m[c] / (rho[c] * V[c])) * dz
                nu = mu[c] / max(1e-6, rho[c])
                d_face = np.sqrt(V[c] / dz)
                q_vol = (g * h_film**3 / (3.0 * max(1e-6, nu))) * (local_dh / d_face)
                mdot = q_vol * rho[c] * d_face
                
                # Limit to 10% of mass per face to prevent negative mass
                moved = min(mdot * dt, m[c] * 0.1)
                moved = min(moved, V[n] * rho[n] - m[n])
                
                if moved > 1e-9:
                    h_spec = H[c] / m[c]
                    dm[c] -= moved
                    dH[c] -= moved * h_spec
                    
            elif local_dh < -1e-6:
                if m[n] <= 1e-9 or m[c] >= V[c] * rho[c] - 1e-9:
                    continue
                h_film = (m[n] / (rho[n] * V[n])) * dz
                nu = mu[n] / max(1e-6, rho[n])
                d_face = np.sqrt(V[n] / dz)
                q_vol = (g * h_film**3 / (3.0 * max(1e-6, nu))) * (-local_dh / d_face)
                mdot = q_vol * rho[n] * d_face
                
                # Limit to 10% of mass per face
                moved = min(mdot * dt, m[n] * 0.1)
                moved = min(moved, V[c] * rho[c] - m[c])
                
                if moved > 1e-9:
                    h_spec = H[n] / m[n]
                    dm[c] += moved
                    dH[c] += moved * h_spec

    for c in prange(N):
        m[c] += dm[c]
        H[c] += dH[c]

@njit(cache=True)
def apply_flatten(m, H, rho, mu, fs, ncfg, ngrid):
    col_height = np.zeros(ngrid.N)
    _compute_column_heights(m, rho, ngrid.V, ncfg.dz, ngrid.col_cells, ngrid.col_start, ngrid.col_len, col_height)
    _flatten_kernel(m, H, ngrid.V, rho, mu, fs, ngrid.nbr, col_height, ncfg.dz, ncfg.dt_sec, ncfg.fs_lock)