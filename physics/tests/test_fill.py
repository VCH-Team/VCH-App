# physics/tests/test_fill.py
import numpy as np
import pytest
import materials
from physics import grid as grid_module
from physics import state as state_module
from physics import config
from physics.operators import fill, audit

@pytest.fixture
def setup_fill():
    cfg = config.with_defaults({
        "r_inner": 0.5, "tank_height": 1.0, "res": 10,
        "M_fluid": 50.0, "T_start": 20.0, "T_amb_mid": 20.0,
    })
    mat = materials.load(materials.list_available()[0])
    g = grid_module.Grid.build_3d(cfg)
    s = state_module.State(g, mat, cfg)
    
    # Pick the absolute top cell as the fill inlet
    fill_idx = np.argmax(g.zc)
    
    return cfg, g, s, mat, fill_idx

def test_fill_adds_mass(setup_fill):
    """Filling should increase total mass and update accumulators."""
    cfg, g, s, mat, fill_idx = setup_fill
    
    initial_m = s.total_mass()
    
    # Simulate 5 seconds of filling at 2 kg/s with 80C fluid
    fill.apply(g, s, mat, cfg, dt=5.0, fill_cell_idx=fill_idx, m_dot=2.0, T_fill=80.0)
    
    final_m = s.total_mass()
    
    # Mass should go up by exactly 10 kg (2 kg/s * 5s)
    assert np.isclose(final_m - initial_m, 10.0)
    assert np.isclose(s.m_in_cum, 10.0)
    
    # The fill cell should now be hotter
    assert s.T[fill_idx] > 20.0
    
    # Audit should still perfectly balance
    res = audit.evaluate(s)
    assert abs(res["m_resid"]) < 1e-12
    assert abs(res["H_resid"]) < 1e-12

def test_fill_specific_enthalpy(setup_fill):
    """The added enthalpy should match the incoming fluid's temperature."""
    cfg, g, s, mat, fill_idx = setup_fill
    
    T_fill = 80.0
    h_fill = np.interp(T_fill, mat["T_grid"], mat["H_grid"])
    
    fill.apply(g, s, mat, cfg, dt=2.0, fill_cell_idx=fill_idx, m_dot=1.0, T_fill=T_fill)
    
    # Added enthalpy should be dm * h_fill
    assert np.isclose(s.H_in_cum, 2.0 * h_fill)