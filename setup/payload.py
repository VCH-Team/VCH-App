# setup/payload.py
import numpy as np
from typing import NamedTuple

# ==============================================================================
# 1. NUMBA-COMPATIBLE STRUCTS (NamedTuples)
# ==============================================================================

class NumbaConfig(NamedTuple):
    # Timing & Logic
    dt_sec: float
    t_window_hr: float
    t_cooldown_hr: float
    n_cycles: int
    snapshot_interval_hr: float
    fs_lock: float
    K_settle: float
    K_flatten: float
    tank_shape_id: int          # 0 = cylinder, 1 = cuboid
    res: int
    dz: float
    T_start: float              
    
    # Physics Constants
    T_amb_mid: float
    h_air: float
    t_wall: float
    t_ins: float
    k_ins: float
    beta_liq: float
    dT_natural: float
    thresh_liq: float
    thresh_visc: float
    
    # Coil Constants (Pre-calculated in Setup)
    m_dot_coil: float
    rho_c: float
    cp_c: float
    mu_c: float
    k_c: float
    k_tube: float
    C_coil: float
    d_in: float
    d_out: float
    R_f_out: float
    T_water_in: float
    
    # Drain & Fill
    simulate_drain: bool
    drain_cell_idx: int
    drain_col_idx: int
    drain_area: float
    pump_head_m: float           # <--- CHANGED
    motor_power_kw: float        # <--- NEW
    drain_max_flow_m3h: float
    pump_max_visc: float         
    pump_chunk_tol_pct: float  
    
    simulate_fill: bool
    fill_cell_idx: int
    fill_mdot: float            # Volumetric flow (m3/s)
    fill_T: float
    fill_max_flow_m3h: float
    fill_spread: bool
    fill_radius_cells: int      
    max_tank_mass: float        # Maximum physical mass tank can hold

    # Boundary / Ground Physics
    grounded: bool              # True if on ground, False if elevated
    t_ins_bottom: float         # Bottom insulation thickness
    k_ground: float             # Ground thermal conductivity
    L_ground: float             # Ground characteristic length (1.0m)

    # Wall Material (for U-value calculation)
    T_wall_arr: np.ndarray
    k_wall_arr: np.ndarray

class NumbaGrid(NamedTuple):
    N: int
    V: np.ndarray              
    nbr: np.ndarray            
    A_face: np.ndarray         
    d_face: np.ndarray         
    side_area: np.ndarray      # <--- REPLACED wall_area
    bottom_area: np.ndarray    # <--- ADDED bottom_area
    xc: np.ndarray             
    yc: np.ndarray             
    zc: np.ndarray             
    col_cells: np.ndarray      
    col_start: np.ndarray      
    col_len: np.ndarray        
    coil_cells: np.ndarray     
    coil_A_seg: float
    coil_R_coil: float

class NumbaMaterial(NamedTuple):
    T_grid: np.ndarray
    H_grid: np.ndarray
    rho_grid: np.ndarray
    k_grid: np.ndarray
    mu_grid: np.ndarray
    cp_eff_grid: np.ndarray
    cp_sens_grid: np.ndarray
    
    T_ms: float
    T_me: float
    H_solid: float
    H_liquid: float
    has_melt: bool

# ==============================================================================
# 2. FACTORY FUNCTION
# ==============================================================================

