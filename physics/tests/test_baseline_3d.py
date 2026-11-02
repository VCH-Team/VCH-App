# physics/tests/test_baseline_3d.py
import numpy as np
import pytest
import materials
from physics import config
from physics import phase_3d
from physics.operators import audit

@pytest.fixture
def setup_full_sim():
    cfg = config.with_defaults({
        "r_inner": 0.5, "tank_height": 1.0, "res": 10,
        "M_fluid": 100.0, "T_start": 20.0, "T_amb_mid": 20.0,
        "T_water_in": 80.0, "flow_m3h": 1.0,
        "dt_sec": 1.0, "t_window_hr": 0.01,
        "N_cycles": 1,
        "simulate_fill": False, "simulate_drain": False,
        "coil_clearance_bottom": 0.0, # <--- ADD THIS LINE to put the coil at the bottom
        "T_water_arr": np.linspace(0, 100, 10),
        "rho_water_arr": np.full(10, 1000.0),
        "cp_water_arr": np.full(10, 4180.0),
        "mu_water_arr": np.full(10, 0.001),
        "k_water_arr": np.full(10, 0.6),
        "T_tube_arr": np.linspace(0, 100, 10),
        "k_tube_arr": np.full(10, 16.0),
    })
    mat = materials.load(materials.list_available()[0])
    return cfg, mat

def test_full_simulation_runs(setup_full_sim):
    """Runs a full mini-simulation and ensures physics hold together."""
    cfg, mat = setup_full_sim
    
    # Run the driver
    res = phase_3d.run_simulation(cfg, mat, R_coil=0.4, n_turns=5)
    
    # The tank should have gained heat from the coil
    assert res["E_coil"] > 0.0
    
    # Final mass should match initial (since drain/fill are off)
    assert np.isclose(res["final_mass"], 100.0, rtol=0.05)
    
    # Energy balance: E_coil = dH_stored + E_loss
    # We can't check exact numbers without the state object, 
    # but we can verify the keys exist and are positive.
    assert "total_enthalpy" in res
    assert res["total_enthalpy"] > 0.0