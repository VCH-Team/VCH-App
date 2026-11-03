# physics/timestep.py
import numpy as np

def choose(state, T_prev, cfg, dt_current, time_to_next_event):
    """
    Calculates the next dt.
    Returns (dt_next, accept_step).
    """
    # 1. Find the maximum temperature change anywhere in the tank
    dT_max = 0.0
    valid = (state.m > 1e-6) & (T_prev > -900.0) # ignore empty cells
    
    if np.any(valid):
        dT_max = np.max(np.abs(state.T[valid] - T_prev[valid]))
        
    # 2. Check accuracy (if dT > 5.0 C in one step, that's too fast)
    T_tol = 5.0
    accept = True
    
    if dT_max > T_tol * 2.0:
        accept = False # Step is way too big, reject it
        dt_next = dt_current * 0.5
    elif dT_max > T_tol:
        dt_next = dt_current * (T_tol / dT_max) * 0.9
    else:
        # If we barely heated up, try growing the timestep
        dt_next = dt_current * 1.2
        
        # 3. Apply hard limits
    dt_min = cfg.get("dt_min", 0.1)
    dt_max = cfg.get("dt_max", 10.0)
    dt_next = max(dt_min, min(dt_max, dt_next))
    
    # 4. Event limit
    dt_next = min(dt_next, time_to_next_event)
    
    # 5. Safety Brake: Never allow dt to be 0 or negative
    if dt_next <= 1e-6:
        dt_next = dt_min
        
    return dt_next, accept