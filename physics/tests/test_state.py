# physics/tests/test_state.py
import numpy as np
import pytest
import materials
from physics import grid as grid_module
from physics import state as state_module
from physics import config

@pytest.fixture
def setup_state():
    cfg = config.with_defaults({
        "r_inner": 0.5,
        "tank_height": 1.0,
        "res": 10,
        "M_fluid": 30.0,
        "T_start": 25.0,
    })
    mat = materials.load(materials.list_available()[0])
    g = grid_module.Grid.build_3d(cfg)
    s = state_module.State(g, mat, cfg)
    return cfg, g, s, mat

def test_initial_mass(setup_state):
    """The tank should fill to the requested mass."""
    cfg, g, s, mat = setup_state
    # Because of grid discretization, it might be a tiny bit off, but it should be close
    assert np.isclose(s.total_mass(), 30.0, rtol=0.05)
    
def test_initial_temperature(setup_state):
    """The initial enthalpy should map back to T_start."""
    cfg, g, s, mat = setup_state
    # Check that cells with mass have the correct temperature
    non_empty = s.m > state_module.M_EPS
    np.testing.assert_allclose(s.T[non_empty], 25.0, atol=0.1)

def test_derived_arrays_shape(setup_state):
    """Ensure all arrays are allocated and finite."""
    cfg, g, s, mat = setup_state
    s.check() # Our custom method to check for NaNs or negative mass
    
    assert len(s.T) == g.N
    assert len(s.rho) == g.N
    assert len(s.cap) == g.N
    assert len(s.fill) == g.N

def test_state_copy(setup_state):
    """Ensure .copy() creates a true deep copy (important for step rejection)."""
    cfg, g, s, mat = setup_state
    s2 = s.copy()
    
    # Change original
    s.m[0] += 100.0
    s.T[0] = 999.9
    
    # Check copy is unaffected
    assert s2.m[0] != s.m[0]
    assert s2.T[0] != s.T[0]