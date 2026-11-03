# physics/grid.py
import numpy as np

class Grid:
    def __init__(self):
        self.N = 0
        self.V = None
        self.xc = None
        self.yc = None
        self.zc = None
        self.nbr = None
        self.A_face = None
        self.d_face = None
        self.col_start = None
        self.col_len = None
        self.col_cells = None
        self.wall_area = None
        self.cell_coords = None # <--- Added this
        self.is_1d = False

    @classmethod
    def build_3d(cls, cfg):
        g = cls()
        res = int(cfg["res"])
        r_inner = float(cfg["r_inner"])
        tank_height = float(cfg["tank_height"])

        dx = (2.0 * r_inner) / res
        dy = dx
        dz = tank_height / res

        # Map 3D index (i,j,k) to flat index c
        index_map = np.full((res, res, res), -1, dtype=np.int32)
        
        xc_list, yc_list, zc_list, V_list = [], [], [], []
        cell_coords_list = [] # <--- Added this
        
        c = 0
        for k in range(res):
            for j in range(res):
                for i in range(res):
                    xc = -r_inner + (i + 0.5) * dx
                    yc = -r_inner + (j + 0.5) * dy
                    zc = (k + 0.5) * dz
                    
                    # Only keep cells inside the cylinder
                    if xc**2 + yc**2 <= r_inner**2:
                        index_map[i, j, k] = c
                        xc_list.append(xc)
                        yc_list.append(yc)
                        zc_list.append(zc)
                        V_list.append(dx * dy * dz)
                        cell_coords_list.append([i, j, k]) # <--- Added this
                        c += 1

        g.N = c
        g.xc = np.array(xc_list)
        g.yc = np.array(yc_list)
        g.zc = np.array(zc_list)
        g.V = np.array(V_list)
        g.cell_coords = np.array(cell_coords_list, dtype=np.int32) # <--- Added this
        
        # Face order: -x, +x, -y, +y, -z, +z
        g.nbr = np.full((g.N, 6), -1, dtype=np.int32)
        g.A_face = np.zeros((g.N, 6))
        g.d_face = np.zeros((g.N, 6))
        
        A_x = dy * dz
        A_y = dx * dz
        A_z = dx * dy
        
        for k in range(res):
            for j in range(res):
                for i in range(res):
                    c = index_map[i, j, k]
                    if c < 0:
                        continue
                    
                    if i > 0 and index_map[i-1, j, k] >= 0:
                        g.nbr[c, 0] = index_map[i-1, j, k]
                        g.A_face[c, 0] = A_x
                        g.d_face[c, 0] = dx
                    if i < res - 1 and index_map[i+1, j, k] >= 0:
                        g.nbr[c, 1] = index_map[i+1, j, k]
                        g.A_face[c, 1] = A_x
                        g.d_face[c, 1] = dx
                        
                    if j > 0 and index_map[i, j-1, k] >= 0:
                        g.nbr[c, 2] = index_map[i, j-1, k]
                        g.A_face[c, 2] = A_y
                        g.d_face[c, 2] = dy
                    if j < res - 1 and index_map[i, j+1, k] >= 0:
                        g.nbr[c, 3] = index_map[i, j+1, k]
                        g.A_face[c, 3] = A_y
                        g.d_face[c, 3] = dy
                        
                    if k > 0 and index_map[i, j, k-1] >= 0:
                        g.nbr[c, 4] = index_map[i, j, k-1]
                        g.A_face[c, 4] = A_z
                        g.d_face[c, 4] = dz
                    if k < res - 1 and index_map[i, j, k+1] >= 0:
                        g.nbr[c, 5] = index_map[i, j, k+1]
                        g.A_face[c, 5] = A_z
                        g.d_face[c, 5] = dz

        # Build columns for settling
        col_start = []
        col_len = []
        col_cells = []
        
        for j in range(res):
            for i in range(res):
                col_c = []
                for k in range(res):
                    c = index_map[i, j, k]
                    if c >= 0:
                        col_c.append(c)
                if len(col_c) > 0:
                    col_start.append(len(col_cells))
                    col_len.append(len(col_c))
                    col_cells.extend(col_c)

        g.col_start = np.array(col_start, dtype=np.int32)
        g.col_len = np.array(col_len, dtype=np.int32)
        g.col_cells = np.array(col_cells, dtype=np.int32)
        
        # Calculate wall areas (faces that are -1 and touch the outside)
        g.wall_area = np.zeros(g.N)
        for c in range(g.N):
            for f in range(4): # radial walls only
                if g.nbr[c, f] == -1:
                    g.wall_area[c] += g.A_face[c, f]
                    
        return g