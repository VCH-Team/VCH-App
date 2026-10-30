# state.py -- everything that changes during the simulation.
#
# Two kinds of data:
#   CONSERVED (the truth)  : m [kg], H [J]           per cell
#   DERIVED  (recomputed)  : T, rho, k, mu, fs, cap, fill   per cell
# Derived arrays are always a pure function of (m, H) and the material tables.
# Operators change m and H only; call state.update_derived(mat) afterwards.
#
# Mesh interface assumed (attributes read from `mesh`):
#   mesh.n_cells                      int
#   mesh.V         (n_cells,)         cell volume [m3]
#   mesh.zc        (n_cells,)         cell-centre height [m]  (not used by v1 fill)
#   mesh.n_cols                       int, number of vertical columns
#   mesh.col_cells (n_cells,) int     cell ids, grouped by column, bottom -> top
#   mesh.col_start (n_cols,)  int     offset of each column in col_cells
#   mesh.col_len   (n_cols,)  int     number of cells in each column
import numpy as np
from numba import njit, prange

M_EPS = 1e-12          # below this a cell counts as empty [kg]


# ------------------------------------------------------------------ kernels
@njit(parallel=True, cache=True)
def _initial_fill(m, H, V, col_cells, col_start, col_len, f, rho_start, h_start):
    """Fill every column bottom-up to the same fraction f of its own volume.
    Columns are independent, so this is safe to run in parallel."""
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
            if remaining >= V[c] * (1.0 - 1e-12):      # full cell
                m[c] = V[c] * rho_start
                remaining -= V[c]
                if remaining < 0.0:
                    remaining = 0.0
            elif remaining > 0.0:                      # partial (top) cell
                m[c] = remaining * rho_start
                remaining = 0.0
            else:                                      # empty
                m[c] = 0.0
            H[c] = m[c] * h_start


@njit(parallel=True, cache=True)
def _derive(m, H, V, h_empty, has_melt, H_solid, H_liquid,
            T_grid, H_grid, rho_grid, k_grid, mu_grid, cp_eff_grid,
            T, rho, k, mu, fs, cap, fill):
    """Recompute all derived fields from (m, H). Cells are independent."""
    for c in prange(m.shape[0]):
        h = H[c] / m[c] if m[c] > M_EPS else h_empty   # specific enthalpy J/kg
        Tc = np.interp(h, H_grid, T_grid)
        T[c] = Tc
        rho[c] = np.interp(Tc, T_grid, rho_grid)
        k[c] = np.interp(Tc, T_grid, k_grid)
        mu[c] = np.interp(Tc, T_grid, mu_grid)
        cap[c] = np.interp(Tc, T_grid, cp_eff_grid)
        if has_melt and H_liquid > H_solid:
            liq = (h - H_solid) / (H_liquid - H_solid)
            liq = min(1.0, max(0.0, liq))
            fs[c] = 1.0 - liq
        else:
            fs[c] = 0.0
        fill[c] = m[c] / (rho[c] * V[c]) if m[c] > M_EPS else 0.0


# -------------------------------------------------------------------- State
class State:
    CONSERVED = ("m", "H")
    DERIVED = ("T", "rho", "k", "mu", "fs", "cap", "fill")
    CUMULATIVE = ("m_in_cum", "m_out_cum", "H_in_cum", "H_out_cum",
                  "E_coil_cum", "E_loss_cum")

    def __init__(self, mesh, mat, cfg):
        n = int(mesh.n_cells)
        self.n_cells = n
        self.V = np.asarray(mesh.V, dtype=np.float64)

        # conserved
        self.m = np.zeros(n)
        self.H = np.zeros(n)
        # derived
        self.T = np.zeros(n)
        self.rho = np.zeros(n)
        self.k = np.zeros(n)
        self.mu = np.zeros(n)
        self.fs = np.zeros(n)      # solid fraction 0..1 (from enthalpy in melt band)
        self.cap = np.zeros(n)     # effective specific heat cp_eff [J/kgK]
        self.fill = np.zeros(n)    # volumetric fill fraction m / (rho V)
        # cumulative bookkeeping (scalars; kernels return deltas, Python adds)
        for a in self.CUMULATIVE:
            setattr(self, a, 0.0)

        self._initial_fill(mesh, mat, cfg)
        self.update_derived(mat)

    # ---- initial fill ---------------------------------------------------
    def _initial_fill(self, mesh, mat, cfg):
        T_start = float(cfg["T_start"])
        rho_start = float(np.interp(T_start, mat["T_grid"], mat["rho_grid"]))
        # NOTE: np.interp(x, xp, fp): x=T_start, xp=T_grid, fp=H_grid.
        h_start = float(np.interp(T_start, mat["T_grid"], mat["H_grid"]))

        V_tank = float(self.V.sum())          # mesh volume => exact mass bookkeeping
        if cfg.get("fill_to_max", True) or cfg.get("M_fluid") is None:
            M_target = rho_start * V_tank
        else:
            M_target = float(cfg["M_fluid"])
        V_target = M_target / rho_start
        f = min(1.0, V_target / V_tank)       # fill fraction, capped at the rim

        _initial_fill(self.m, self.H, self.V,
                      np.asarray(mesh.col_cells, dtype=np.int64),
                      np.asarray(mesh.col_start, dtype=np.int64),
                      np.asarray(mesh.col_len, dtype=np.int64),
                      f, rho_start, h_start)

        self.T_start = T_start
        self.h_start = h_start
        self.fill_fraction = f
        self.M_requested = M_target
        self.M_initial = float(self.m.sum())  # what actually went in (after capping)

    # ---- derived fields -------------------------------------------------
    def update_derived(self, mat):
        T_ms = float(mat["T_ms"])
        T_me = float(mat["T_me"])
        has_melt = not (np.isnan(T_ms) or np.isnan(T_me))
        H_s = float(np.interp(T_ms, mat["T_grid"], mat["H_grid"])) if has_melt else 0.0
        H_l = float(np.interp(T_me, mat["T_grid"], mat["H_grid"])) if has_melt else 0.0
        _derive(self.m, self.H, self.V, self.h_start, has_melt, H_s, H_l,
                mat["T_grid"], mat["H_grid"], mat["rho_grid"], mat["k_grid"],
                mat["mu_grid"], mat["cp_eff_grid"],
                self.T, self.rho, self.k, self.mu, self.fs, self.cap, self.fill)

    # ---- diagnostics ----------------------------------------------------
    def total_mass(self):
        return float(self.m.sum())

    def total_enthalpy(self):
        return float(self.H.sum())

    def check(self):
        """Raise if the conserved state is corrupt. Cheap; call it while debugging."""
        for a in self.CONSERVED + self.DERIVED:
            arr = getattr(self, a)
            if not np.all(np.isfinite(arr)):
                raise FloatingPointError(f"State.{a} has non-finite values")
        if self.m.min() < -M_EPS:
            raise ValueError(f"negative cell mass: {self.m.min():.3e} kg")

    # ---- copy (for debugging / snapshots) -------------------------------
    def copy(self):
        new = State.__new__(State)
        new.n_cells = self.n_cells
        new.V = self.V                         # geometry never changes: share it
        for attr in self.CONSERVED + self.DERIVED:
            setattr(new, attr, getattr(self, attr).copy())
        for attr in self.CUMULATIVE:
            setattr(new, attr, getattr(self, attr))
        for attr in ("T_start", "h_start", "fill_fraction", "M_requested", "M_initial"):
            setattr(new, attr, getattr(self, attr))
        return new