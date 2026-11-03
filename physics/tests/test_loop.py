# physics/tests/test_loop.py
import numpy as np
import pytest
import materials
from physics import grid as grid_module
from physics import state as state_module
from physics import config
from physics import loop
from physics.operators import audit

@pytest.fixture
def setup_loop():
    cfg = config.with_defaults({
        "r_inner": 0.5, "tank_height": 1.0, "res": 10,
        "M_fluid": 50.0, "T_start": 25.0, "T_amb_mid": 25.0,
        "T_water_in": 80.0, "flow_m3h": 1.0,
        "dt_sec": 1.0,
        "simulate_fill": False, "simulate_drain": False,
        "coil_clearance_bottom": 0.0, # <--- ADD THIS LINE
        "T_water_arr": np.linspace(0, 100, 10),
        "rho_water_arr": np.full(10, 1000.0),
        "cp_water_arr": np.full(10, 4180.0),
        "mu_water_arr": np.full(10, 0.001),
        "k_water_arr": np.full(10, 0.6),
        "T_tube_arr": np.linspace(0, 100, 10),
        "k_tube_arr": np.full(10, 16.0),
    })

    mat = materials.load(materials.list_available()[0])
    g = grid_module.Grid.build_3d(cfg)
    s = state_module.State(g, mat, cfg)
    
    # Fake a coil at the bottom of the tank where the fluid actually is
    coil_w = np.zeros(g.N)
    lowest_cell = np.argmin(g.zc)
    from physics.operators import coil # add at top
    coil_segs = coil.build_coil_segments(g, cfg, R_coil=0.4, n_turns=2)
    return cfg, g, s, mat, coil_segs

def test_loop_runs_without_crashing(setup_loop):
    """Run 1 minute of simulation. It should complete and conserve mass."""
    cfg, g, s, mat, coil_segs = setup_loop
    
    initial_m = s.total_mass()
    s.H_initial = s.total_enthalpy()
    
    # Run just 0.016 hours (~1 minute) to test
    # Pass a realistic coil radius and turns so heat is actually transferred
    loop.run_chunk(g, s, mat, cfg, coil_segs, -1, -1, t_window_hr=0.016)
    
    # Mass shouldn't have changed since drain/fill are off
    assert np.isclose(s.total_mass(), initial_m)
    
    # Audit should be happy
    res = audit.evaluate(s)
    assert abs(res["m_resid"]) < 1e-12
    assert abs(res["H_resid"]) < 1e-12
    
    # The tank should have warmed up slightly from the coil
    assert s.total_enthalpy() > s.H_initial