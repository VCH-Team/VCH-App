# physics/operators/fill.py
import numpy as np

def apply(grid, state, mat, cfg, dt, fill_cell_idx, m_dot, T_fill):
    """
    Adds mass and enthalpy to the fill cell.
    m_dot is in kg/s. T_fill is the temperature of the incoming fluid.
    """
    if m_dot <= 0.0 or fill_cell_idx < 0:
        return
        
    # Get properties of the incoming fluid
    rho_fill = np.interp(T_fill, mat["T_grid"], mat["rho_grid"])
    h_fill = np.interp(T_fill, mat["T_grid"], mat["H_grid"])
    
    # Calculate mass to add this step
    dm = m_dot * dt
    
    if dm > 0.0:
        # Add mass and enthalpy to the cell
        state.m[fill_cell_idx] += dm
        state.H[fill_cell_idx] += dm * h_fill
        
        # Track cumulative gains
        state.m_in_cum += dm
        state.H_in_cum += dm * h_fill
        
        # Update properties for the filled cell
        state.update_derived(mat)