# engine/closures.py
import numpy as np
from numba import njit

@njit(inline='always')
def is_flowable(H, H_solid, H_liquid, has_melt, mu, thresh_liq, thresh_visc):
    """
    Determines if the fluid is flowable based on liquid fraction and viscosity.
    """
    if not has_melt:
        return True
        
    if H_liquid > H_solid:
        frac = (H - H_solid) / (H_liquid - H_solid)
        frac = min(1.0, max(0.0, frac))
    else:
        frac = 1.0
        
    return (frac >= thresh_liq) and (mu <= thresh_visc)

@njit(inline='always')
def h_internal(m_dot, d_in, d_coil_actual, rho, cp, mu, k):
    """
    Coil side internal convection coefficient (Gnielinski correlation).
    """
    A = np.pi * (d_in/2.0)**2
    v = m_dot / (max(1e-6, rho) * A)
    Re = rho * v * d_in / max(1e-6, mu)
    Pr = mu * cp / max(1e-6, k)
    
    if Re > 10000.0:
        f = (0.79*np.log(Re) - 1.64)**-2
        Nu = (f/8.0)*(Re - 1000.0)*Pr/(1.0 + 2.17*np.sqrt(f/8.0)*(Pr**(2.0/3.0) - 1.0))
        Nu *= (1.0 + (d_in / d_coil_actual)**0.9) # Dean curvature correction
    else:
        Nu = 4.36 # Laminar fully developed
        
    return Nu * k / d_in

@njit(inline='always')
def h_external(T_oil, H_oil, mat, thresh_liq, thresh_visc, beta, dT_natural, d_out):
    """
    Tank side external convection coefficient (Churchill-Chu for vertical plate).
    If the fluid is solid, it falls back to pure conduction.
    """
    rho = np.interp(T_oil, mat.T_grid, mat.rho_grid)
    cp  = np.interp(T_oil, mat.T_grid, mat.cp_sens_grid)
    k   = np.interp(T_oil, mat.T_grid, mat.k_grid)
    mu  = np.interp(T_oil, mat.T_grid, mat.mu_grid)
    
    flowable = is_flowable(H_oil, mat.H_solid, mat.H_liquid, mat.has_melt, mu, thresh_liq, thresh_visc)
    
    if not flowable:
        return 2.0 * k / d_out
        
    nu = mu / max(1e-6, rho)
    alpha = k / max(1e-6, rho * cp)
    Pr = nu / max(1e-6, alpha)
    
    d_char = d_out
    Ra = 9.81 * beta * dT_natural * (d_char**3) / max(1e-6, nu * alpha)
    Nu = (0.60 + (0.387 * Ra**(1.0/6.0)) / (1.0 + (0.559/max(1e-6, Pr))**(9.0/16.0))**(8.0/27.0))**2
    
    return Nu * k / d_char

@njit(inline='always')
def calc_U_side(T_avg_wall, T_wall_arr, k_wall_arr, h_air, t_wall, t_ins, k_ins):
    """
    Calculates overall heat transfer coefficient for the side walls.
    """
    if h_air <= 0:
        return 0.0
        
    R_conv = 1.0 / h_air
    k_wall = np.interp(T_avg_wall, T_wall_arr, k_wall_arr)
    R_wall = t_wall / k_wall
    R_ins = (t_ins / k_ins) if t_ins > 0 else 0.0
    
    return 1.0 / (R_conv + R_wall + R_ins)

@njit(inline='always')
def calc_U_bottom(T_avg_wall, T_wall_arr, k_wall_arr, h_air, t_wall, 
                  t_ins_bottom, k_ins, grounded, k_ground, L_ground):
    """
    Calculates overall heat transfer coefficient for the bottom.
    Differentiates between elevated (air) and grounded (conduction).
    """
    k_wall = np.interp(T_avg_wall, T_wall_arr, k_wall_arr)
    R_wall = t_wall / k_wall
    R_ins = (t_ins_bottom / k_ins) if t_ins_bottom > 0 else 0.0
    
    if grounded:
        # Heat conducts into the ground (no air convection on the bottom)
        R_ground = L_ground / max(1e-6, k_ground)
        return 1.0 / (R_ground + R_wall + R_ins)
    else:
        # Heat convects into the air
        if h_air <= 0:
            return 0.0
        R_conv = 1.0 / h_air
        return 1.0 / (R_conv + R_wall + R_ins)

@njit(inline='always')
def nu_eff_buoyancy(Ra):
    """
    Effective Nusselt number for natural convection on a vertical face.
    """
    if Ra < 1e4:
        return 1.0  # Pure conduction
        
    Pr = 5.0  # Approximate Prandtl number
    nu_lam = 0.68 + (0.67 * Ra**(1/4)) / (1 + (0.492/Pr)**(9/16))**(4/9)
    
    # Cap to prevent explicit time-stepping instability
    return min(100.0, max(1.0, nu_lam))

@njit(inline='always')
def cd_reynolds(Re):
    """
    Discharge coefficient as a function of Reynolds number.
    """
    if Re < 10:
        return 0.1
    elif Re < 100:
        return 0.1 + (0.5 * (Re - 10) / 90.0)
    else:
        return 0.6