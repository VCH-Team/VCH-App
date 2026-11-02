# physics/tests/test_grid.py
import numpy as np
import pytest
from physics.grid import Grid

@pytest.fixture
def test_cfg():
    return {"res": 10, "r_inner": 1.0, "tank_height": 2.0}

def test_volume_sum(test_cfg):
    """Checks that the sum of all cell volumes roughly matches the cylinder volume."""
    grid = Grid.build_3d(test_cfg)
    expected_vol = np.pi * (test_cfg["r_inner"]**2) * test_cfg["tank_height"]
    actual_vol = np.sum(grid.V)
    # Grid discretization means we lose a little volume around the curved walls
    assert abs(actual_vol - expected_vol) / expected_vol < 0.05

def test_face_reciprocity(test_cfg):
    """Checks that the face area seen from cell A equals the area seen from cell B."""
    grid = Grid.build_3d(test_cfg)
    opposite = [1, 0, 3, 2, 5, 4]
    
    for c in range(grid.N):
        for f in range(6):
            nbr_cell = grid.nbr[c, f]
            if nbr_cell >= 0:
                assert np.isclose(grid.A_face[c, f], grid.A_face[nbr_cell, opposite[f]])

def test_column_integrity(test_cfg):
    """Checks that the column arrays are set up correctly."""
    grid = Grid.build_3d(test_cfg)
    assert len(grid.col_start) > 0
    assert len(grid.col_len) > 0
    # Total cells in columns must equal total active cells
    assert np.sum(grid.col_len) == grid.N
    assert len(grid.col_cells) == grid.N