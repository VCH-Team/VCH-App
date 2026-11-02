# physics/tests/test_drain.py
import numpy as np
import pytest
import materials
from physics import grid as grid_module
from physics import state as state_module
from physics import config
from physics.operators import drain, audit

@pytest.fixture
def setup_drain():
    cfg = config.with_defaults({
        "r_inner": 0.5, "tank_height": 1.0, "res": 10,
        "M_fluid": 100.0, "T_start": 25.0, "T_amb_mid": 25.0,
        "thresh_liq": 0.2, "thresh_visc": 5.0
    })
    
    # Load any material, then FORCE a melt band so this test always works
    mat_names = materials.list_available()
    mat = materials.load(mat_names[0])
    mat["T_ms"] = 10.0
    mat["T_me"] = 20.0

    g = grid_module.Grid.build_3d(cfg)
    s = state_module.State(g, mat, cfg)
    
    drain_idx = np.argmin(g.zc)
    return cfg, g, s, mat, drain_idx

def test_drain_removes_mass(setup_drain):
    """Draining should reduce total mass and update accumulators."""
    cfg, g, s, mat, drain_idx = setup_drain
    
    initial_m = s.total_mass()
    
    # Simulate 10 seconds of draining
    drain_area = 0.01 # m^2
    drain.apply(g, s, mat, cfg, dt=10.0, drain_cell_idx=drain_idx, drain_area=drain_area)
    
    final_m = s.total_mass()
    
    # Mass should drop
    assert final_m < initial_m
    assert s.m_out_cum > 0.0
    
    # Audit should still perfectly balance
    res = audit.evaluate(s)
    assert abs(res["m_resid"]) < 1e-12
    assert abs(res["H_resid"]) < 1e-12

def test_drain_flowable_check(setup_drain):
    """If the material is frozen solid, nothing should drain."""
    cfg, g, s, mat, drain_idx = setup_drain
    
    # Force the drain cell to be frozen by making it 100% solid fraction
    s.fs[drain_idx] = 1.0
    # Also set T to solidus if available
    if not np.isnan(mat["T_ms"]):
        s.T[drain_idx] = mat["T_ms"] - 10.0
        s.H[drain_idx] = s.m[drain_idx] * np.interp(mat["T_ms"] - 10.0, mat["T_grid"], mat["H_grid"])

    initial_m = s.total_mass()
    
    drain.apply(g, s, mat, cfg, dt=10.0, drain_cell_idx=drain_idx, drain_area=0.01)
    
    # Mass should NOT drop
    assert np.isclose(s.total_mass(), initial_m)
    assert s.m_out_cum == 0.0