def build_payload(cfg, mat_tank_dict, mat_coil_dict, mat_tube_dict, mat_wall_dict, grid, coil_segs, drain_idx, fill_idx, drain_col_idx):
    """
    Takes the raw Python dictionaries and objects, and compiles them into
    rigid NamedTuples that Numba can read at C-speed.
    """
    
    # --- A. Pre-calculate Melt Band for Tank Material ---
    T_ms = float(mat_tank_dict.get("T_ms", np.nan))
    T_me = float(mat_tank_dict.get("T_me", np.nan))
    has_melt = not (np.isnan(T_ms) or np.isnan(T_me))
    
    H_solid = float(np.interp(T_ms, mat_tank_dict["T_grid"], mat_tank_dict["H_grid"])) if has_melt else 0.0
    H_liquid = float(np.interp(T_me, mat_tank_dict["T_grid"], mat_tank_dict["H_grid"])) if has_melt else 0.0

    mat_tank = NumbaMaterial(
        T_grid=np.ascontiguousarray(mat_tank_dict["T_grid"], dtype=np.float64),
        H_grid=np.ascontiguousarray(mat_tank_dict["H_grid"], dtype=np.float64),
        rho_grid=np.ascontiguousarray(mat_tank_dict["rho_grid"], dtype=np.float64),
        k_grid=np.ascontiguousarray(mat_tank_dict["k_grid"], dtype=np.float64),
        mu_grid=np.ascontiguousarray(mat_tank_dict["mu_grid"], dtype=np.float64),
        cp_eff_grid=np.ascontiguousarray(mat_tank_dict["cp_eff_grid"], dtype=np.float64),
        cp_sens_grid=np.ascontiguousarray(mat_tank_dict["cp_sens_grid"], dtype=np.float64),
        T_ms=T_ms, T_me=T_me,
        H_solid=H_solid, H_liquid=H_liquid,
        has_melt=has_melt
    )

    # Calculate nozzle radius in grid cells (assuming cubic cells)
    cell_size = (grid.V[0]) ** (1/3) if grid.N > 0 else 0.05
    fill_radius_m = cfg.get("fill_diameter", 0.05) / 2.0
    fill_radius_cells = int(np.ceil(fill_radius_m / cell_size))
    if fill_radius_cells < 1: 
        fill_radius_cells = 1

    # --- Calculate absolute maximum mass the tank can hold ---
    V_tank = float(np.sum(grid.V))
    rho_min = float(np.min(mat_tank_dict["rho_grid"]))
    max_tank_mass = V_tank * rho_min * 1.05 

    # --- B. Pre-calculate Coil Fluid Properties ---
    T_in = float(cfg["T_water_in"])
    m_dot_coil = float(cfg["flow_m3h"] * np.interp(T_in, mat_coil_dict["T_grid"], mat_coil_dict["rho_grid"]) / 3600.0)
    rho_c = float(np.interp(T_in, mat_coil_dict["T_grid"], mat_coil_dict["rho_grid"]))
    cp_c  = float(np.interp(T_in, mat_coil_dict["T_grid"], mat_coil_dict["cp_sens_grid"]))
    mu_c  = float(np.interp(T_in, mat_coil_dict["T_grid"], mat_coil_dict["mu_grid"]))
    k_c   = float(np.interp(T_in, mat_coil_dict["T_grid"], mat_coil_dict["k_grid"]))
    k_tube = float(np.interp(T_in, mat_tube_dict["T_grid"], mat_tube_dict["k_grid"]))
    C_coil = m_dot_coil * cp_c

    # --- C. Compile NumbaConfig ---
    shape_id = 0 if cfg.get("tank_shape", "cylinder") == "cylinder" else 1
    
    drain_area = float(np.pi * (cfg.get("drain_diameter", 0.0) / 2.0)**2) if cfg.get("simulate_drain", False) else 0.0
    fill_mdot = float(cfg.get("fill_flow_m3h", 0.0)) / 3600.0 if cfg.get("simulate_fill", False) else 0.0

    ncfg = NumbaConfig(
        dt_sec=float(cfg["dt_sec"]),
        t_window_hr=float(cfg["t_window_hr"]),
        t_cooldown_hr=float(cfg["t_cooldown_hr"]),
        n_cycles=int(cfg["N_cycles"]),
        snapshot_interval_hr=float(cfg["snapshot_interval_hr"]),
        fs_lock=float(cfg["fs_lock"]),
        K_settle=float(cfg["K_settle"]),
        K_flatten=float(cfg["K_flatten"]),
        tank_shape_id=shape_id,
        res=int(cfg["res"]),
        dz=float(cfg["tank_height"] / cfg["res"]),
        T_start=float(cfg["T_start"]), 
        
        T_amb_mid=float(cfg["T_amb_mid"]),
        h_air=float(cfg["h_air"]),
        t_wall=float(cfg["t_wall"]),
        t_ins=float(cfg["t_ins"]),
        k_ins=float(cfg.get("k_ins", 0.04)),
        beta_liq=float(cfg["beta_liq"]),
        dT_natural=float(cfg["dT_natural"]),
        thresh_liq=float(cfg["thresh_liq"]),
        thresh_visc=float(cfg["thresh_visc"]),
        
        m_dot_coil=m_dot_coil,
        rho_c=rho_c,
        cp_c=cp_c,
        mu_c=mu_c,
        k_c=k_c,
        k_tube=k_tube,
        C_coil=C_coil,
        d_in=float(cfg["d_in"]),
        d_out=float(cfg["d_out"]),
        R_f_out=float(cfg["R_f_out"]),
        T_water_in=T_in,
        
        # --- DRAIN & PUMP SECTION (Make sure there's only ONE of each here) ---
        simulate_drain=bool(cfg.get("simulate_drain", False)),
        drain_cell_idx=int(drain_idx),
        drain_col_idx=int(drain_col_idx),
        drain_area=drain_area,
        pump_head_m=float(cfg.get("pump_head_m", 10.0)),         
        motor_power_kw=float(cfg.get("motor_power_kw", 0.5)),    
        drain_max_flow_m3h=float(cfg.get("drain_max_flow_m3h", 0.0)),
        pump_max_visc=float(cfg.get("pump_max_visc", 0.5)),
        pump_chunk_tol_pct=float(cfg.get("pump_chunk_tol_pct", 0.0)),
        # ------------------------------------------------------------------------
        
        simulate_fill=bool(cfg.get("simulate_fill", False)),
        fill_cell_idx=int(fill_idx),
        fill_mdot=fill_mdot,
        fill_T=float(cfg.get("fill_T", cfg["T_amb_mid"])),
        fill_max_flow_m3h=float(cfg.get("fill_max_flow_m3h", 0.0)),
        fill_spread=bool(cfg.get("fill_spread", True)),
        fill_radius_cells=fill_radius_cells, 
        max_tank_mass=max_tank_mass,  
        
        grounded=bool(cfg.get("grounded", False)),
        t_ins_bottom=float(cfg.get("t_ins_bottom", 0.0)),
        k_ground=float(cfg.get("k_ground", 1.0)),
        L_ground=float(cfg.get("L_ground", 1.0)),
        
        T_wall_arr=np.ascontiguousarray(mat_wall_dict["T_grid"], dtype=np.float64),
        k_wall_arr=np.ascontiguousarray(mat_wall_dict["k_grid"], dtype=np.float64)
    )

    # --- D. Compile NumbaGrid ---
    ngrid = NumbaGrid(
        N=int(grid.N),
        V=np.ascontiguousarray(grid.V, dtype=np.float64),
        nbr=np.ascontiguousarray(grid.nbr, dtype=np.int32),
        A_face=np.ascontiguousarray(grid.A_face, dtype=np.float64),
        d_face=np.ascontiguousarray(grid.d_face, dtype=np.float64),
        side_area=np.ascontiguousarray(grid.side_area, dtype=np.float64),     # <--- NEW
        bottom_area=np.ascontiguousarray(grid.bottom_area, dtype=np.float64), # <--- NEW
        xc=np.ascontiguousarray(grid.xc, dtype=np.float64),
        yc=np.ascontiguousarray(grid.yc, dtype=np.float64),
        zc=np.ascontiguousarray(grid.zc, dtype=np.float64),
        col_cells=np.ascontiguousarray(grid.col_cells, dtype=np.int32),
        col_start=np.ascontiguousarray(grid.col_start, dtype=np.int32),
        col_len=np.ascontiguousarray(grid.col_len, dtype=np.int32),
        coil_cells=np.ascontiguousarray(coil_segs.cells, dtype=np.int32),
        coil_A_seg=float(coil_segs.A_seg),
        coil_R_coil=float(coil_segs.R_coil)
    )

    return ncfg, ngrid, mat_tank