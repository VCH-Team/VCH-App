# physics/closures.py
import numpy as np
from numba import njit

@njit(cache=True)
def nu_eff_buoyancy(Ra):
    if Ra < 1e4:
        return 1.0
        
    Pr = 5.0
    nu_lam = 0.68 + (0.67 * Ra**(1/4)) / (1 + (0.492/Pr)**(9/16))**(4/9)
    
    # HARD CAP: Convection can't be more than 100x pure conduction
    return min(100.0, max(1.0, nu_lam)) 

def cd_reynolds(Re):
    if Re < 10:
        return 0.1
    elif Re < 100:
        return 0.1 + (0.5 * (Re - 10) / 90.0)
    else:
        return 0.6

def is_flowable(T, H, T_grid, H_grid, mu_grid, T_ms, T_me, thresh_liq, thresh_visc, fs_lock=0.8):
    if np.isnan(T_ms) or np.isnan(T_me):
        return True
        
    H_solid = np.interp(T_ms, T_grid, H_grid)
    H_liquid = np.interp(T_me, T_grid, H_grid)
    
    if H_liquid > H_solid:
        frac = (H - H_solid) / (H_liquid - H_solid)
        frac = min(1.0, max(0.0, frac))
    else:
        frac = 1.0
        
    fs = 1.0 - frac
    
    # If it's almost entirely solid, it cannot flow
    if fs >= fs_lock:
        return False
        
    mu = np.interp(T, T_grid, mu_grid)
    return (frac >= thresh_liq) and (mu <= thresh_visc)

def k_face(k_i, k_j, T_i, T_j, rho_i, rho_j):
    return 2.0 * k_i * k_j / (k_i + k_j)

def h_internal(m_dot, d_in, d_coil_actual, rho, cp, mu, k):
    A = np.pi * (d_in/2.0)**2
    v = m_dot / (max(1e-6, rho) * A)
    Re = rho * v * d_in / max(1e-6, mu)
    Pr = mu * cp / max(1e-6, k)
    if Re > 10000.0:
        f = (0.79*np.log(Re) - 1.64)**-2
        Nu = (f/8.0)*(Re - 1000.0)*Pr/(1.0 + 2.17*np.sqrt(f/8.0)*(Pr**(2.0/3.0) - 1.0))
        Nu *= (1.0 + (d_in / d_coil_actual)**0.9)
    else:
        Nu = 4.36
    return Nu * k / d_in

def h_external(T_oil, H_oil, T_grid, H_grid, rho_grid, cp_grid, k_grid, mu_grid, T_ms, T_me, fs_lock, thresh_visc, beta, dT_natural, d_out):
    flowable = is_flowable(T_oil, H_oil, T_grid, H_grid, mu_grid, T_ms, T_me, fs_lock, thresh_visc)
    if not flowable:
        return 5.0
        
    rho = np.interp(T_oil, T_grid, rho_grid)
    cp  = np.interp(T_oil, T_grid, cp_grid)
    k   = np.interp(T_oil, T_grid, k_grid)
    mu  = np.interp(T_oil, T_grid, mu_grid)
    
    nu = mu / max(1e-6, rho)
    alpha = k / max(1e-6, rho * cp)
    Pr = nu / max(1e-6, alpha)
    
    d_char = d_out
    Ra = 9.81 * beta * dT_natural * (d_char**3) / max(1e-6, nu * alpha)
    Nu = (0.60 + (0.387 * Ra**(1.0/6.0)) / (1.0 + (0.559/max(1e-6, Pr))**(9.0/16.0))**(8.0/27.0))**2
    return Nu * k / d_char

@njit(cache=True)
def nu_eff_buoyancy(Ra):
    """
    Effective Nusselt number for natural convection on a vertical face.
    Based on Churchill-Chu correlation for a vertical plate.
    """
    if Ra < 1e4:
        return 1.0  # Pure conduction
        
    Pr = 5.0  # Approximate Prandtl number for oils/PCMs
    # Churchill-Chu for vertical plate
    nu_lam = 0.68 + (0.67 * Ra**(1/4)) / (1 + (0.492/Pr)**(9/16))**(4/9)
    return max(1.0, nu_lam)

def cd_reynolds(Re):
    """
    Discharge coefficient as a function of Reynolds number.
    Smooth transition from laminar to turbulent orifice flow.
    """
    if Re < 10:
        return 0.1  # Very thick, barely flows
    elif Re < 100:
        # Laminar transition
        return 0.1 + (0.5 * (Re - 10) / 90.0)
    else:
        return 0.6  # Fully turbulent

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