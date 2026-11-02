# physics/tests/test_grid.py
import numpy as np
import pytest
from physics.grid import Grid

# We create a fake config dictionary just for testing
@pytest.fixture
def test_cfg():
    return {
        "N": 10,              # Use 10 cells for a quick test
        "r_inner": 1.0,       # 1 meter radius
        "tank_height": 2.0    # 2 meters tall
    }

def test_1d_volume_conservation(test_cfg):
    """Checks that the sum of all cell volumes equals the total cylinder volume."""
    grid = Grid.build_1d(test_cfg)
    
    # Volume of a cylinder = pi * r^2 * h
    expected_volume = np.pi * (test_cfg["r_inner"]**2) * test_cfg["tank_height"]
    actual_volume = np.sum(grid.V)
    
    # np.isclose checks if the numbers are the same up to 6 decimal places
    assert np.isclose(actual_volume, expected_volume), "Grid volumes do not add up to tank volume!"

def test_face_reciprocity(test_cfg):
    """Checks that the outer face area of cell i matches the inner face of cell i+1."""
    grid = Grid.build_1d(test_cfg)
    
    for i in range(grid.N - 1):
        outer_face_area = grid.A_face[i, 1]   # +x face of current cell
        inner_face_area = grid.A_face[i+1, 0] # -x face of next cell
        
        assert np.isclose(outer_face_area, inner_face_area), f"Face area mismatch between cell {i} and {i+1}!"

def test_wall_area(test_cfg):
    """Checks that ONLY the outermost cell touches the tank wall."""
    grid = Grid.build_1d(test_cfg)
    
    # All inner cells should have 0 wall area
    assert np.all(grid.wall_area[:-1] == 0.0), "Inner cells should not touch the external wall!"
    
    # The very last cell should have a wall area > 0
    assert grid.wall_area[-1] > 0.0, "Outer cell must have an external wall area!"

def test_column_integrity(test_cfg):
    """Checks that the column arrays (needed by state.py) are set up correctly for 1D."""
    grid = Grid.build_1d(test_cfg)
    
    assert grid.n_cols == test_cfg["N"]
    assert len(grid.col_start) == test_cfg["N"]
    assert len(grid.col_len) == test_cfg["N"]
    assert len(grid.col_cells) == test_cfg["N"]
    
    # In 1D, every column has exactly 1 cell
    assert np.all(grid.col_len == 1), "Every 1D column should contain exactly 1 cell."
    
    # Check the first and last column mapping
    assert grid.col_cells[0] == 0
    assert grid.col_cells[-1] == test_cfg["N"] - 1