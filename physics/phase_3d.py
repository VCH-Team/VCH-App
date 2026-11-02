# physics/phase_3d.py
import numpy as np
from physics import grid as grid_module
from physics import state as state_module
from physics import loop

def build_coil_weights(grid, cfg, R_coil):
    """
    Maps the chosen coil radius to the actual 3D cells it passes through.
    Returns an array of weights (summing to 1.0) for all cells.
    """
    coil_w = np.zeros(grid.N)
    
    r_lo = R_coil - cfg["d_out"] / 2.0
    r_hi = R_coil + cfg["d_out"] / 2.0
    z_lo = cfg["coil_clearance_bottom"]
    z_hi = cfg["coil_clearance_bottom"] + cfg["L_avail"]
    
    total_w = 0.0
    for c in range(grid.N):
        r = np.sqrt(grid.xc[c]**2 + grid.yc[c]**2)
        z = grid.zc[c]
        
        # Check if cell center is inside the coil band
        if r_lo <= r <= r_hi and z_lo <= z <= z_hi:
            coil_w[c] = 1.0
            total_w += 1.0
            
    if total_w > 0.0:
        coil_w /= total_w
        
    return coil_w

def run_simulation(cfg, mat, R_coil, n_turns):
    """
    Runs the full multi-cycle 3D simulation.
    """
    print(f"Initializing 3D Grid (res={cfg['res']})...")
    grid = grid_module.Grid.build_3d(cfg)
    state = state_module.State(grid, mat, cfg)
    
    # 1. Setup the Coil
    coil_w = build_coil_weights(grid, cfg, R_coil)
    if np.sum(coil_w) == 0:
        raise ValueError("Coil radius is entirely outside the tank!")
        
    # 2. Setup Drain and Fill Indices
    # For simplicity in Phase 3, we just use the absolute bottom and top cells.
    # Later, we will map (r, theta, z) from the UI to the exact cell index.
    drain_idx = np.argmin(grid.zc) if cfg.get("simulate_drain", False) else -1
    fill_idx = np.argmax(grid.zc) if cfg.get("simulate_fill", False) else -1
    
    # 3. Run the Cycles
    n_cycles = cfg.get("N_cycles", 1)
    for c in range(n_cycles):
        print(f"\n--- CYCLE {c+1}/{n_cycles} ---")
        
        # Heating Phase
        print("Starting Heating Phase...")
        loop.run_chunk(
            grid, state, mat, cfg, coil_w, drain_idx, fill_idx, 
            R_coil, n_turns, cfg["t_window_hr"], is_heating=True
        )
        
        # Cooling Phase (skip on the last cycle if we don't want to cool down at the end)
        if c < n_cycles - 1 or cfg.get("cool_down_at_end", False):
            print("Starting Cooling Phase...")
            loop.run_chunk(
                grid, state, mat, cfg, coil_w, drain_idx, fill_idx, 
                R_coil, n_turns, cfg["t_cooldown_hr"], is_heating=False
            )
            
    print("\nSimulation Complete.")
    
    # 4. Return the results dict (matching the contract)
    return {
        "final_mass": state.total_mass(),
        "total_enthalpy": state.total_enthalpy(),
        "m_out": state.m_out_cum,
        "m_in": state.m_in_cum,
        "E_coil": state.E_coil_cum,
        "E_loss": state.E_loss_cum,
    }