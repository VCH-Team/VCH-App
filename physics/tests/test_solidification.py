# physics/tests/test_solidification.py
import numpy as np
import pytest
import materials
from physics import grid as grid_module
from physics import state as state_module
from physics import config
from physics.operators import settle, drain

@pytest.fixture
def setup_solid():
    cfg = config.with_defaults({
        "r_inner": 0.5, "tank_height": 1.0, "res": 10,
        "M_fluid": 100.0, "T_start": 25.0, "T_amb_mid": 25.0,
        "fs_lock": 0.8, "thresh_visc": 5.0
    })
    mat = materials.load(materials.list_available()[0])
    mat["T_ms"] = 10.0
    mat["T_me"] = 20.0
    
    g = grid_module.Grid.build_3d(cfg)
    s = state_module.State(g, mat, cfg)
    
    c_bot = g.col_cells[0]
    s.fs[c_bot] = 0.9
    s.T[c_bot] = 0.0 
    s.H[c_bot] = s.m[c_bot] * np.interp(0.0, mat["T_grid"], mat["H_grid"])
    
    c_top = g.col_cells[1]
    s.m[c_top] = 0.5 # <--- Reduced from 5.0 to 0.5 so it fits in one cell
    s.T[c_top] = 30.0
    s.H[c_top] = s.m[c_top] * np.interp(30.0, mat["T_grid"], mat["H_grid"])
    
    s.update_derived(mat)
    s.fs[c_bot] = 0.9 
    
    return cfg, g, s, mat, c_bot, c_top

def test_solid_cell_blocks_settle(setup_solid):
    cfg, g, s, mat, c_bot, c_top = setup_solid
    
    m_bot_before = s.m[c_bot]
    m_top_before = s.m[c_top]
    
    settle.apply(g, s, mat, cfg)
    
    assert np.isclose(s.m[c_bot], m_bot_before)
    assert np.isclose(s.m[c_top], m_top_before)

def test_solid_cell_blocks_drain(setup_solid):
    cfg, g, s, mat, c_bot, c_top = setup_solid
    
    m_bot_before = s.m[c_bot]
    
    drain.apply(g, s, mat, cfg, dt=10.0, drain_cell_idx=c_bot, drain_area=0.01)
    
    assert np.isclose(s.m[c_bot], m_bot_before)