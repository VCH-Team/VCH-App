# physics/closures.py

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