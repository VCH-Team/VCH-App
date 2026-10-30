# physics/properties.py
"""
Recompute derived quantities (T, rho, k, mu, fs, cap, fill) from the
conserved state (m, H).

Called after any operator that changes mass or enthalpy.

Empty cells (m <= M_MIN) are masked with NaN in T/rho/k/mu/fs, and 0 in
cap/fill, so any accidental use of an empty cell shows up as a bug instead
of silently returning garbage.
"""
import numpy as np

M_MIN = 1e-6  # kg — cells below this are treated as empty


def refresh(grid, state, mat):
    """Update state in place from state.m and state.H.

    Args:
        grid: Grid object (uses .V and .N)
        state: State object (reads .m, .H; writes .T, .rho, .k, .mu,
               .fs, .cap, .fill)
        mat: material dict with T_grid, H_grid, rho_grid, k_grid,
             mu_grid, fs_grid
    """
    N = grid.N
    m = state.m
    H = state.H

    # Which cells actually contain mass? A boolean array of length N.
    non_empty = m > M_MIN

    # Specific enthalpy h = H / m.
    # Guard against divide-by-zero for empty cells — only divide where
    # non_empty is True.
    h = np.zeros(N, dtype=np.float64)
    h[non_empty] = H[non_empty] / m[non_empty]

    # Invert h -> T using the material's enthalpy table.
    # np.interp works on arrays: pass an array of h values, get an array
    # of T values back. No loop needed — NumPy does it in C.
    state.T[:] = np.interp(h, mat["H_grid"], mat["T_grid"])

    # Now look up the other properties from T.
    state.rho[:] = np.interp(state.T, mat["T_grid"], mat["rho_grid"])
    state.k[:]   = np.interp(state.T, mat["T_grid"], mat["k_grid"])
    state.mu[:]  = np.interp(state.T, mat["T_grid"], mat["mu_grid"])
    state.fs[:]  = np.interp(state.T, mat["T_grid"], mat["fs_grid"])

    # Capacity: the mass this cell could hold at its own temperature.
    # cap = rho(T) * V
    state.cap[:] = state.rho * grid.V

    # Fill fraction: actual mass / capacity.
    # np.maximum(cap, 1e-9) avoids divide-by-zero for empty cells whose
    # rho might be NaN (masked below).
    safe_cap = np.maximum(state.cap, 1e-9)
    state.fill[:] = m / safe_cap

    # Mask empty cells — set to NaN (T/rho/k/mu/fs) and 0 (cap/fill).
    state.T[~non_empty]   = np.nan
    state.rho[~non_empty] = np.nan
    state.k[~non_empty]   = np.nan
    state.mu[~non_empty]  = np.nan
    state.fs[~non_empty]  = np.nan
    state.cap[~non_empty]  = 0.0
    state.fill[~non_empty] = 0.0