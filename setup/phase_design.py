# setup/phase_design.py
import numpy as np
from engine import closures
from setup.payload import NumbaMaterial

def _march_coil(T_tank, T_coil_in, m_dot, L_total, R_coil, d_in, d_out, R_f_out, mat, cfg, n_seg=50):
    T_tank = float(T_tank)
    T_coil_in = float(T_coil_in)
    m_dot = float(m_dot)
    L_total = float(L_total)
    
    if L_total <= 0:
        return 0.0
        
    dL = L_total / n_seg
    A_seg = np.pi * d_out * dL
    T_coil = T_coil_in
    Q_total = 0.0
    
    H_tank = np.interp(T_tank, mat["T_grid"], mat["H_grid"])
    T_ms = mat.get("T_ms", np.nan)
    T_me = mat.get("T_me", np.nan)
    has_melt = not (np.isnan(T_ms) or np.isnan(T_me))
    
    H_solid = float(np.interp(T_ms, mat["T_grid"], mat["H_grid"])) if has_melt else 0.0
    H_liquid = float(np.interp(T_me, mat["T_grid"], mat["H_grid"])) if has_melt else 0.0
    
    nm = NumbaMaterial(
        T_grid=mat["T_grid"], H_grid=mat["H_grid"], rho_grid=mat["rho_grid"],
        k_grid=mat["k_grid"], mu_grid=mat["mu_grid"], cp_eff_grid=mat["cp_eff_grid"],
        cp_sens_grid=mat["cp_sens_grid"], T_ms=T_ms, T_me=T_me,
        H_solid=H_solid, H_liquid=H_liquid, has_melt=has_melt
    )
    
    for _ in range(n_seg):
        if T_coil <= T_tank + 1e-3:
            break
            
        dT = max(0.1, T_coil - T_tank)
        h_out = closures.h_external(T_tank, H_tank, nm, cfg["thresh_liq"], cfg["thresh_visc"], cfg["beta_liq"], dT, d_out)
        
        rho_c  = np.interp(T_coil, cfg["T_water_arr"], cfg["rho_water_arr"])
        cp_c   = np.interp(T_coil, cfg["T_water_arr"], cfg["cp_water_arr"])
        mu_c   = np.interp(T_coil, cfg["T_water_arr"], cfg["mu_water_arr"])
        k_c    = np.interp(T_coil, cfg["T_water_arr"], cfg["k_water_arr"])
        k_tube = np.interp(T_coil, cfg["T_tube_arr"],  cfg["k_tube_arr"])
        
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
        
    return float(Q_total)

def compute_ntu_curves(cfg, mat, R_coil, n_max, n_pts=50):
    m_dot = cfg["flow_m3h"] * np.interp(cfg["T_water_in"], cfg["T_water_arr"], cfg["rho_water_arr"]) / 3600.0
    T_coil_in = cfg["T_water_in"]
    d_in = cfg["d_in"]
    d_out = cfg["d_out"]
    R_f_out = cfg["R_f_out"]
    
    L_max = 2.0 * np.pi * R_coil * n_max
    L_vals = np.linspace(0, L_max, n_pts)
    
    T_amb_low = cfg["T_amb_low"]
    T_ms = float(mat.get("T_ms", np.nan))
    T_me = float(mat.get("T_me", np.nan))
    T_target = cfg.get("T_target", T_coil_in - 5.0)
    
    if np.isnan(T_ms) or np.isnan(T_me):
        bands = [(T_amb_low, "Coldest (Start)"), (T_target, "Hottest (Target)")]
    else:
        bands = [
            (T_amb_low, "Solid (Low)"), (T_ms, "Solid (High)"),
            (T_ms, "Slurry (Low)"), (T_me, "Slurry (High)"),
            (T_me, "Liquid (Low)"), (T_target, "Liquid (High)")
        ]
        
    curves = []
    for T_tank, label in bands:
        Q_vals = []
        for L in L_vals:
            Q = _march_coil(T_tank, T_coil_in, m_dot, L, R_coil, d_in, d_out, R_f_out, mat, cfg, n_seg=50)
            Q_vals.append(Q)
        curves.append({"T_tank": T_tank, "label": label, "Q": np.array(Q_vals)})
        
    return {"L": L_vals, "curves": curves}