# physics/tests/test_phase_design.py
import numpy as np
import pytest
import materials
from physics import phase_design
from physics import config

@pytest.fixture
def setup_design():
    cfg = config.with_defaults({
        "T_water_in": 70.0,
        "T_amb_low": 5.0,
        "T_target": 50.0,
        "flow_m3h": 1.0,
        "r_inner": 1.0,
    })
    # Load the first available material
    mat = materials.load(materials.list_available()[0])
    
    # Test parameters
    R_coil = 0.8
    n_max = 20
    return cfg, mat, R_coil, n_max

def test_saturation(setup_design):
    """Heat transfer must increase with length, but eventually flatten out."""
    cfg, mat, R_coil, n_max = setup_design
    res = phase_design.compute_ntu_curves(cfg, mat, R_coil, n_max, n_pts=10)
    
    for curve in res["curves"]:
        Q = curve["Q"]
        # 1. It should be strictly increasing (more length = more heat)
        assert np.all(np.diff(Q) > 0)
        
        # 2. It should be concave down (flattening out as it approaches T_coil_in)
        # The second derivative should be negative or close to zero
        dQ = np.diff(Q)
        ddQ = np.diff(dQ)
        assert np.all(ddQ <= 1e-3) # Allow tiny numerical noise

def test_colder_tank_transfers_more_heat(setup_design):
    """A colder tank should have a higher Q than a hotter tank."""
    cfg, mat, R_coil, n_max = setup_design
    res = phase_design.compute_ntu_curves(cfg, mat, R_coil, n_max, n_pts=10)
    
    # If it has phase change (6 curves), curve 0 is coldest, curve 5 is hottest.
    # If no phase change (2 curves), curve 0 is coldest, curve 1 is hottest.
    Q_cold = res["curves"][0]["Q"][-1] # Q at max length for coldest tank
    Q_hot = res["curves"][-1]["Q"][-1] # Q at max length for hottest tank
    
    assert Q_cold > Q_hot

def test_zero_length(setup_design):
    """A coil of length 0 should transfer 0 heat."""
    cfg, mat, R_coil, n_max = setup_design
    res = phase_design.compute_ntu_curves(cfg, mat, R_coil, n_max, n_pts=10)
    
    for curve in res["curves"]:
        assert curve["Q"][0] == 0.0

def test_tank_hotter_than_coil(setup_design):
    """If the tank is hotter than the coil inlet, Q should be 0 (no heating)."""
    cfg, mat, R_coil, n_max = setup_design
    cfg["T_amb_low"] = 90.0 # Hotter than T_water_in (70)
    
    res = phase_design.compute_ntu_curves(cfg, mat, R_coil, n_max, n_pts=10)
    
    # The first curve (T_tank = 90) should be all zeros
    assert np.all(res["curves"][0]["Q"] == 0.0)