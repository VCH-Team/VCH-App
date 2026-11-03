# physics/state.py
import numpy as np
from numba import njit, prange

M_EPS = 1e-12

@njit(parallel=True, cache=True)
def _initial_fill(m, H, V, col_cells, col_start, col_len, f, rho_start, h_start):
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
def _derive(m, H, V, h_empty, has_melt, H_solid, H_liquid,
            T_grid, H_grid, rho_grid, k_grid, mu_grid, cp_eff_grid,
            T, rho, k, mu, fs, cp_eff, cap, fill):
    for c in prange(m.shape[0]):
        h = H[c] / m[c] if m[c] > M_EPS else h_empty
        Tc = np.interp(h, H_grid, T_grid)
        T[c] = Tc
        rho[c] = np.interp(Tc, T_grid, rho_grid)
        k[c] = np.interp(Tc, T_grid, k_grid)
        mu[c] = np.interp(Tc, T_grid, mu_grid)
        cp_eff[c] = np.interp(Tc, T_grid, cp_eff_grid)
        
        if has_melt and H_liquid > H_solid:
            liq = (h - H_solid) / (H_liquid - H_solid)
            liq = min(1.0, max(0.0, liq))
            fs[c] = 1.0 - liq
        else:
            fs[c] = 0.0
            
        cap[c] = rho[c] * V[c]  # Mass capacity in kg
        fill[c] = m[c] / cap[c] if m[c] > M_EPS else 0.0

class State:
    CONSERVED = ("m", "H")
    DERIVED = ("T", "rho", "k", "mu", "fs", "cp_eff", "cap", "fill")
    CUMULATIVE = ("m_in_cum", "m_out_cum", "H_in_cum", "H_out_cum", "E_coil_cum", "E_loss_cum")

    def __init__(self, grid, mat, cfg):
        n = int(grid.N)
        self.n_cells = n
        self.V = np.asarray(grid.V, dtype=np.float64)

        self.m = np.zeros(n)
        self.H = np.zeros(n)
        self.T_coil_out = 0
        for a in self.DERIVED:
            setattr(self, a, np.zeros(n))
            
        for a in self.CUMULATIVE:
            setattr(self, a, 0.0)

        self._initial_fill(grid, mat, cfg)
        self.update_derived(mat)

    def _initial_fill(self, grid, mat, cfg):
        T_start = float(cfg["T_start"])
        rho_start = float(np.interp(T_start, mat["T_grid"], mat["rho_grid"]))
        h_start = float(np.interp(T_start, mat["T_grid"], mat["H_grid"]))

        V_tank = float(self.V.sum())
        M_target = cfg.get("M_fluid")
        
        # If M_fluid is None or 0, fill the whole tank. Otherwise, use the requested mass.
        if M_target is None or M_target <= 0:
            M_target = rho_start * V_tank
        else:
            M_target = float(M_target)
        
        V_target = M_target / rho_start
        f = min(1.0, V_target / V_tank)

        _initial_fill(self.m, self.H, self.V,
                      np.asarray(grid.col_cells, dtype=np.int64),
                      np.asarray(grid.col_start, dtype=np.int64),
                      np.asarray(grid.col_len, dtype=np.int64),
                      f, rho_start, h_start)

        self.T_start = T_start
        self.h_start = h_start
        self.fill_fraction = f
        self.M_requested = M_target
        self.M_initial = float(self.m.sum())
        self.H_initial = float(self.H.sum())

    def update_derived(self, mat):
        T_ms = float(mat["T_ms"])
        T_me = float(mat["T_me"])
        has_melt = not (np.isnan(T_ms) or np.isnan(T_me))
        H_s = float(np.interp(T_ms, mat["T_grid"], mat["H_grid"])) if has_melt else 0.0
        H_l = float(np.interp(T_me, mat["T_grid"], mat["H_grid"])) if has_melt else 0.0
        
        _derive(self.m, self.H, self.V, self.h_start, has_melt, H_s, H_l,
                mat["T_grid"], mat["H_grid"], mat["rho_grid"], mat["k_grid"],
                mat["mu_grid"], mat["cp_eff_grid"],
                self.T, self.rho, self.k, self.mu, self.fs, self.cp_eff, self.cap, self.fill)

    def total_mass(self):
        return float(self.m.sum())

    def total_enthalpy(self):
        return float(self.H.sum())

    def check(self):
        for a in self.CONSERVED + self.DERIVED:
            arr = getattr(self, a)
            if not np.all(np.isfinite(arr)):
                raise FloatingPointError(f"State.{a} has non-finite values")
        if self.m.min() < -M_EPS:
            raise ValueError(f"negative cell mass: {self.m.min():.3e} kg")

    def copy(self):
        new = State.__new__(State)
        new.n_cells = self.n_cells
        new.V = self.V
        for attr in self.CONSERVED + self.DERIVED:
            setattr(new, attr, getattr(self, attr).copy())
        for attr in self.CUMULATIVE:
            setattr(new, attr, getattr(self, attr))
        for attr in ("T_start", "h_start", "fill_fraction", "M_requested", "M_initial", "H_initial", "T_coil_out"):
            setattr(new, attr, getattr(self, attr))
        return new