# setup/grid_builder.py
import numpy as np

class Grid:
    def __init__(self): pass

    @classmethod
    def build_3d(cls, cfg):
        g = cls()
        res = int(cfg["res"])
        tank_height = float(cfg["tank_height"])
        shape = cfg.get("tank_shape", "cylinder")
        
        if shape == "cylinder":
            r_inner = float(cfg["r_inner"])
            L_x = 2.0 * r_inner
            L_y = 2.0 * r_inner
        else:
            r_inner = 0.0
            L_x = float(cfg["tank_length"])
            L_y = float(cfg["tank_width"])

        dx = L_x / res
        dy = L_y / res
        dz = tank_height / res

        index_map = np.full((res, res, res), -1, dtype=np.int32)
        xc_list, yc_list, zc_list, V_list = [], [], [], []
        cell_coords_list = []
        
        c = 0
        for k in range(res):
            for j in range(res):
                for i in range(res):
                    xc = -L_x/2.0 + (i + 0.5) * dx
                    yc = -L_y/2.0 + (j + 0.5) * dy
                    zc = (k + 0.5) * dz
                    
                    is_inside = False
                    if shape == "cylinder":
                        if xc**2 + yc**2 <= r_inner**2:
                            is_inside = True
                    elif shape == "cuboid":
                        is_inside = True 

                    if is_inside:
                        index_map[i, j, k] = c
                        xc_list.append(xc)
                        yc_list.append(yc)
                        zc_list.append(zc)
                        V_list.append(dx * dy * dz)
                        cell_coords_list.append([i, j, k])
                        c += 1

        g.N = c
        g.xc = np.array(xc_list)
        g.yc = np.array(yc_list)
        g.zc = np.array(zc_list)
        g.V = np.array(V_list)
        g.cell_coords = np.array(cell_coords_list, dtype=np.int32)
        
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

        g.col_start, g.col_len, g.col_cells = [], [], []
        for j in range(res):
            for i in range(res):
                col_c = [index_map[i, j, k] for k in range(res) if index_map[i, j, k] >= 0]
                if col_c:
                    g.col_start.append(len(g.col_cells))
                    g.col_len.append(len(col_c))
                    g.col_cells.extend(col_c)

        g.col_start = np.array(g.col_start, dtype=np.int32)
        g.col_len = np.array(g.col_len, dtype=np.int32)
        g.col_cells = np.array(g.col_cells, dtype=np.int32)
        
        # =====================================================================
        # NEW: CALCULATE SIDE AND BOTTOM AREAS WITH GEOMETRIC CORRECTION
        # =====================================================================
        g.side_area = np.zeros(g.N)
        g.bottom_area = np.zeros(g.N)
        
        # 1. Calculate raw staircase areas
        for c in range(g.N):
            for f in range(4): # Lateral faces (0, 1, 2, 3)
                if g.nbr[c, f] == -1:
                    g.side_area[c] += g.A_face[c, f]
            
            if g.nbr[c, 4] == -1: # Bottom face (4)
                g.bottom_area[c] += g.A_face[c, 4]
                
        # 2. Calculate True Geometric Areas based on user inputs
        if shape == "cylinder":
            True_Side_Area = 2.0 * np.pi * r_inner * tank_height
            True_Bottom_Area = np.pi * r_inner**2
        else:
            True_Side_Area = 2.0 * (L_x + L_y) * tank_height
            True_Bottom_Area = L_x * L_y
            
        # 3. Calculate Correction Factors
        sum_side_raw = np.sum(g.side_area)
        sum_bottom_raw = np.sum(g.bottom_area)
        
        corr_side = (True_Side_Area / sum_side_raw) if sum_side_raw > 1e-9 else 1.0
        corr_bottom = (True_Bottom_Area / sum_bottom_raw) if sum_bottom_raw > 1e-9 else 1.0
        
        # 4. Apply Correction Factors
        g.side_area *= corr_side
        g.bottom_area *= corr_bottom
        
        # Print the correction for diagnostics
        print(f"  [Grid] True Side Area: {True_Side_Area:.2f} m² | Correction Factor: {corr_side:.4f}")
        print(f"  [Grid] True Bottom Area: {True_Bottom_Area:.2f} m² | Correction Factor: {corr_bottom:.4f}")

        return g

class CoilSegments:
    def __init__(self, cells, A_seg, d_in, d_out, R_coil):
        self.cells, self.A_seg, self.d_in, self.d_out, self.R_coil = cells, A_seg, d_in, d_out, R_coil

def build_coil_segments(grid, cfg, R_coil, n_turns):
    d_in, d_out, H = cfg["d_in"], cfg["d_out"], cfg["L_avail"]
    r_lo, r_hi = R_coil - d_out/2.0, R_coil + d_out/2.0
    z_lo, z_hi = cfg["coil_clearance_bottom"], cfg["coil_clearance_bottom"] + cfg["L_avail"]
    cells = [c for c in range(grid.N) if r_lo <= np.sqrt(grid.xc[c]**2 + grid.yc[c]**2) <= r_hi and z_lo <= grid.zc[c] <= z_hi]
    cells = np.array(cells)
    cells = cells[np.argsort(grid.zc[cells])]
    L_total = 2.0 * np.pi * R_coil * n_turns
    return CoilSegments(cells, (np.pi * d_out * L_total) / len(cells), d_in, d_out, R_coil)