# physics/tests/test_baseline_3d.py
import numpy as np
import pytest
import materials
import os
import tempfile
from physics import config
from physics import phase_3d

@pytest.fixture
def setup_full_sim():
    cfg = config.with_defaults({
        "r_inner": 0.5, "tank_height": 1.0, "res": 10,
        "M_fluid": 100.0, "T_start": 20.0, "T_amb_mid": 20.0,
        "T_water_in": 80.0, "flow_m3h": 1.0,
        "dt_sec": 1.0, "t_window_hr": 0.02,
        "N_cycles": 1,
        "simulate_fill": False, "simulate_drain": False,
        "coil_clearance_bottom": 0.0,
        "snapshot_interval_hr": 0.01,
        "T_water_arr": np.linspace(0, 100, 10),
        "rho_water_arr": np.full(10, 1000.0),
        "cp_water_arr": np.full(10, 4180.0),
        "mu_water_arr": np.full(10, 0.001),
        "k_water_arr": np.full(10, 0.6),
        "T_tube_arr": np.linspace(0, 100, 10),
        "k_tube_arr": np.full(10, 16.0),
        "T_wall_arr": np.linspace(0, 100, 10), # <--- ADDED
        "k_wall_arr": np.full(10, 16.0),       # <--- ADDED
        "rho_wall_arr": np.full(10, 8000.0),   # <--- ADDED
        "cp_wall_arr": np.full(10, 500.0),     # <--- ADDED
    })
    mat = materials.load(materials.list_available()[0])
    return cfg, mat

def test_full_simulation_runs(setup_full_sim):
    cfg, mat = setup_full_sim
    
    with tempfile.TemporaryDirectory() as tmpdir:
        res = phase_3d.run_simulation(cfg, mat, R_coil=0.4, n_turns=5, outdir=tmpdir)
        
        assert "cycle_metrics" in res
        assert len(res["cycle_metrics"]) == 1
        assert len(res["snapshots"]) > 0
        
        snap_dir = os.path.join(tmpdir, "snapshots")
        assert os.path.exists(snap_dir)
        files = os.listdir(snap_dir)
        assert len(files) > 0
        assert files[0].endswith(".npz")