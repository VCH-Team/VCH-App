# engine/operators/audit.py
import numpy as np
from numba import njit, prange

@njit(parallel=True, cache=True)
def audit_kernel(m, H, M_initial, H_initial, m_in_cum, m_out_cum, H_in_cum, H_out_cum, E_coil_cum, E_loss_cum):
    """Calculates mass and energy residuals."""
    current_m = 0.0
    current_H = 0.0
    
    for i in prange(m.shape[0]):
        current_m += m[i]
        current_H += H[i]
        
    expected_m = M_initial + m_in_cum - m_out_cum
    expected_H = H_initial + H_in_cum - H_out_cum + E_coil_cum - E_loss_cum

    m_resid = (current_m - expected_m) / max(1e-9, abs(M_initial))
    H_resid = (current_H - expected_H) / max(1e-9, abs(H_initial))

    return m_resid, H_resid, current_m, expected_m