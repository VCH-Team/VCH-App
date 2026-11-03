# physics/operators/coil.py
import numpy as np
from physics import closures

class CoilSegments:
    def __init__(self, cells, A_seg, d_in, d_out, R_coil):
        self.cells = cells
        self.A_seg = A_seg
        self.d_in = d_in
        self.d_out = d_out
        self.R_coil = R_coil

def build_coil_segments(grid, cfg, R_coil, n_turns):
    """
    Finds all cells the coil passes through and sorts them bottom-to-top.
    """
    r_lo = R_coil - cfg["d_out"] / 2.0
    r_hi = R_coil + cfg["d_out"] / 2.0
    z_lo = cfg["coil_clearance_bottom"]
    z_hi = cfg["coil_clearance_bottom"] + cfg["L_avail"]
    
    cells = []
    for c in range(grid.N):
        r = np.sqrt(grid.xc[c]**2 + grid.yc[c]**2)
        z = grid.zc[c]
        if r_lo <= r <= r_hi and z_lo <= z <= z_hi:
            cells.append(c)
            
    if len(cells) == 0:
        return None
        
    # Sort the cells by Z height (bottom to top) to represent the serpentine flow
    cells = np.array(cells)
    sort_idx = np.argsort(grid.zc[cells])
    cells = cells[sort_idx]
    
    # Total area divided by number of segments
    L_total = 2.0 * np.pi * R_coil * n_turns
    A_total = np.pi * cfg["d_out"] * L_total
    A_seg = A_total / len(cells)
    
    return CoilSegments(cells, A_seg, cfg["d_in"], cfg["d_out"], R_coil)

def march(grid, state, mat, cfg, dt, coil_segs, is_heating=True):
    """
    Marches the coil fluid through the segments, calculating heat transfer.
    """
    dH_coil = np.zeros(grid.N)
    T_in = cfg["T_water_in"]
    
    if not is_heating or coil_segs is None or len(coil_segs.cells) == 0:
        return dH_coil, T_in, T_in
        
    # Fluid properties (assuming constant flow rate and properties)
    m_dot = cfg["flow_m3h"] * np.interp(T_in, cfg["T_water_arr"], cfg["rho_water_arr"]) / 3600.0
    rho_c = np.interp(T_in, cfg["T_water_arr"], cfg["rho_water_arr"])
    cp_c  = np.interp(T_in, cfg["T_water_arr"], cfg["cp_water_arr"])
    mu_c  = np.interp(T_in, cfg["T_water_arr"], cfg["mu_water_arr"])
    k_c   = np.interp(T_in, cfg["T_water_arr"], cfg["k_water_arr"])
    k_tube = np.interp(T_in, cfg["T_tube_arr"], cfg["k_tube_arr"])
    
    C_coil = m_dot * cp_c
    T_fluid = T_in
    
    for c in coil_segs.cells:
        if state.m[c] <= 1e-6:
            continue
            
        T_cell = state.T[c] 
        
        if T_fluid <= T_cell + 1e-3:
            break 
            
        H_cell = state.H[c] / state.m[c]
        
        # Calculate heat transfer coefficients
        h_in = closures.h_internal(m_dot, coil_segs.d_in, 2.0*coil_segs.R_coil, rho_c, cp_c, mu_c, k_c)
        
        dT_drive = max(0.1, T_fluid - T_cell)
        h_out = closures.h_external(
            T_cell, H_cell, mat["T_grid"], mat["H_grid"], mat["rho_grid"], mat["cp_sens_grid"], mat["k_grid"], mat["mu_grid"],
            mat["T_ms"], mat["T_me"], cfg["thresh_liq"], cfg["thresh_visc"],
            cfg["beta_liq"], dT_drive, coil_segs.d_out
        )
        
        R_in = 1.0 / max(1e-6, h_in)
        R_wall = (coil_segs.d_out * np.log(coil_segs.d_out/coil_segs.d_in)) / (2.0 * k_tube)
        U = 1.0 / (R_in + R_wall + cfg["R_f_out"] + 1.0 / max(1e-6, h_out))
        
        # Effectiveness-NTU
        NTU = U * coil_segs.A_seg / max(1e-6, C_coil)
        eps = 1.0 - np.exp(-NTU)
        
        Q = eps * C_coil * (T_fluid - T_cell)
        
        # Add to the tank
        dH_coil[c] += Q * dt
        
        # Cool the fluid for the next segment
        T_fluid -= Q / max(1e-6, C_coil)
        
    return dH_coil, T_in, T_fluid