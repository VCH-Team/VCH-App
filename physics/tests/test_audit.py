# physics/tests/test_audit.py
import numpy as np
import pytest
import materials
from physics import grid as grid_module
from physics import state as state_module
from physics import config
from physics.operators import audit

@pytest.fixture
def setup_state():
    cfg = config.with_defaults({
        "r_inner": 0.5, "tank_height": 1.0, "res": 10,
        "M_fluid": 30.0, "T_start": 25.0,
    })
    mat = materials.load(materials.list_available()[0])
    g = grid_module.Grid.build_3d(cfg)
    s = state_module.State(g, mat, cfg)
    return s

def test_audit_clean(setup_state):
    """A fresh state with no changes should have zero residual."""
    s = setup_state
    res = audit.evaluate(s)
    assert abs(res["m_resid"]) < 1e-12
    assert abs(res["H_resid"]) < 1e-12

def test_audit_accurate_flow(setup_state):
    """If we add mass and record it in the accumulator, the audit should pass."""
    s = setup_state
    added_m = 5.0
    added_H = 5.0 * 100000.0 # arbitrary enthalpy
    
    s.m[0] += added_m
    s.H[0] += added_H
    s.m_in_cum += added_m
    s.H_in_cum += added_H
    
    res = audit.evaluate(s)
    assert abs(res["m_resid"]) < 1e-12
    assert abs(res["H_resid"]) < 1e-12

def test_audit_catches_leak(setup_state):
    """If we accidentally lose mass without recording it, the audit should scream."""
    s = setup_state
    
    # Accidentally delete mass from cell 0 without recording it
    s.m[0] -= 2.0 
    
    res = audit.evaluate(s)
    # The mass residual should now be negative and noticeable
    assert res["m_resid"] < -1e-6