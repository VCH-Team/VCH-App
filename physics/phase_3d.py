# physics/phase_3d.py
import numpy as np
from physics import grid as grid_module
from physics import state as state_module
from physics import loop
from physics.operators import coil

def run_simulation(cfg, mat, R_coil, n_turns):
    print(f"Initializing 3D Grid (res={cfg['res']})...")
    grid = grid_module.Grid.build_3d(cfg)
    state = state_module.State(grid, mat, cfg)
    
    # 1. Setup the Coil Segments
    coil_segs = coil.build_coil_segments(grid, cfg, R_coil, n_turns)
    if coil_segs is None:
        raise ValueError("Coil radius is entirely outside the tank!")
        
    # 2. Setup Drain and Fill Indices
    drain_idx = np.argmin(grid.zc) if cfg.get("simulate_drain", False) else -1
    fill_idx = np.argmax(grid.zc) if cfg.get("simulate_fill", False) else -1
    
    # 3. Run the Cycles
    n_cycles = cfg.get("N_cycles", 1)
    for c in range(n_cycles):
        print(f"\n--- CYCLE {c+1}/{n_cycles} ---")
        
        print("Starting Heating Phase...")
        loop.run_chunk(
            grid, state, mat, cfg, coil_segs, drain_idx, fill_idx, 
            cfg["t_window_hr"], is_heating=True
        )
        
        if c < n_cycles - 1 or cfg.get("cool_down_at_end", False):
            print("Starting Cooling Phase...")
            loop.run_chunk(
                grid, state, mat, cfg, coil_segs, drain_idx, fill_idx, 
                cfg["t_cooldown_hr"], is_heating=False
            )
            
    print("\nSimulation Complete.")
    
    return {
        "final_mass": state.total_mass(),
        "total_enthalpy": state.total_enthalpy(),
        "m_out": state.m_out_cum,
        "m_in": state.m_in_cum,
        "E_coil": state.E_coil_cum,
        "E_loss": state.E_loss_cum,
    }
    
    # 4. Return the results dict (matching the contract)
    return {
        "final_mass": state.total_mass(),
        "total_enthalpy": state.total_enthalpy(),
        "m_out": state.m_out_cum,
        "m_in": state.m_in_cum,
        "E_coil": state.E_coil_cum,
        "E_loss": state.E_loss_cum,
    }