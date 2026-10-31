# physics/grid.py
import numpy as np

class Grid:
    """
    Holds the spatial data for the simulation.
    For Phase 1, we are implementing the 1D radial grid.
    """
    def __init__(self):
        self.N = 0                  # Number of active cells
        self.V = None               # (N,) Volume of each cell [m^3]
        self.xc = None              # (N,) Cell center radius [m]
        self.yc = None              # (N,) Cell center y (0 for 1D)
        self.zc = None              # (N,) Cell center z (0 for 1D)
        
        self.nbr = None             # (N, 6) int32. Neighbors (-1 = wall). 
        self.A_face = None          # (N, 6) Face areas [m^2]
        self.d_face = None          # (N, 6) Distance to neighbor center [m]
        
        self.wall_area = None       # (N,) External wall area [m^2]
        self.is_1d = True

    @classmethod
    def build_1d(cls, cfg: dict) -> "Grid":
        """Builds a 1D radial grid based on the configuration dictionary."""
        grid = cls()
        grid.is_1d = True
        
        N = cfg["n_radial_1d"]
        R_tank = cfg["tank_radius"]
        H_tank = cfg["tank_height"]
        
        grid.N = N
        
        # 1. Define the radial edges of the cells
        r_edges = np.linspace(0.0, R_tank, N + 1)
        
        # 2. Cell centers (xc)
        grid.xc = 0.5 * (r_edges[:-1] + r_edges[1:])
        grid.yc = np.zeros(N)
        grid.zc = np.zeros(N)
        
        # 3. Cell Volumes (V)
        grid.V = np.pi * (r_edges[1:]**2 - r_edges[:-1]**2) * H_tank
        
        # 4. Face Areas (A_face)
        grid.A_face = np.zeros((N, 6))
        grid.A_face[:, 0] = 2.0 * np.pi * r_edges[:-1] * H_tank # Inner
        grid.A_face[:, 1] = 2.0 * np.pi * r_edges[1:] * H_tank  # Outer
        
        # 5. Neighbors (nbr)
        grid.nbr = np.full((N, 6), -1, dtype=np.int32)
        for i in range(N):
            if i > 0:
                grid.nbr[i, 0] = i - 1  # Inner neighbor
            if i < N - 1:
                grid.nbr[i, 1] = i + 1  # Outer neighbor
                
        # 6. Distances (d_face)
        grid.d_face = np.zeros((N, 6))
        for i in range(N):
            if i > 0:
                grid.d_face[i, 0] = grid.xc[i] - grid.xc[i-1]
            if i < N - 1:
                grid.d_face[i, 1] = grid.xc[i+1] - grid.xc[i]
                
        # 7. Wall Area
        grid.wall_area = np.zeros(N)
        grid.wall_area[-1] = grid.A_face[-1, 1]
        
        return grid

    @classmethod
    def build_3d(cls, cfg: dict) -> "Grid":
        raise NotImplementedError("3D grid will be built in Phase 3.")