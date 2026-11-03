# physics/tests/test_settle.py
import numpy as np
import pytest
import materials
from physics import grid as grid_module
from physics import state as state_module
from physics import config
from physics.operators import settle, audit

@pytest.fixture
def setup_settle():
    cfg = config.with_defaults({
        "r_inner": 0.5, "tank_height": 1.0, "res": 10,
        "M_fluid": 100.0, "T_start": 25.0, "T_amb_mid": 25.0,
    })
    # ... rest is same
    mat = materials.load(materials.list_available()[0])
    g = grid_module.Grid.build_3d(cfg)
    s = state_module.State(g, mat, cfg)
    return cfg, g, s, mat

def test_settle_conserves_mass_and_energy(setup_settle):
    """Moving mass around should never lose mass or energy."""
    cfg, g, s, mat = setup_settle
    
    # Artificially create a void at the bottom by moving mass to the top
    col = 0
    start = g.col_start[col]
    length = g.col_len[col]
    c_bot = g.col_cells[start]
    c_top = g.col_cells[start + length - 1]
    
    moved_m = s.m[c_bot]
    moved_H = s.H[c_bot]
    
    s.m[c_bot] = 0.0
    s.H[c_bot] = 0.0
    s.m[c_top] += moved_m
    s.H[c_top] += moved_H
    
    s.update_derived(mat)
    s.H_initial = s.total_enthalpy() # reset audit reference
    
    initial_m = s.total_mass()
    initial_H = s.total_enthalpy()
    
    settle.apply(g, s, mat, cfg)
    
    assert np.isclose(initial_m, s.total_mass())
    assert np.isclose(initial_H, s.total_enthalpy())
    
    # The bottom cell should have refilled (mostly)
    assert s.m[c_bot] > 0.0
    
    res = audit.evaluate(s)
    assert abs(res["m_resid"]) < 1e-12
    assert abs(res["H_resid"]) < 1e-12

def test_thermal_expansion_moves_up(setup_settle):
    """If a bottom cell expands (heats up), excess mass should push upward."""
    cfg, g, s, mat = setup_settle
    
    col = 0
    start = g.col_start[col]
    c_bot = g.col_cells[start]
    c_top = g.col_cells[start + 1]
    
    # Heat up the bottom cell significantly
    s.T[c_bot] = 90.0
    s.H[c_bot] = s.m[c_bot] * np.interp(90.0, mat["T_grid"], mat["H_grid"])
    
    s.update_derived(mat)
    s.H_initial = s.total_enthalpy()
    
    m_bot_before = s.m[c_bot]
    m_top_before = s.m[c_top]
    
    settle.apply(g, s, mat, cfg)
    
    # Because it heated up, its density dropped, capacity dropped, so mass pushed UP
    assert s.m[c_bot] < m_bot_before
    assert s.m[c_top] > m_top_before