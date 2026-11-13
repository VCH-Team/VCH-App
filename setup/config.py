# setup/config.py
import numpy as np

GROUP_ORDER = ["geometry", "ambient", "coil", "materials", "schedule",
               "drain", "fill", "physics", "numerics"]

DEFAULTS = {
    # ------------------------------------------------------------ geometry
    "r_inner": dict(group="geometry", label="Tank inner radius", type="float", default=1.22, unit="m", min=0.05, max=20.0),
    "tank_height": dict(group="geometry", label="Total tank height", type="float", default=2.8, unit="m", min=0.1, max=50.0),
    "L_avail": dict(group="geometry", label="Axial length available for coil", type="float", default=2.3, unit="m", min=0.05, max=50.0),
    "coil_clearance_bottom": dict(group="geometry", label="Coil clearance at tank bottom", type="float", default=0.2, unit="m", min=0.0, max=10.0),
    "t_wall": dict(group="geometry", label="Tank wall thickness", type="float", default=0.005, unit="m", min=0.0005, max=0.2),
    "fill_to_max": dict(group="geometry", label="Fill tank to rim", type="bool", default=True),
    "M_fluid": dict(group="geometry", label="Fluid mass", type="float", default=None, unit="kg", min=1.0, max=1e7, visible_if=("fill_to_max", False)),
    
    # --- NEW: Bottom Insulation & Ground Physics ---
    "t_ins": dict(group="geometry", label="Side insulation thickness", type="float", default=0.0, unit="m", min=0.0, max=1.0),
    "t_ins_bottom": dict(group="geometry", label="Bottom insulation thickness", type="float", default=0.0, unit="m", min=0.0, max=1.0),
    "grounded": dict(group="geometry", label="Mounted on ground", type="bool", default=False),
    "k_ground": dict(group="geometry", label="Ground conductivity", type="float", default=1.7, unit="W/mK", min=0.01, max=10.0),
    "L_ground": dict(group="geometry", label="Ground characteristic depth", type="float", default=1.0, unit="m", min=0.1, max=10.0),

    # ------------------------------------------------------------- ambient
    "T_amb_low": dict(group="ambient", label="Expected cold", type="float", default=5.0, unit="degC", min=-50.0, max=60.0),
    "T_amb_mid": dict(group="ambient", label="Ambient", type="float", default=18.0, unit="degC", min=-50.0, max=60.0),
    "T_amb_hot": dict(group="ambient", label="Best case", type="float", default=25.0, unit="degC", min=-50.0, max=60.0),
    "h_air": dict(group="ambient", label="Environment", type="choice", default=5.0, unit="W/m2K", choices=[(5.0, "Indoor"), (10.0, "Outdoor"), (25.0, "Windy")]),

    # ---------------------------------------------------------------- coil
    "T_water_in": dict(group="coil", label="Coil inlet temperature", type="float", default=70.0, unit="degC", min=0.0, max=200.0),
    "flow_m3h": dict(group="coil", label="Coil volumetric flow", type="float", default=1.17, unit="m3/h", min=0.001, max=1000.0),
    "d_in": dict(group="coil", label="Tube inner diameter", type="float", default=0.0409, unit="m", min=0.002, max=0.5),
    "d_out": dict(group="coil", label="Tube outer diameter", type="float", default=0.04826, unit="m", min=0.003, max=0.5),
    "R_f_out": dict(group="coil", label="Outside fouling resistance", type="float", default=0.0004, unit="m2K/W", min=0.0, max=0.1),

    # ------------------------------------------------------------ schedule
    "T_start": dict(group="schedule", label="Starting tank fluid temperature", type="float", default=18.0, unit="degC", min=-50.0, max=200.0),
    "t_window_hr": dict(group="schedule", label="Heating window per phase", type="float", default=12.0, unit="h", min=0.01, max=1000.0),
    "t_cooldown_hr": dict(group="schedule", label="Cooldown window per phase", type="float", default=12.0, unit="h", min=0.0, max=1000.0),
    "N_cycles": dict(group="schedule", label="Number of cycles", type="int", default=1, min=1, max=20),

        # --------------------------------------------------------------- drain
    "simulate_drain": dict(group="drain", label="Simulate continuous draining", type="bool", default=False),
    "drain_diameter": dict(group="drain", label="Drain valve diameter", type="float", default=0.05, unit="m", min=0.001, max=1.0),
    "pump_head_m": dict(group="drain", label="Pump Shutoff Head", type="float", default=10.0, unit="m"),
    "motor_power_kw": dict(group="drain", label="Motor Power Rating", type="float", default=0.5, unit="kW"),
    "drain_max_flow_m3h": dict(group="drain", label="Max Flow Rate", type="float", default=0.0),
    
    "pump_type": dict(group="drain", label="Pump Type", type="str", default="Centrifugal"),
    "pump_max_visc": dict(group="drain", label="Pump Max Viscosity", type="float", default=0.5, unit="Pa.s"),
    "pump_chunk_tol_pct": dict(group="drain", label="Pump Max Solid Tolerance", type="float", default=0.0, unit="%"),
    
    # ---------------------------------------------------------------- fill
    "simulate_fill": dict(group="fill", label="Simulate continuous filling", type="bool", default=False),
    "fill_diameter": dict(group="fill", label="Fill nozzle diameter", type="float", default=0.05, unit="m", min=0.001, max=1.0),
    "fill_flow_m3h": dict(group="fill", label="Fill volumetric flow rate", type="float", default=1.0, unit="m3/h", min=0.01, max=100.0),
    "fill_T": dict(group="fill", label="Fill fluid temperature", type="float", default=18.0, unit="degC", min=-50.0, max=200.0),
    "fill_max_flow_m3h": dict(group="fill", label="Max Flow Rate cap", type="float", default=0.0),
    "fill_spread": dict(group="fill", label="Positive Pressure", type="bool", default=True),

    # ------------------------------------------------------------- physics
    "beta_liq": dict(group="physics", label="Liquid thermal expansion coeff", type="float", default=7e-4, unit="1/K", min=0.0, max=1e-2),
    "dT_natural": dict(group="physics", label="Natural-convection driving delta-T", type="float", default=5.0, unit="K", min=0.01, max=100.0),
    "K_settle": dict(group="physics", label="Settling coefficient", type="float", default=1.0, min=0.001, max=100.0),
    "K_flatten": dict(group="physics", label="Flattening coefficient", type="float", default=1.0, min=0.0, max=100.0),
    "fs_lock": dict(group="physics", label="Solid-fraction lock threshold", type="float", default=0.8, min=0.0, max=1.0),
    "thresh_liq": dict(group="physics", label="Flowable liquid-fraction threshold", type="float", default=0.2, min=0.0, max=1.0),
    "thresh_visc": dict(group="physics", label="Flowable viscosity threshold", type="float", default=5.0, unit="Pa.s", min=0.0, max=1e6),

    # ------------------------------------------------------------ numerics
    "res": dict(group="numerics", label="Grid resolution", type="int", default=30, min=5, max=300),
    "dt_sec": dict(group="numerics", label="Timestep", type="float", default=1.0, unit="s", min=0.1, max=60.0),
    "snapshot_interval_hr": dict(group="numerics", label="Snapshot interval (hours)", type="float", default=0.5, min=0.01, max=10.0),
    "tank_shape": dict(group="geometry", label="Tank Shape", type="str", default="cylinder"),
    "tank_length": dict(group="geometry", label="Tank Length (m)", type="float", default=2.44),
    "tank_width": dict(group="geometry", label="Tank Width (m)", type="float", default=2.44),
}

def with_defaults(cfg):
    merged = {k: v["default"] for k, v in DEFAULTS.items()}
    merged.update(cfg)
    return merged