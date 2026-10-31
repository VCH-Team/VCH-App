# physics/grid.py
import numpy as np

class Grid:
    """
    Holds the spatial data for the simulation.
    Matches the API expected by state.py and properties.py.
    """
    def __init__(self):
        # properties.py uses grid.N, state.py uses mesh.n_cells. 
        # We provide both so both files work!
        self.N = 0                  
        self.n_cells = 0            
        
        self.V = None               # (N,) Volume of each cell [m^3]
        self.xc = None              # (N,) Cell center radius [m]
        self.yc = None              # (N,) Cell center y (0 for 1D)
        self.zc = None              # (N,) Cell center z (0 for 1D) - needed by state.py
        
        self.nbr = None             # (N, 6) int32. Neighbors (-1 = wall). 
        self.A_face = None          # (N, 6) Face areas [m^2]
        self.d_face = None          # (N, 6) Distance to neighbor center [m]
        self.wall_area = None       # (N,) External wall area [m^2]
        self.is_1d = True
        
        # Column data needed by state.py for initial filling
        self.n_cols = 0
        self.col_start = None
        self.col_len = None
        self.col_cells = None

    @classmethod
    def build_1d(cls, cfg: dict) -> "Grid":
        """Builds a 1D radial grid based on the config dictionary."""
        grid = cls()
        grid.is_1d = True
        
        # Notice we are now using your friend's config keys: "N" and "r_inner"
        N = cfg["N"]
        R_tank = cfg["r_inner"]
        H_tank = cfg["tank_height"]
        
        grid.N = N
        grid.n_cells = N
        
        # 1. Define the radial edges of the cells
        r_edges = np.linspace(0.0, R_tank, N + 1)
        
        # 2. Cell centers
        grid.xc = 0.5 * (r_edges[:-1] + r_edges[1:])
        grid.yc = np.zeros(N)
        grid.zc = np.zeros(N) # Dummy array for 1D
        
        # 3. Cell Volumes
        grid.V = np.pi * (r_edges[1:]**2 - r_edges[:-1]**2) * H_tank
        
        # 4. Face Areas
        grid.A_face = np.zeros((N, 6))
        grid.A_face[:, 0] = 2.0 * np.pi * r_edges[:-1] * H_tank 
        grid.A_face[:, 1] = 2.0 * np.pi * r_edges[1:] * H_tank  
        
        # 5. Neighbors
        grid.nbr = np.full((N, 6), -1, dtype=np.int32)
        for i in range(N):
            if i > 0: grid.nbr[i, 0] = i - 1
            if i < N - 1: grid.nbr[i, 1] = i + 1
                
        # 6. Distances
        grid.d_face = np.zeros((N, 6))
        for i in range(N):
            if i > 0: grid.d_face[i, 0] = grid.xc[i] - grid.xc[i-1]
            if i < N - 1: grid.d_face[i, 1] = grid.xc[i+1] - grid.xc[i]
                
        # 7. Wall Area
        grid.wall_area = np.zeros(N)
        grid.wall_area[-1] = grid.A_face[-1, 1]
        
        # 8. Dummy Columns for 1D (Satisfies state.py's _initial_fill kernel)
        # In 1D, we just treat every radial ring as its own single-cell column
        grid.n_cols = N
        grid.col_start = np.arange(N, dtype=np.int64)
        grid.col_len = np.ones(N, dtype=np.int64)
        grid.col_cells = np.arange(N, dtype=np.int64)
        
        return grid

    @classmethod
    def build_3d(cls, cfg: dict) -> "Grid":
        raise NotImplementedError("3D grid will be built in Phase 3.")