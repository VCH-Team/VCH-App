# config.py -- single source of truth for every user input.
#
# The GUI (CE) reads DEFAULTS and builds forms automatically, one tab per
# `group`. Simulations read values from `cfg` and validate with validate().
#
# Entry schema (all keys optional except group/type/label/default):
#   group        : tab name (see GROUP_ORDER)
#   label        : text shown next to the field
#   type         : "float" | "int" | "bool" | "choice" | "material"
#   default      : value used when the user changes nothing (None = see below)
#   unit         : display unit, "" if dimensionless
#   min / max    : inclusive bounds (float / int only)
#   max_ref      : (key, offset) -> max = cfg[key] + offset   (overrides max)
#   default_from : (key, offset) -> default = cfg[key] + offset, or just a key
#                  string to copy that key's value. Resolved by defaults().
#   choices      : [(value, label), ...] for type "choice"
#   role         : for type "material": which material role it fills
#   visible_if   : (key, value) -> field is only shown/validated when
#                  cfg[key] == value
#   help         : one-line tooltip
#
# Material fields have default None, which means "first available material";
# the GUI fills the drop-down from materials.list_available().

GROUP_ORDER = ["geometry", "ambient", "coil", "materials", "schedule",
               "drain", "fill", "physics", "numerics"]

DEFAULTS = {
    # ------------------------------------------------------------ geometry
    "r_inner": dict(group="geometry", label="Tank inner radius", type="float",
                    default=1.22, unit="m", min=0.05, max=20.0),
    "tank_height": dict(group="geometry", label="Total tank height", type="float",
                        default=2.8, unit="m", min=0.1, max=50.0),
    "L_avail": dict(group="geometry", label="Axial length available for coil",
                    type="float", default=2.3, unit="m", min=0.05, max=50.0),
    "coil_clearance_bottom": dict(group="geometry", label="Coil clearance at tank bottom",
                                  type="float", default=0.2, unit="m", min=0.0, max=10.0),
    "t_wall": dict(group="geometry", label="Tank wall thickness", type="float",
                   default=0.005, unit="m", min=0.0005, max=0.2),
    "fill_to_max": dict(group="geometry", label="Fill tank to rim", type="bool",
                        default=True, help="If off, enter the fluid mass below."),
    "M_fluid": dict(group="geometry", label="Fluid mass", type="float",
                    default=None, unit="kg", min=1.0, max=1e7,
                    visible_if=("fill_to_max", False),
                    help="Capped at tank capacity at the starting temperature."),
    "t_ins": dict(group="geometry", label="Insulation thickness", type="float",
                  default=0.0, unit="m", min=0.0, max=1.0,
                  help="0 = no insulation. (Old UI: yes/no then 0.05 m.)"),

    # ------------------------------------------------------------- ambient
    "T_amb_low": dict(group="ambient", label="Expected cold", type="float",
                      default=5.0, unit="degC", min=-50.0, max=60.0),
    "T_amb_mid": dict(group="ambient", label="Ambient", type="float",
                      default=18.0, unit="degC", min=-50.0, max=60.0),
    "T_amb_hot": dict(group="ambient", label="Best case", type="float",
                      default=25.0, unit="degC", min=-50.0, max=60.0),
    "h_air": dict(group="ambient", label="Environment", type="choice", default=5.0,
                  unit="W/m2K",
                  choices=[(5.0, "Indoor (h_air=5)"),
                           (10.0, "Outdoor (h_air=10)"),
                           (25.0, "Windy (h_air=25)")]),

    # ---------------------------------------------------------------- coil
    "T_water_in": dict(group="coil", label="Coil inlet temperature", type="float",
                       default=70.0, unit="degC", min=0.0, max=200.0),
    "flow_m3h": dict(group="coil", label="Coil volumetric flow", type="float",
                     default=1.17, unit="m3/h", min=0.001, max=1000.0),
    "d_in": dict(group="coil", label="Tube inner diameter", type="float",
                 default=0.0409, unit="m", min=0.002, max=0.5),
    "d_out": dict(group="coil", label="Tube outer diameter", type="float",
                  default=0.04826, unit="m", min=0.003, max=0.5),
    "R_f_out": dict(group="coil", label="Outside fouling resistance", type="float",
                    default=0.0004, unit="m2K/W", min=0.0, max=0.1),

    # ----------------------------------------------------------- materials
    "fluid_name": dict(group="materials", label="Coil-side fluid", type="material",
                       role="fluid", default=None),
    "tank_name": dict(group="materials", label="Tank-side fluid (PCM)", type="material",
                      role="fluid", default=None),
    "wall_name": dict(group="materials", label="Tank wall material", type="material",
                      role="metal", default=None),
    "coil_mat": dict(group="materials", label="Coil tube material", type="material",
                     role="metal", default=None),
    "ins_mat_name": dict(group="materials", label="Insulation material", type="material",
                         role="insulation", default=None,
                         help="Only used when insulation thickness > 0."),

    # ------------------------------------------------------------ schedule
    "T_start": dict(group="schedule", label="Starting tank fluid temperature",
                    type="float", default_from="T_amb_mid", default=18.0,
                    unit="degC", min=-50.0, max=200.0),
    "t_window_hr": dict(group="schedule", label="Heating window per phase", type="float",
                        default=12.0, unit="h", min=0.01, max=1000.0),
    "t_cooldown_hr": dict(group="schedule", label="Cooldown window per phase", type="float",
                          default=12.0, unit="h", min=0.0, max=1000.0),
    "N_cycles": dict(group="schedule", label="Number of cycles (ends on heating)",
                     type="int", default=1, min=1, max=20),

    # --------------------------------------------------------------- drain
    "simulate_drain": dict(group="drain", label="Simulate continuous draining",
                           type="bool", default=False),
    "drain_diameter": dict(group="drain", label="Drain valve diameter", type="float",
                           default=0.05, unit="m", min=0.001, max=1.0,
                           visible_if=("simulate_drain", True)),
    "drain_r_idx": dict(group="drain", label="Drain radial index (0=centre, res-1=wall)",
                        type="int", default=0, min=0, max_ref=("res", -1),
                        visible_if=("simulate_drain", True)),
    "drain_angle": dict(group="drain", label="Drain angular position", type="float",
                        default=0.0, unit="deg", min=0.0, max=360.0,
                        visible_if=("simulate_drain", True),
                        help="Ignored when radial index is 0."),
    "drain_z_idx": dict(group="drain", label="Drain axial index (0=bottom, res-1=top)",
                        type="int", default=0, min=0, max_ref=("res", -1),
                        visible_if=("simulate_drain", True)),

    # ---------------------------------------------------------------- fill
    "simulate_fill": dict(group="fill", label="Simulate continuous filling",
                          type="bool", default=False),
    "fill_diameter": dict(group="fill", label="Fill nozzle diameter", type="float",
                          default=0.05, unit="m", min=0.001, max=1.0,
                          visible_if=("simulate_fill", True)),
    "fill_flow_m3h": dict(group="fill", label="Fill volumetric flow rate", type="float",
                          default=1.0, unit="m3/h", min=0.01, max=100.0,
                          visible_if=("simulate_fill", True)),
    "fill_T": dict(group="fill", label="Fill fluid temperature", type="float",
                   default_from="T_amb_mid", default=18.0, unit="degC",
                   min=-50.0, max=200.0, visible_if=("simulate_fill", True)),
    "fill_r_idx": dict(group="fill", label="Fill radial index (0=centre, res-1=wall)",
                       type="int", default=0, min=0, max_ref=("res", -1),
                       visible_if=("simulate_fill", True)),
    "fill_angle": dict(group="fill", label="Fill angular position", type="float",
                       default=0.0, unit="deg", min=0.0, max=360.0,
                       visible_if=("simulate_fill", True),
                       help="Ignored when radial index is 0."),
    "fill_z_idx": dict(group="fill", label="Fill axial index (0=bottom, res-1=top)",
                       type="int", default_from=("res", -1), default=29, min=0,
                       max_ref=("res", -1), visible_if=("simulate_fill", True)),
    "fill_mode": dict(group="fill", label="Fill behaviour", type="choice", default=0,
                      choices=[(0, "Constant"), (1, "Heating only"), (2, "Cooling only")],
                      visible_if=("simulate_fill", True)),

    # ------------------------------------------------------------- physics
    "beta_liq": dict(group="physics", label="Liquid thermal expansion coeff beta",
                     type="float", default=7e-4, unit="1/K", min=0.0, max=1e-2),
    "dT_natural": dict(group="physics", label="Natural-convection driving delta-T",
                       type="float", default=5.0, unit="K", min=0.01, max=100.0),
    "K_settle": dict(group="physics", label="Settling coefficient", type="float",
                     default=1.0, min=0.001, max=100.0,
                     help="Scales how fast fluid settles vertically under gravity."),
    "K_flatten": dict(group="physics", label="Flattening coefficient", type="float",
                      default=1.0, min=0.0, max=100.0,
                      help="PLACEHOLDER default -- set the real value or delete if unused."),
    "fs_lock": dict(group="physics", label="Solid-fraction lock threshold", type="float",
                    default=0.8, min=0.0, max=1.0),
    "thresh_liq": dict(group="physics", label="Flowable liquid-fraction threshold",
                       type="float", default=0.2, min=0.0, max=1.0,
                       help="Old code read this from the Settings sheet of the datasheet."),
    "thresh_visc": dict(group="physics", label="Flowable viscosity threshold",
                        type="float", default=5.0, unit="Pa.s", min=0.0, max=1e6,
                        help="Old code read this from the Settings sheet of the datasheet."),

    # ------------------------------------------------------------ numerics
    "res": dict(group="numerics", label="3D/2D grid resolution (cells per axis)",
                type="int", default=30, min=5, max=300),
    "dt_sec": dict(group="numerics", label="Timestep", type="float",
                   default=1.0, unit="s", min=0.1, max=60.0),
    "N": dict(group="numerics", label="Radial nodes (1D sweep)", type="int",
              default=100, min=20, max=500),
    "N_radii": dict(group="numerics", label="Number of coil radii to explore",
                    type="int", default=3, min=2, max=20),
    "n_samples": dict(group="numerics", label="Turn samples per radius", type="int",
                      default=10, min=2, max=200,
                      help="Also cannot exceed L_avail / d_out turns."),
}


