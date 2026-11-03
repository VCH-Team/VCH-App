# physics/tests/test_coil.py
import numpy as np
import pytest
import materials
from physics import grid as grid_module
from physics import state as state_module
from physics import config
from physics.operators import coil

@pytest.fixture
def setup_coil():
    cfg = config.with_defaults({
        "r_inner": 0.5, "tank_height": 1.0, "res": 10,
        "M_fluid": 100.0, "T_start": 20.0, "T_amb_mid": 20.0,
        "T_water_in": 80.0, "flow_m3h": 1.0,
        "coil_clearance_bottom": 0.0, "L_avail": 1.0,
        "T_water_arr": np.linspace(0, 100, 10),
        "rho_water_arr": np.full(10, 1000.0),
        "cp_water_arr": np.full(10, 4180.0),
        "mu_water_arr": np.full(10, 0.001),
        "k_water_arr": np.full(10, 0.6),
        "T_tube_arr": np.linspace(0, 100, 10),
        "k_tube_arr": np.full(10, 16.0),
    })
    mat = materials.load(materials.list_available()[0])
    g = grid_module.Grid.build_3d(cfg)
    s = state_module.State(g, mat, cfg)
    
    R_coil = 0.2
    n_turns = 5
    segments = coil.build_coil_segments(g, cfg, R_coil, n_turns)
    
    return cfg, g, s, mat, segments

def test_coil_fluid_cools_down(setup_coil):
    cfg, g, s, mat, segments = setup_coil
    
    dH, T_in, T_out = coil.march(g, s, mat, cfg, dt=1.0, coil_segs=segments)
    
    # Fluid should enter at 80 and leave cooler
    assert T_in == 80.0
    assert T_out < T_in
    
def test_coil_energy_conservation(setup_coil):
    cfg, g, s, mat, segments = setup_coil
    m_dot = cfg["flow_m3h"] * 1000.0 / 3600.0
    cp = 4180.0
    
    dH, T_in, T_out = coil.march(g, s, mat, cfg, dt=1.0, coil_segs=segments)
    
    # Energy lost by the fluid must equal the energy added to the tank
    energy_lost_by_fluid = m_dot * cp * (T_in - T_out) * 1.0
    energy_added_to_tank = np.sum(dH)
    
    assert np.isclose(energy_lost_by_fluid, energy_added_to_tank, rtol=1e-4)