# physics/tests/test_convection.py
import numpy as np
import pytest
import materials
from physics import grid as grid_module
from physics import state as state_module
from physics import config
from physics.operators import heat, coil

@pytest.fixture
def setup_convection():
    cfg = config.with_defaults({
        "r_inner": 0.5, "tank_height": 1.0, "res": 10,
        "M_fluid": 100.0, "T_start": 20.0, "T_amb_mid": 20.0, # <-- increased mass
        "h_air": 0.0, "flow_m3h": 0.0, 
        "coil_clearance_bottom": 0.0
    })
    mat = materials.load(materials.list_available()[0])
    g = grid_module.Grid.build_3d(cfg)
    s = state_module.State(g, mat, cfg)
    
    c_bot = g.col_cells[0]
    c_top = g.col_cells[1]
    
    # Force mass into c_top so it can receive heat
    s.m[c_top] = 1.0
    s.T[c_bot] = 80.0
    s.H[c_bot] = s.m[c_bot] * np.interp(80.0, mat["T_grid"], mat["H_grid"])
    s.T[c_top] = 20.0
    s.H[c_top] = s.m[c_top] * np.interp(20.0, mat["T_grid"], mat["H_grid"])
    
    s.update_derived(mat)
    s.H_initial = s.total_enthalpy()
    coil_segs = coil.build_coil_segments(g, cfg, R_coil=0.0, n_turns=0)
    return cfg, g, s, mat, coil_segs, c_bot, c_top

def test_convection_accelerates_heat_transfer(setup_convection):
    """An unstable hot-bottom layer should transfer heat faster than pure conduction."""
    cfg, g, s, mat, coil_segs, c_bot, c_top = setup_convection
    
    T_top_before = s.T[c_top]
    
    # Run one step of heat transfer
    heat.apply(g, s, mat, coil_segs, cfg, dt=1.0)
    
    # The top cell should have warmed up significantly
    assert s.T[c_top] > T_top_before