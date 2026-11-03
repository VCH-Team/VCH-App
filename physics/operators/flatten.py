# physics/operators/flatten.py
import numpy as np
from numba import njit

@njit(cache=True)
def _flatten_kernel(m, H, V, rho, mu, fs, nbr, col_height, dz, dt, fs_lock):
    N = m.shape[0]
    g = 9.81
    
    for c in range(N):
        if fs[c] >= fs_lock: continue # Locked cells don't flow
        
        for f in (0, 1, 2, 3):
            n = nbr[c, f]
            if n < 0: continue
            if fs[n] >= fs_lock: continue # Can't flow into a solid block
            
            h_c = col_height[c]
            h_n = col_height[n]
            
            local_dh = h_c - h_n
            if local_dh <= 1e-6: continue
                
            if m[c] <= 1e-9 or m[n] >= V[n] * rho[n] - 1e-9: continue
                
            h_film = (m[c] / (rho[c] * V[c])) * dz
            nu = mu[c] / max(1e-6, rho[c])
            d_face = np.sqrt(V[c] / dz) 
            
            q_vol = (g * h_film**3 / (3.0 * max(1e-6, nu))) * (local_dh / d_face)
            mdot = q_vol * rho[c] * d_face
            
            moved = min(mdot * dt, m[c] * 0.5)
            moved = min(moved, V[n] * rho[n] - m[n])
            
            if moved > 1e-9:
                h_spec = H[c] / m[c]
                m[c] -= moved
                H[c] -= moved * h_spec
                m[n] += moved
                H[n] += moved * h_spec

def apply(grid, state, mat, cfg):
    if grid.N == 0: return
    state.update_derived(mat)
    dz = cfg["tank_height"] / cfg["res"]
    
    col_height = np.zeros(grid.N)
    for i in range(len(grid.col_start)):
        start = grid.col_start[i]
        length = grid.col_len[i]
        vol_col = 0.0
        for q in range(length):
            c = grid.col_cells[start + q]
            if state.m[c] > 1e-9:
                vol_col += state.m[c] / max(1e-6, state.rho[c])
        area_col = grid.V[grid.col_cells[start]] / dz
        eff_h = vol_col / max(1e-9, area_col)
        for q in range(length):
            c = grid.col_cells[start + q]
            col_height[c] = eff_h

    _flatten_kernel(
        state.m, state.H, state.V, state.rho, state.mu, state.fs,
        grid.nbr, col_height, dz, cfg["dt_sec"], cfg["fs_lock"]
    )
    state.update_derived(mat)