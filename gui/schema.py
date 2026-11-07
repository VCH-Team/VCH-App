"""Declarative GUI field schema — one entry per input the user fills.
Edit this file to add/remove/rename inputs without touching any widget code."""

SCHEMA = [
    # Each tab is (tab_id, tab_label, [field dicts]).
    # Each field dict has: key (var name), label (shown in GUI),
    #                     type (float/int/bool/choice/material),
    #                     default, plus role/choices when relevant.

    ("materials", "Materials", [
        # type="material" → combobox filled from pipeline_bridge.list_for_role(role)
        {"key": "mat_tank", "label": "Tank Fluid (PCM)", "type": "material",
         "role": "fluid", "default": "RBD Palm Oil"},
        {"key": "mat_coil", "label": "Coil Fluid", "type": "material",
         "role": "fluid", "default": "Water"},
        {"key": "mat_tube", "label": "Coil Tube Metal", "type": "material",
         "role": "metal", "default": "Copper"},
        {"key": "mat_wall", "label": "Tank Wall Metal", "type": "material",
         "role": "metal", "default": "Mild Steel"},
        {"key": "mat_ins", "label": "Insulation Material", "type": "material",
         "role": "insulation", "default": "Polyisocyanurate (PIR)"},
    ]),

    ("geometry", "Geometry", [
        # type="choice" → combobox; choices is [(value, label), ...]
        {"key": "shape", "label": "Tank shape", "type": "choice",
         "default": "cylinder",
         "choices": [("cylinder", "Cylinder"), ("cuboid", "Cuboid")]},
        {"key": "r_inner", "label": "Tank radius (m)", "type": "float", "default": 0.5},
        {"key": "tank_height", "label": "Tank height (m)", "type": "float", "default": 1.0},
        {"key": "res", "label": "Grid resolution", "type": "int", "default": 20},
        {"key": "t_wall", "label": "Wall thickness (m)", "type": "float", "default": 0.005},
        # type="bool" → Checkbutton
        {"key": "has_ins", "label": "Add insulation", "type": "bool", "default": False},
        {"key": "t_ins", "label": "Insulation thickness (m)", "type": "float", "default": 0.05},
        {"key": "k_ins", "label": "Insulation k (W/mK)", "type": "float", "default": 0.024},
        {"key": "h_air", "label": "Ambient air h (W/m2K)", "type": "float", "default": 10.0},
    ]),

    ("operating", "Operating", [
        {"key": "T_amb_low", "label": "Coldest site temp (°C)", "type": "float", "default": 5.0},
        {"key": "T_amb_mid", "label": "Ambient temp (°C)", "type": "float", "default": 25.0},
        {"key": "T_start", "label": "Tank start temp (°C)", "type": "float", "default": 20.0},
        {"key": "T_target", "label": "Target liquid temp (°C)", "type": "float", "default": 60.0},
        {"key": "T_water_in", "label": "Coil inlet temp (°C)", "type": "float", "default": 80.0},
        {"key": "flow_m3h", "label": "Coil flow rate (m3/h)", "type": "float", "default": 1.0},
        {"key": "M_fluid", "label": "Tank fluid mass (kg, 0 = full)", "type": "float", "default": 0.0},
    ]),

    ("coil", "Coil & Timing", [
        {"key": "d_in", "label": "Coil inner dia (m)", "type": "float", "default": 0.0409},
        {"key": "d_out", "label": "Coil outer dia (m)", "type": "float", "default": 0.04826},
        {"key": "bottom_clearance", "label": "Bottom clearance (m)", "type": "float", "default": 0.05},
        {"key": "top_clearance", "label": "Top clearance (m)", "type": "float", "default": 0.05},
        {"key": "t_window_hr", "label": "Simulation duration (h)", "type": "float", "default": 1.0},
        {"key": "dt_sec", "label": "Time step (s)", "type": "float", "default": 1.0},
        {"key": "snapshot_interval_hr", "label": "Snapshot interval (h)", "type": "float", "default": 0.1},
    ]),

    ("drain_fill", "Drain & Fill", [
        {"key": "sim_drain", "label": "Enable drain", "type": "bool", "default": False},
        {"key": "drain_z", "label": "Drain height (m)", "type": "float", "default": 0.01},
        {"key": "drain_d", "label": "Drain hole dia (m)", "type": "float", "default": 0.05},
        {"key": "sim_fill", "label": "Enable fill", "type": "bool", "default": False},
        {"key": "fill_z", "label": "Fill height (m)", "type": "float", "default": 0.99},
        {"key": "fill_d", "label": "Fill nozzle dia (m)", "type": "float", "default": 0.05},
        {"key": "fill_flow", "label": "Fill flow (m3/h)", "type": "float", "default": 0.5},
        {"key": "fill_T", "label": "Fill temp (°C)", "type": "float", "default": 20.0},
    ]),

    ("phase_a", "Phase A", [
        {"key": "num_R", "label": "Coil radii to compare", "type": "int", "default": 3},
        {"key": "min_R", "label": "Min radius (m)", "type": "float", "default": 0.15},
        {"key": "max_R", "label": "Max radius (m)", "type": "float", "default": 0.45},
        {"key": "max_turns", "label": "Max turns to test", "type": "int", "default": 20},
    ]),

    ("coil_select", "Coil Selection", [
        {"key": "R_coil", "label": "Chosen coil radius (m)", "type": "float", "default": 0.45},
        {"key": "n_turns", "label": "Chosen turns", "type": "int", "default": 10},
    ]),
]