# ---------------------------------------------------------------- helpers
def _resolve_default(key, spec, cfg):
    ref = spec.get("default_from")
    if ref is None:
        return spec["default"]
    if isinstance(ref, str):
        return cfg.get(ref, spec["default"])
    k, off = ref
    base = cfg.get(k, DEFAULTS[k]["default"])
    return base + off


def defaults():
    """Flat {key: value} dict of all defaults, with default_from resolved."""
    cfg = {k: s["default"] for k, s in DEFAULTS.items()}
    for k, s in DEFAULTS.items():
        if "default_from" in s:
            cfg[k] = _resolve_default(k, s, cfg)
    return cfg


def groups():
    """{group: [(key, spec), ...]} in GROUP_ORDER, for the GUI to lay out tabs."""
    out = {g: [] for g in GROUP_ORDER}
    for k, s in DEFAULTS.items():
        out[s["group"]].append((k, s))
    return out


def is_visible(key, cfg):
    cond = DEFAULTS[key].get("visible_if")
    return cond is None or cfg.get(cond[0]) == cond[1]


def validate(user_cfg, available_materials=None):
    """Merge user values over defaults, coerce types, check bounds.

    Returns (cfg, errors). errors is {key: message}; empty means valid.
    Hidden fields (visible_if false) are coerced but not range-checked.
    """
    cfg = defaults()
    cfg.update({k: v for k, v in user_cfg.items() if k in DEFAULTS})
    errors = {}

    for key, spec in DEFAULTS.items():
        v = cfg[key]
        t = spec["type"]
        check = is_visible(key, cfg)
        try:
            if v is None:
                if t == "material" or key == "M_fluid":
                    continue                      # None is legal (see header)
                raise ValueError("value required")
            if t == "float":
                v = float(v)
            elif t == "int":
                if float(v) != int(float(v)):
                    raise ValueError("must be an integer")
                v = int(float(v))
            elif t == "bool":
                v = bool(v)
            elif t == "choice":
                allowed = [c[0] for c in spec["choices"]]
                if v not in allowed:
                    raise ValueError(f"must be one of {allowed}")
            elif t == "material":
                if available_materials is not None and v not in available_materials:
                    raise ValueError("material not found")
            cfg[key] = v

            if check and t in ("float", "int"):
                lo = spec.get("min")
                hi = spec.get("max")
                if "max_ref" in spec:
                    rk, off = spec["max_ref"]
                    hi = int(cfg[rk]) + off
                if lo is not None and v < lo:
                    raise ValueError(f"must be >= {lo}")
                if hi is not None and v > hi:
                    raise ValueError(f"must be <= {hi}")
        except (ValueError, TypeError) as e:
            if check:
                errors[key] = str(e)

    # cross-field checks
    if not errors:
        if cfg["d_in"] >= cfg["d_out"]:
            errors["d_in"] = "inner diameter must be smaller than outer diameter"
        if cfg["coil_clearance_bottom"] + cfg["L_avail"] > cfg["tank_height"]:
            errors["L_avail"] = "coil clearance + axial length exceeds tank height"
        if not (cfg["T_amb_low"] <= cfg["T_amb_mid"] <= cfg["T_amb_hot"]):
            errors["T_amb_mid"] = "expected order: cold <= ambient <= best case"
        if cfg["n_samples"] > max(2, int(cfg["L_avail"] / cfg["d_out"])):
            errors["n_samples"] = "more turn samples than turns that fit in L_avail"
    return cfg, errors