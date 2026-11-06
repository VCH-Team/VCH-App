# viewer.py
import glob
import os
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

def create_interactive_viewer(run_folder):
    print(f"Looking for snapshots in: {run_folder}")
    snap_dir = os.path.join(run_folder, "snapshots")
    files = sorted(glob.glob(os.path.join(snap_dir, "*.npz")))
    
    if not files:
        print("No snapshots found!"); return
        
    print(f"Found {len(files)} snapshots. Building viewer...")
    frames, times, avg_temps = [], [], []
    global_T_min, global_T_max = 1000.0, -1000.0

    for f in files:
        data = np.load(f)
        times.append(data["t_hr"])
        global_T_min = min(global_T_min, np.nanmin(data["T"]))
        global_T_max = max(global_T_max, np.nanmax(data["T"]))
        avg_temps.append(np.nanmean(data["T"]))

    res = np.load(files[0])["T"].shape[0]
    center = res / 2.0 

    for i, f in enumerate(files):
        data = np.load(f)
        T, t_hr = data["T"], data["t_hr"]
        
        # --- THE FIX IS HERE ---
        # Order must match T_3d[x, y, z]
        x, y, z = np.indices((res, res, res))
        
        m = data["m"]
        active_mask = (m > 1e-6)
        
        # Shift X and Y to center at 0, leave Z alone (height)
        x_a = x[active_mask] - center
        y_a = y[active_mask] - center
        z_a = z[active_mask]
        T_a = T[active_mask]
        
        trace_3d = go.Scatter3d(
            x=x_a, y=y_a, z=z_a, mode='markers',
            marker=dict(
                size=4, color=T_a, colorscale='Inferno',
                cmin=global_T_min, cmax=global_T_max,
                showscale=True if i == 0 else False,
                colorbar=dict(title="Temp (°C)", x=1.0, len=0.7)
            )
        )
        
        trace_2d = go.Scatter(
            x=[t_hr], y=[avg_temps[i]], mode='markers',
            marker=dict(size=12, color='red', symbol='x'), name="Current"
        )
        
        frames.append(go.Frame(data=[trace_3d, trace_2d], traces=[1, 2], name=f"t={t_hr:.2f}"))

    fig = make_subplots(
        rows=2, cols=1, specs=[[{'type': 'scene'}], [{'type': 'xy'}]],
        row_heights=[0.7, 0.3],
        subplot_titles=("3D Tank View", "Average Tank Temperature")
    )

    fig.add_trace(go.Scatter(x=times, y=avg_temps, mode='lines', name='Avg Temp', line=dict(color='orange')), row=2, col=1)
    fig.add_trace(frames[0].data[0], row=1, col=1)
    fig.add_trace(frames[0].data[1], row=2, col=1)

    # Ghost cylinder
    theta = np.linspace(0, 2*np.pi, 100)
    z_wall = np.linspace(0, res, 100)
    theta_mesh, z_mesh = np.meshgrid(theta, z_wall)
    
    r_mesh = np.full_like(theta_mesh, (res/2) - 1)
    x_wall = r_mesh * np.cos(theta_mesh)
    y_wall = r_mesh * np.sin(theta_mesh)

    fig.add_trace(
        go.Surface(
            x=x_wall, y=y_wall, z=z_mesh,
            opacity=0.1, colorscale=[[0, 'gray'], [1, 'gray']],
            showscale=False, name="Tank Wall", hoverinfo="skip"
        ),
        row=1, col=1
    )

    fig.frames = frames
    sliders = [dict(
        active=0, currentvalue={"prefix": "Time: "}, pad={"t": 50},
        steps=[dict(method="animate", args=[[f.name], dict(mode="immediate", frame=dict(duration=0, redraw=True))], label=f.name) for f in frames]
    )]

    # LOCK AXES
    fig.update_layout(
        title="3D Tank Thermal Dashboard",
        scene=dict(
            xaxis_title="X", yaxis_title="Y", zaxis_title="Z (Height)", 
            aspectmode='cube',
            xaxis=dict(range=[-center, center]),
            yaxis=dict(range=[-center, center]),
            zaxis=dict(range=[0, res])
        ),
        sliders=sliders, width=1000, height=900
    )

    html_path = os.path.join(run_folder, "interactive_viewer.html")
    fig.write_html(html_path, auto_open=True)
    print(f"Viewer saved to: {html_path}")

if __name__ == "__main__":
    run_folders = sorted(glob.glob("testout/run_*"))
    if not run_folders: print("No runs found in testout/")
    else: create_interactive_viewer(run_folders[-1])