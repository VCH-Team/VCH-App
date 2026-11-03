# physics/tests/test_flatten.py
import numpy as np
import pytest
import materials
from physics import grid as grid_module
from physics import state as state_module
from physics import config
from physics.operators import flatten, audit

@pytest.fixture
def setup_flatten():
    cfg = config.with_defaults({
        "r_inner": 0.5, "tank_height": 1.0, "res": 10,
        "M_fluid": 50.0, "T_start": 25.0, "T_amb_mid": 25.0,
        "dt_sec": 1.0,  # <-- Need this now
    })
    mat = materials.load(materials.list_available()[0])
    g = grid_module.Grid.build_3d(cfg)
    s = state_module.State(g, mat, cfg)
    
    # Reset audit baseline
    s.H_initial = s.total_enthalpy()
    
    return cfg, g, s, mat

def test_flatten_conserves_mass(setup_flatten):
    """Moving mass sideways should never lose mass or energy."""
    cfg, g, s, mat = setup_flatten
    
    initial_m = s.total_mass()
    initial_H = s.total_enthalpy()
    
    flatten.apply(g, s, mat, cfg)
    
    assert np.isclose(initial_m, s.total_mass())
    assert np.isclose(initial_H, s.total_enthalpy())
    
    res = audit.evaluate(s)
    assert abs(res["m_resid"]) < 1e-12
    assert abs(res["H_resid"]) < 1e-12

def test_flatten_flows_downhill(setup_flatten):
    """Mass should flow from a high column to an adjacent low column."""
    cfg, g, s, mat = setup_flatten
    
    # Find two adjacent cells in the X direction
    c1 = 0
    c2 = g.nbr[c1, 1] # +x neighbor
    assert c2 >= 0
    
    # Take all mass from c2 and put it in c1 (making c1's column much higher)
    moved_m = s.m[c2]
    moved_H = s.H[c2]
    s.m[c1] += moved_m
    s.H[c1] += moved_H
    s.m[c2] = 0.0
    s.H[c2] = 0.0
    
    s.update_derived(mat)
    s.H_initial = s.total_enthalpy()
    
    m1_before = s.m[c1]
    m2_before = s.m[c2] # This is 0.0
    
    # Run flatten
    flatten.apply(g, s, mat, cfg)
    
    # Mass should have moved from c1 to c2
    assert s.m[c1] < m1_before
    assert s.m[c2] > m2_before