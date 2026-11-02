# physics/phase_design.py
import numpy as np
from physics import closures

def _march_coil(T_tank, T_coil_in, m_dot, L_total, R_coil, d_in, d_out, R_f_out, mat, cfg, n_seg=50):
    """
    Calculates the total heat transfer (Q) for a given coil length (L).
    Marches segment-by-segment along the coil because the fluid cools down.
    """
    if L_total <= 0:
        return 0.0
        
    dL = L_total / n_seg
    A_seg = np.pi * d_out * dL
    T_coil = T_coil_in
    Q_total = 0.0
    
    # Pre-fetch tank properties at T_tank (assumed constant in Phase A)
    H_tank = np.interp(T_tank, mat["T_grid"], mat["H_grid"])
    T_ms = mat.get("T_ms", np.nan)
    T_me = mat.get("T_me", np.nan)
    
    for _ in range(n_seg):
        if T_coil <= T_tank + 1e-3:
            break
            
        dT = max(0.1, T_coil - T_tank)
        h_out = closures.h_external(
            T_tank, H_tank,
            mat["T_grid"], mat["H_grid"], mat["rho_grid"], mat["cp_sens_grid"], mat["k_grid"], mat["mu_grid"],
            T_ms, T_me, cfg["thresh_liq"], cfg["thresh_visc"],
            cfg["beta_liq"], dT, d_out
        )
        
        # Use cfg.get() with fallbacks so tests never crash if arrays are missing
        T_w = cfg.get("T_water_arr", mat["T_grid"])
        rho_c  = np.interp(T_coil, T_w, cfg.get("rho_water_arr", mat["rho_grid"]))
        cp_c   = np.interp(T_coil, T_w, cfg.get("cp_water_arr", mat["cp_sens_grid"]))
        mu_c   = np.interp(T_coil, T_w, cfg.get("mu_water_arr", mat["mu_grid"]))
        k_c    = np.interp(T_coil, T_w, cfg.get("k_water_arr", mat["k_grid"]))
        
        k_tube = np.interp(T_coil, cfg.get("T_tube_arr", mat["T_grid"]), cfg.get("k_tube_arr", np.full(len(mat["T_grid"]), 16.0)))
        
        h_in = closures.h_internal(m_dot, d_in, 2.0*R_coil, rho_c, cp_c, mu_c, k_c)
        
        R_in = 1.0 / max(1e-6, h_in)
        R_wall = (d_out * np.log(d_out/d_in)) / (2.0 * k_tube)
        U = 1.0 / (R_in + R_wall + R_f_out + 1.0 / max(1e-6, h_out))
        
        C_coil = m_dot * cp_c
        NTU = U * A_seg / max(1e-6, C_coil)
        eps = 1.0 - np.exp(-NTU)
        
        Q_seg = eps * C_coil * (T_coil - T_tank)
        
        Q_total += Q_seg
        T_coil -= Q_seg / max(1e-6, C_coil)
        
    return Q_total


def compute_ntu_curves(cfg, mat, R_coil, n_max, n_pts=50):
    """
    Generates the 6 NTU curves for the Phase A design chart.
    Returns a dictionary with 'L' (lengths) and 'curves' (the 6 lines).
    """
    # 1. Setup constant parameters (with fallback to mat if cfg arrays are missing)
    T_w = cfg.get("T_water_arr", mat["T_grid"])
    rho_w = cfg.get("rho_water_arr", mat["rho_grid"])
    
    m_dot = cfg["flow_m3h"] * np.interp(cfg["T_water_in"], T_w, rho_w) / 3600.0
    T_coil_in = cfg["T_water_in"]
    d_in = cfg["d_in"]
    d_out = cfg["d_out"]
    R_f_out = cfg["R_f_out"]
    
    # 2. Define the lengths we want to evaluate (0 to max length)
    L_max = 2.0 * np.pi * R_coil * n_max
    L_vals = np.linspace(0, L_max, n_pts)
    
    # 3. Find the 6 critical temperatures for the bands
    T_amb_low = cfg["T_amb_low"]
    T_ms = mat.get("T_ms", np.nan)
    T_me = mat.get("T_me", np.nan)
    T_target = cfg.get("T_target", T_coil_in - 5.0)
    
    bands = []
    if np.isnan(T_ms) or np.isnan(T_me):
        # No phase change (single phase fluid)
        bands = [
            (T_amb_low, "Coldest (Start)"),
            (T_target, "Hottest (Target)")
        ]
    else:
        # 6 lines for PCM (Solid, Slurry, Liquid regimes)
        bands = [
            (T_amb_low, "Solid (Low)"),
            (T_ms,      "Solid (High)"),
            (T_ms,      "Slurry (Low)"),
            (T_me,      "Slurry (High)"),
            (T_me,      "Liquid (Low)"),
            (T_target,  "Liquid (High)")
        ]
        
    # 4. Calculate Q vs L for each band
    curves = []
    for T_tank, label in bands:
        Q_vals = []
        for L in L_vals:
            Q = _march_coil(T_tank, T_coil_in, m_dot, L, R_coil, d_in, d_out, R_f_out, mat, cfg, n_seg=50)
            Q_vals.append(Q)
            
        curves.append({
            "T_tank": T_tank,
            "label": label,
            "Q": np.array(Q_vals)
        })
        
    return {
        "L": L_vals,
        "curves": curves
    }