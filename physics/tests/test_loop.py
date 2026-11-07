# physics/tests/test_loop.py
import numpy as np
import pytest
import materials
import time
import tempfile
import threading
from physics import grid as grid_module
from physics import state as state_module
from physics import config
from physics import loop
from physics.operators import audit, coil

@pytest.fixture
def setup_loop():
    cfg = config.with_defaults({
        "r_inner": 0.5, "tank_height": 1.0, "res": 20,
        "M_fluid": 100.0, "T_start": 25.0, "T_amb_mid": 25.0,
        "T_water_in": 80.0, "flow_m3h": 1.0,
        "dt_sec": 1.0,
        "simulate_fill": False, "simulate_drain": False,
        "coil_clearance_bottom": 0.0, 
        "T_water_arr": np.linspace(0, 100, 10),
        "rho_water_arr": np.full(10, 1000.0),
        "cp_water_arr": np.full(10, 4180.0),
        "mu_water_arr": np.full(10, 0.001),
        "k_water_arr": np.full(10, 0.6),
        "T_tube_arr": np.linspace(0, 100, 10),
        "k_tube_arr": np.full(10, 16.0),
        "T_wall_arr": np.linspace(0, 100, 10),  # <--- ADDED
        "k_wall_arr": np.full(10, 16.0),        # <--- ADDED
        "rho_wall_arr": np.full(10, 8000.0),    # <--- ADDED
        "cp_wall_arr": np.full(10, 500.0),      # <--- ADDED
        "snapshot_interval_hr": 0.1,
    })

    mat = materials.load(materials.list_available()[0])
    g = grid_module.Grid.build_3d(cfg)
    s = state_module.State(g, mat, cfg)
    
    coil_segs = coil.build_coil_segments(g, cfg, R_coil=0.4, n_turns=2)
    return cfg, g, s, mat, coil_segs

def test_loop_runs_without_crashing(setup_loop):
    cfg, g, s, mat, coil_segs = setup_loop
    initial_m = s.total_mass()
    s.H_initial = s.total_enthalpy()
    
    with tempfile.TemporaryDirectory() as tmpdir:
        snaps, status = loop.run_chunk(
            g, s, mat, cfg, coil_segs, -1, -1, 
            t_window_hr=1.0, 
            outdir=tmpdir, 
            t_start_hr=0.0
        )
    
    assert np.isclose(s.total_mass(), initial_m)
    res = audit.evaluate(s)
    assert abs(res["m_resid"]) < 1e-12
    assert abs(res["H_resid"]) < 1e-12
    assert s.total_enthalpy() > s.H_initial

def test_loop_cancels(setup_loop):
    cfg, g, s, mat, coil_segs = setup_loop
    cancel_flag = threading.Event()
    cancel_flag.set()
    
    with tempfile.TemporaryDirectory() as tmpdir:
        snaps, status = loop.run_chunk(
            g, s, mat, cfg, coil_segs, -1, -1,
            t_window_hr=1.0,
            outdir=tmpdir,
            t_start_hr=0.0,
            cancel_flag=cancel_flag
        )
    assert len(status) == 0