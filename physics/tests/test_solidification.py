# physics/tests/test_solidification.py
import numpy as np
import pytest
import materials
from physics import grid as grid_module
from physics import state as state_module
from physics import config
from physics.operators import settle

@pytest.fixture
def setup_solidification():
    cfg = config.with_defaults({
        "r_inner": 0.5, "tank_height": 1.0, "res": 10,
        "M_fluid": 100.0, "T_start": 25.0, "T_amb_mid": 25.0,
        "fs_lock": 0.8
    })
    mat = materials.load(materials.list_available()[0])
    # Force a melt band
    mat["T_ms"] = 10.0
    mat["T_me"] = 20.0
    
    g = grid_module.Grid.build_3d(cfg)
    s = state_module.State(g, mat, cfg)
    
    c_bot = g.col_cells[0]
    c_top = g.col_cells[1]
    
    # Freeze the bottom cell completely
    s.fs[c_bot] = 1.0
    
    # Put some mass in the top cell
    s.m[c_top] = 1.0
    s.H[c_top] = s.m[c_top] * np.interp(25.0, mat["T_grid"], mat["H_grid"])
    
    return cfg, g, s, mat, c_bot, c_top

def test_frozen_cell_blocks_falling(setup_solidification):
    """Mass on top of a frozen cell should not fall through it."""
    cfg, g, s, mat, c_bot, c_top = setup_solidification
    
    m_bot_before = s.m[c_bot]
    m_top_before = s.m[c_top]
    
    settle.apply(g, s, mat, cfg)
    
    # Top mass should not have fallen into the frozen bottom cell
    assert s.m[c_top] == m_top_before
    assert s.m[c_bot] == m_bot_before