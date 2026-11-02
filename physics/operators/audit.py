# physics/operators/audit.py

def evaluate(state):
    """
    Checks mass and energy conservation.
    Returns the relative residual (should be very close to 0).
    """
    # Current totals in the tank
    current_m = state.total_mass()
    current_H = state.total_enthalpy()

    # Expected totals based on what has entered/left
    expected_m = state.M_initial + state.m_in_cum - state.m_out_cum
    expected_H = state.H_initial + state.H_in_cum - state.H_out_cum + state.E_coil_cum - state.E_loss_cum

    # Calculate relative residuals (avoid division by zero)
    m_resid = (current_m - expected_m) / max(1e-9, abs(state.M_initial))
    H_resid = (current_H - expected_H) / max(1e-9, abs(state.H_initial))

    return {
        "m_resid": float(m_resid),
        "H_resid": float(H_resid),
        "current_m": current_m,
        "expected_m": expected_m
    }