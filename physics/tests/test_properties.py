# physics/tests/test_properties.py
import numpy as np
import pytest
import materials
from physics import grid as grid_module
from physics import state as state_module
from physics import properties
from physics.config import with_defaults


@pytest.fixture
def setup():
    """Build a small grid + filled state for testing."""
    cfg = with_defaults({
        "r_inner": 0.5,
        "tank_height": 1.0,
        "res": 10,          # tiny grid, ~80 cells
        "M_fluid": 30.0,
        "T_start": 25.0,
    })
    mat = materials.load("Water")   # ← replace with your actual cached material name
    g = grid_module.Grid.build_3d(cfg)
    s = state_module.State.allocate(g, mat, T_start=25.0,
                                     M_fluid=30.0,
                                     tank_height=1.0)
    return cfg, g, s, mat


def test_temperature_roundtrip(setup):
    """At T_start, refresh should give back T_start."""
    cfg, g, s, mat = setup
    properties.refresh(g, s, mat)
    non_empty = s.m > properties.M_MIN
    np.testing.assert_allclose(s.T[non_empty], 25.0, atol=0.5)


def test_empty_cells_masked(setup):
    """Cells with no mass have NaN properties and zero cap/fill."""
    cfg, g, s, mat = setup
    properties.refresh(g, s, mat)
    empty = s.m <= properties.M_MIN
    assert np.all(np.isnan(s.T[empty]))
    assert np.all(np.isnan(s.rho[empty]))
    assert np.all(s.cap[empty] == 0.0)
    assert np.all(s.fill[empty] == 0.0)


def test_fill_fraction_sane(setup):
    """Fill fraction is between 0 and 1 for non-empty cells."""
    cfg, g, s, mat = setup
    properties.refresh(g, s, mat)
    non_empty = s.m > properties.M_MIN
    assert np.all(s.fill[non_empty] >= 0.0)
    assert np.all(s.fill[non_empty] <= 1.01)  # tiny round-off allowance