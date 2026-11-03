# physics/tests/test_heat.py
import numpy as np
import pytest
import materials
from physics import grid as grid_module
from physics import state as state_module
from physics import config
from physics.operators import heat, audit

@pytest.fixture
def setup_heat():
    cfg = config.with_defaults({
        "r_inner": 0.5, "tank_height": 1.0, "res": 10,
        "M_fluid": 10.0, "T_start": 25.0, "T_amb_mid": 25.0,
        "h_air": 0.0, 
        "flow_m3h": 0.0 
    })
    mat = materials.load(materials.list_available()[0])
    g = grid_module.Grid.build_3d(cfg)
    s = state_module.State(g, mat, cfg)
    
    # Manually set a hot spot
    s.T[0] = 100.0
    s.H[0] = s.m[0] * np.interp(100.0, mat["T_grid"], mat["H_grid"])
    
    # AUDIT FIX: resync H_initial so audit sees our modified starting point
    s.H_initial = s.total_enthalpy()
    
    coil_segs = None # <--- No coil for the conduction test
    return cfg, g, s, mat, coil_segs

def test_conduction_conserves_energy(setup_heat):
    cfg, g, s, mat, coil_segs = setup_heat
    initial_H = s.total_enthalpy()
    
    # New signature: heat.apply(grid, state, mat, coil_segs, cfg, dt)
    heat.apply(g, s, mat, coil_segs, cfg, dt=1.0)
    
    final_H = s.total_enthalpy()
    assert np.isclose(initial_H, final_H, rtol=1e-5)
    assert s.T[0] < 100.0

def test_audit_still_passes(setup_heat):
    cfg, g, s, mat, coil_segs = setup_heat
    heat.apply(g, s, mat, coil_segs, cfg, dt=1.0)
    
    res = audit.evaluate(s)
    assert abs(res["m_resid"]) < 1e-12
    assert abs(res["H_resid"]) < 1e-12