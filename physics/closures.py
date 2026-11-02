# physics/closures.py
import numpy as np

def is_flowable(T, h, mat, cfg) -> bool:
    """Placeholder for Phase 7."""
    # For now, just return True (everything flows)
    return True

def h_internal(m_dot, d_in, d_coil_actual, rho, cp, mu, k) -> float:
    """Internal convection coefficient. (To be copied from legacy/heat_transfer.py later)."""
    return 100.0 # Dummy value

def h_external(T_cell, T_coil_fluid, rho, cp, k, mu, d_out, cfg) -> float:
    """External convection coefficient. (To be copied from legacy)."""
    return 50.0 # Dummy value

def nu_eff_buoyancy(Ra) -> float:
    """Stub for Phase 1. Returns 1.0 (no extra buoyancy)."""
    return 1.0

def cd_reynolds(Re) -> float:
    """Stub for Phase 1. Returns 0.6."""
    return 0.6

def k_face(k_i, k_j, T_i, T_j, rho_i, rho_j, cfg) -> float:
    """Harmonic mean for conduction."""
    if k_i + k_j == 0:
        return 0.0
    return (2.0 * k_i * k_j) / (k_i + k_j)

def calc_Q(m_dot, T_band, H_band, T_water_in, d_in, d_out, R_f_out, A_coil, d_coil_actual,
           T_water_arr, rho_water_arr, cp_water_arr, mu_water_arr, k_water_arr,
           T_tube_arr, k_tube_arr,
           T_grid, H_grid, rho_grid, cp_sens_grid, k_grid, mu_grid, T_ms, T_me, thresh_liq, thresh_visc,
           beta, dT_natural):
    
    if T_band >= T_water_in: return 0.0
    
    T_eff = 0.5 * (T_water_in + T_band)
    rho_c = np.interp(T_eff, T_water_arr, rho_water_arr)
    cp_c  = np.interp(T_eff, T_water_arr, cp_water_arr)
    mu_c  = np.interp(T_eff, T_water_arr, mu_water_arr)
    k_c   = np.interp(T_eff, T_water_arr, k_water_arr)
    k_tube = np.interp(T_eff, T_tube_arr, k_tube_arr)

    h_in  = h_internal(m_dot, d_in, d_coil_actual, rho_c, cp_c, mu_c, k_c)
    h_out = h_external(T_band, H_band, T_grid, H_grid, rho_grid, cp_sens_grid, k_grid, mu_grid, T_ms, T_me, thresh_liq, thresh_visc, beta, dT_natural, d_out)
                       
    R_in = 1.0 / max(1e-6, h_in)
    R_wall = (d_out * np.log(d_out/d_in)) / (2.0 * k_tube)
    U = 1.0 / (R_in + R_wall + R_f_out + 1.0 / max(1e-6, h_out))
    
    NTU = U * A_coil / max(1e-6, m_dot * cp_c)
    eps = 1.0 - np.exp(-NTU)
    
    return eps * m_dot * cp_c * (T_water_in - T_band)