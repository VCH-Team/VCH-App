# engine/state.py
import numpy as np
from numba import njit, prange

M_EPS = 1e-12

@njit(parallel=True, cache=True)
def initial_fill_kernel(m, H, V, col_cells, col_start, col_len, f, rho_start, h_start):
    n_cols = col_start.shape[0]
    for col in prange(n_cols):
        s = col_start[col]
        n = col_len[col]
        col_vol = 0.0
        for q in range(n):
            col_vol += V[col_cells[s + q]]
            
        remaining = f * col_vol
        for q in range(n):
            c = col_cells[s + q]
            if remaining >= V[c] * (1.0 - 1e-12):
                m[c] = V[c] * rho_start
                remaining -= V[c]
                if remaining < 0.0: remaining = 0.0
            elif remaining > 0.0:
                m[c] = remaining * rho_start
                remaining = 0.0
            else:
                m[c] = 0.0
            H[c] = m[c] * h_start

@njit(parallel=True, cache=True)
def derive_properties_kernel(m, H, V, h_empty, mat, T, rho, k, mu, fs, cp_eff, cap, fill):
    for c in prange(m.shape[0]):
        h = H[c] / m[c] if m[c] > M_EPS else h_empty
        Tc = np.interp(h, mat.H_grid, mat.T_grid)
        
        T[c] = Tc
        rho[c] = np.interp(Tc, mat.T_grid, mat.rho_grid)
        k[c] = np.interp(Tc, mat.T_grid, mat.k_grid)
        mu[c] = np.interp(Tc, mat.T_grid, mat.mu_grid)
        cp_eff[c] = np.interp(Tc, mat.T_grid, mat.cp_eff_grid)
        
        if mat.has_melt and mat.H_liquid > mat.H_solid:
            liq = (h - mat.H_solid) / (mat.H_liquid - mat.H_solid)
            liq = min(1.0, max(0.0, liq))
            fs[c] = 1.0 - liq
        else:
            fs[c] = 0.0
            
        cap[c] = rho[c] * V[c]
        fill[c] = m[c] / cap[c] if m[c] > M_EPS else 0.0