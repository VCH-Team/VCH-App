# IO/viewer.py
import glob
import os
import json
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

def create_interactive_viewer(run_folder):
    print(f"  Building 3D Viewer & 2D Maps for: {run_folder}")
    snap_dir = os.path.join(run_folder, "snapshots")
    files = sorted(glob.glob(os.path.join(snap_dir, "*.npz")))
    
    if not files:
        print("  No snapshots found!"); return
        
    # --- LOAD RUN INFO ---
    info = {"shape": "cylinder", "r_inner": 0.5, "tank_length": 1.0, "tank_width": 1.0, 
            "tank_height": 1.0, "t_wall": 0.0, "t_ins": 0.0, "drain_coords": None, "fill_coords": None,
            "max_tank_mass": 1000.0, "slice_angles": [0.0, 90.0], "dx": 0.05, "dz": 0.05}
    info_path = os.path.join(run_folder, "run_info.json")
    if os.path.exists(info_path):
        with open(info_path, "r") as f:
            info.update(json.load(f))
            
    angle1, angle2 = info["slice_angles"]
    dx, dz = info["dx"], info["dz"]
    
    # --- PRE-CALCULATE SLICE MASKS ---
    res = np.load(files[0])["T"].shape[0]
    center = res / 2.0
    max_r_bins = int(np.ceil(center))
    
    x_idx, y_idx, z_idx = np.indices((res, res, res))
    x_c = x_idx - center
    y_c = y_idx - center
    
    r_grid = np.sqrt(x_c**2 + y_c**2)
    
    def get_slice_mask(x_c, y_c, angle_deg):
        theta = np.radians(angle_deg)
        dist = np.abs(x_c * np.sin(theta) - y_c * np.cos(theta))
        proj = x_c * np.cos(theta) + y_c * np.sin(theta)
        return (dist < 1.2) & (proj > 0)

    if info["shape"] == "cylinder":
        mask1 = get_slice_mask(x_c, y_c, angle1)
        mask2 = get_slice_mask(x_c, y_c, angle2)
    else:
        if angle1 == 0.0: mask1 = (np.abs(y_c) < 1.0) & (x_c > 0)
        elif angle1 == 90.0: mask1 = (np.abs(x_c) < 1.0) & (y_c > 0)
        else: mask1 = get_slice_mask(x_c, y_c, 45.0)
        
        if angle2 == 0.0: mask2 = (np.abs(y_c) < 1.0) & (x_c > 0)
        elif angle2 == 90.0: mask2 = (np.abs(x_c) < 1.0) & (y_c > 0)
        else: mask2 = get_slice_mask(x_c, y_c, 45.0)
    
    # Physical coordinate arrays for the 2D plots
    x_m = np.arange(max_r_bins) * dx
    y_m = np.arange(res) * dz
    max_r_meters = max_r_bins * dx
    max_z_meters = res * dz
    
    # Calculate a smart dtick for grid lines so they stay square
    max_dim = max(max_r_meters, max_z_meters)
    if max_dim <= 1.0: dtick = 0.1
    elif max_dim <= 3.0: dtick = 0.5
    elif max_dim <= 6.0: dtick = 1.0
    else: dtick = 2.0
    
    r_bins = np.clip(np.round(r_grid).astype(int), 0, max_r_bins - 1)
    
    # --- LOAD SNAPSHOTS ---
    frames, times, avg_temps = [], [], []
    global_T_min, global_T_max = 1000.0, -1000.0

    for f in files:
        data = np.load(f)
        times.append(data["t_hr"])
        T = data["T"]
        m = data["m"]
        
        valid_cells = m > 1e-4
        if np.any(valid_cells):
            avg_temps.append(np.nanmean(T[valid_cells]))
            global_T_min = min(global_T_min, np.nanmin(T[valid_cells]))
            global_T_max = max(global_T_max, np.nanmax(T[valid_cells]))
        else:
            avg_temps.append(0.0)

    for i, f in enumerate(files):
        data = np.load(f)
        T, t_hr, m = data["T"], data["t_hr"], data["m"]
        active_mask = (m > 1e-4) & (~np.isnan(T))
        
        # 1. 3D View
        x_a = x_idx[active_mask] * dx - (res/2.0)*dx
        y_a = y_idx[active_mask] * dx - (res/2.0)*dx
        z_a = z_idx[active_mask] * dz
        T_a = T[active_mask]
        
        trace_3d = go.Scatter3d(
            x=x_a, y=y_a, z=z_a, mode='markers',
            marker=dict(size=5, color=T_a, colorscale='Inferno',
                        cmin=global_T_min, cmax=global_T_max, showscale=False, line=dict(width=0))
        )
        
        # 2. Slice 1
        m1 = active_mask & mask1
        sum_T1 = np.zeros((res, max_r_bins))
        count1 = np.zeros((res, max_r_bins))
        np.add.at(sum_T1, (z_idx[m1], r_bins[m1]), T[m1])
        np.add.at(count1, (z_idx[m1], r_bins[m1]), 1)
        heatmap_z1 = np.where(count1 > 0, sum_T1 / count1, np.nan)
        
        trace_slice1 = go.Heatmap(
            z=heatmap_z1, x=x_m, y=y_m,
            colorscale='Inferno', zmin=global_T_min, zmax=global_T_max,
            showscale=False, zsmooth='best'
        )
        
        # 3. Slice 2
        m2 = active_mask & mask2
        sum_T2 = np.zeros((res, max_r_bins))
        count2 = np.zeros((res, max_r_bins))
        np.add.at(sum_T2, (z_idx[m2], r_bins[m2]), T[m2])
        np.add.at(count2, (z_idx[m2], r_bins[m2]), 1)
        heatmap_z2 = np.where(count2 > 0, sum_T2 / count2, np.nan)
        
        trace_slice2 = go.Heatmap(
            z=heatmap_z2, x=x_m, y=y_m,
            colorscale='Inferno', zmin=global_T_min, zmax=global_T_max,
            showscale=False, zsmooth='best'
        )
        
        # 4. Current Temp Dot
        trace_temp_dot = go.Scatter(
            x=[t_hr], y=[avg_temps[i]], mode='markers',
            marker=dict(size=12, color='#00e5ff', symbol='x'), name="Current"
        )
        
        frames.append(go.Frame(
            data=[trace_3d, trace_slice1, trace_slice2, trace_temp_dot], 
            traces=[2, 3, 4, 5], name=f"t={t_hr:.2f}"
        ))

    # --- BUILD SUBPLOTS ---
    fig = make_subplots(
        rows=3, cols=2, 
        specs=[[{'type': 'scene', 'colspan': 2}, None], 
               [{'type': 'xy'}, {'type': 'xy'}], 
               [{'type': 'xy', 'colspan': 2}, None]],
        row_heights=[0.45, 0.45, 0.10],
        column_widths=[0.5, 0.5],
        subplot_titles=("3D Tank View", f"Thermal Map 1 ({angle1}°)", f"Thermal Map 2 ({angle2}°)", "Average Tank Temperature (°C)")
    )

    fig.add_trace(go.Scatter(x=times, y=avg_temps, mode='lines', name='Avg Temp', 
                             line=dict(color='#00e5ff', width=3), fill='tozeroy', fillcolor='rgba(0, 229, 255, 0.1)'), 
                  row=3, col=1)
    
    fig.add_trace(
        go.Scatter3d(x=[None], y=[None], z=[None], mode='markers',
            marker=dict(color=[global_T_min, global_T_max], colorscale='Inferno',
                        cmin=global_T_min, cmax=global_T_max, showscale=True,
                        colorbar=dict(title="Temp (°C)", x=1.05, len=0.5)),
            showlegend=False, hoverinfo='none'), row=1, col=1
    )

    fig.add_trace(frames[0].data[0], row=1, col=1)
    fig.add_trace(frames[0].data[1], row=2, col=1)
    fig.add_trace(frames[0].data[2], row=2, col=2)
    fig.add_trace(frames[0].data[3], row=3, col=1)

    # Markers
    if info.get("drain_coords"):
        fig.add_trace(go.Scatter3d(
            x=[info["drain_coords"][0] * dx - (res/2.0)*dx], y=[info["drain_coords"][1] * dx - (res/2.0)*dx], z=[info["drain_coords"][2] * dz],
            mode='markers', marker=dict(size=15, color='#ff2a75', symbol='cross', line=dict(width=2)), name='Drain'
        ), row=1, col=1)
        
    if info.get("fill_coords"):
        fig.add_trace(go.Scatter3d(
            x=[info["fill_coords"][0] * dx - (res/2.0)*dx], y=[info["fill_coords"][1] * dx - (res/2.0)*dx], z=[info["fill_coords"][2] * dz],
            mode='markers', marker=dict(size=12, color='#00ff88', symbol='circle', line=dict(width=1)), name='Fill'
        ), row=1, col=1)

    # Shells
    H_grid = res * dz
    if info["shape"] == "cylinder":
        theta = np.linspace(0, 2*np.pi, 100)
        z_grid = np.linspace(0, H_grid, 50)
        theta_mesh, z_mesh = np.meshgrid(theta, z_grid)
        
        r_mesh = np.full_like(theta_mesh, (res/2.0)*dx)
        fig.add_trace(go.Surface(
            x=r_mesh * np.cos(theta_mesh), y=r_mesh * np.sin(theta_mesh), z=z_mesh,
            opacity=0.1, colorscale=[[0, '#ffffff'], [1, '#ffffff']],
            showscale=False, hoverinfo="skip", showlegend=False
        ), row=1, col=1)
    else: 
        L = (info["tank_length"] / 2.0)
        W = (info["tank_width"] / 2.0)
        x_c = [-L, L, L, -L, -L]
        y_c = [-W, -W, W, W, -W]
        
        fig.add_trace(go.Mesh3d(x=x_c, y=y_c, z=[0]*5, opacity=0.1, color='white', showscale=False, hoverinfo="skip", showlegend=False), row=1, col=1)
        fig.add_trace(go.Mesh3d(x=x_c, y=y_c, z=[H_grid]*5, opacity=0.1, color='white', showscale=False, hoverinfo="skip", showlegend=False), row=1, col=1)
        for i in range(4):
            fig.add_trace(go.Mesh3d(x=[x_c[i], x_c[i+1], x_c[i+1], x_c[i]], y=[y_c[i], y_c[i+1], y_c[i+1], y_c[i]], 
                                    z=[0, 0, H_grid, H_grid], opacity=0.1, color='white', showscale=False, hoverinfo="skip", showlegend=False), row=1, col=1)

    # --- ANIMATION & LAYOUT ---
    fig.frames = frames
    sliders = [dict(
        active=0, currentvalue={"prefix": "Time: "}, pad={"t": 50},
        steps=[dict(method="animate", args=[[f.name], dict(mode="immediate", frame=dict(duration=0, redraw=True))], label=f.name) for f in frames]
    )]

    fig.update_layout(
        title="3D Tank Thermal Dashboard",
        template="plotly_dark", paper_bgcolor="#0b0c10", plot_bgcolor="#0b0c10",
        margin=dict(l=20, r=20, t=50, b=20),
        scene=dict(
            xaxis_title="X (m)", yaxis_title="Y (m)", zaxis_title="Z (m)", aspectmode='data',
            xaxis=dict(range=[-center*dx-0.1, center*dx+0.1]), yaxis=dict(range=[-center*dx-0.1, center*dx+0.1]), zaxis=dict(range=[0, H_grid+0.1])
        ),
        sliders=sliders, height=1100
    )
    
    # --- LOCK IN EXACT RANGES, 1:1 RATIO, AND IDENTICAL GRID TICKS ---
    # Map 1
    fig.update_xaxes(title_text="Radius (m)", range=[0, max_r_meters], constrain="domain", dtick=dtick, row=2, col=1)
    fig.update_yaxes(title_text="Height (m)", range=[0, max_z_meters], scaleanchor="x", scaleratio=1, dtick=dtick, row=2, col=1)
    
    # Map 2
    fig.update_xaxes(title_text="Radius (m)", range=[0, max_r_meters], constrain="domain", dtick=dtick, row=2, col=2)
    fig.update_yaxes(title_text="Height (m)", range=[0, max_z_meters], scaleanchor="x2", scaleratio=1, dtick=dtick, row=2, col=2)
    
    # Temp Chart
    fig.update_yaxes(title_text="Temp (°C)", row=3, col=1)

    html_path = os.path.join(run_folder, "interactive_viewer.html")
    fig.write_html(html_path, auto_open=False, include_plotlyjs='cdn')