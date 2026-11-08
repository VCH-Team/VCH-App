"""Same viewer as the root viewer.py, but it only writes the HTML (no browser pop-up)
and returns the path so the dashboard can embed it."""
import glob
import json
import os

import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots


def build_viewer_html(run_folder, shape="cylinder"):
    files = sorted(glob.glob(os.path.join(run_folder, "snapshots", "*.npz")))
    if not files:
        return None

    drain_coords = fill_coords = None
    info_path = os.path.join(run_folder, "run_info.json")
    if os.path.exists(info_path):
        with open(info_path, "r") as f:
            info = json.load(f)
        drain_coords, fill_coords = info.get("drain_coords"), info.get("fill_coords")

    times, avg_temps = [], []
    t_min, t_max = 1000.0, -1000.0
    for f in files:
        with np.load(f) as d:
            times.append(float(d["t_hr"]))
            t_min = min(t_min, float(np.nanmin(d["T"])))
            t_max = max(t_max, float(np.nanmax(d["T"])))
            avg_temps.append(float(np.nanmean(d["T"])))

    with np.load(files[0]) as d:
        res = d["T"].shape[0]
    center = res / 2.0
    x, y, z = np.indices((res, res, res))

    frames = []
    for i, f in enumerate(files):
        with np.load(f) as d:
            T, m, t_hr = d["T"], d["m"], float(d["t_hr"])
        mask = m > 1e-6
        trace_3d = go.Scatter3d(
            x=x[mask] - center, y=y[mask] - center, z=z[mask], mode="markers",
            marker=dict(size=4, color=T[mask], colorscale="Inferno", cmin=t_min, cmax=t_max,
                        showscale=(i == 0), colorbar=dict(title="Temp (°C)", x=1.0, len=0.7)))
        trace_2d = go.Scatter(x=[t_hr], y=[avg_temps[i]], mode="markers",
                              marker=dict(size=12, color="red", symbol="x"), name="Current")
        frames.append(go.Frame(data=[trace_3d, trace_2d], traces=[1, 2], name=f"t={t_hr:.2f}"))

    fig = make_subplots(rows=2, cols=1, specs=[[{"type": "scene"}], [{"type": "xy"}]],
                        row_heights=[0.7, 0.3],
                        subplot_titles=("3D Tank View", "Average Tank Temperature"))
    fig.add_trace(go.Scatter(x=times, y=avg_temps, mode="lines", name="Avg Temp",
                             line=dict(color="orange")), row=2, col=1)
    fig.add_trace(frames[0].data[0], row=1, col=1)
    fig.add_trace(frames[0].data[1], row=2, col=1)

    if drain_coords:
        fig.add_trace(go.Scatter3d(
            x=[drain_coords[0] - center], y=[drain_coords[1] - center], z=[drain_coords[2]],
            mode="markers", marker=dict(size=15, color="red", symbol="cross", line=dict(width=2)),
            name="Drain"), row=1, col=1)
    if fill_coords:
        fig.add_trace(go.Scatter3d(
            x=[fill_coords[0] - center], y=[fill_coords[1] - center], z=[fill_coords[2]],
            mode="markers", marker=dict(size=12, color="blue", symbol="circle", line=dict(width=1)),
            name="Fill"), row=1, col=1)

    if shape == "cylinder":
        theta, z_wall = np.meshgrid(np.linspace(0, 2 * np.pi, 100), np.linspace(0, res, 100))
        r_wall = (res / 2) - 1
        fig.add_trace(go.Surface(
            x=r_wall * np.cos(theta), y=r_wall * np.sin(theta), z=z_wall, opacity=0.1,
            colorscale=[[0, "gray"], [1, "gray"]], showscale=False, name="Tank Wall",
            hoverinfo="skip"), row=1, col=1)

    fig.frames = frames
    sliders = [dict(
        active=0, currentvalue={"prefix": "Time: "}, pad={"t": 50},
        steps=[dict(method="animate", label=fr.name,
                    args=[[fr.name], dict(mode="immediate", frame=dict(duration=0, redraw=True))])
               for fr in frames])]
    fig.update_layout(
        title="3D Tank Thermal Dashboard", template="plotly_dark", height=860, sliders=sliders,
        scene=dict(xaxis_title="X", yaxis_title="Y", zaxis_title="Z (Height)", aspectmode="cube",
                   xaxis=dict(range=[-center, center]), yaxis=dict(range=[-center, center]),
                   zaxis=dict(range=[0, res])))

    html_path = os.path.join(run_folder, "interactive_viewer.html")
    fig.write_html(html_path, auto_open=False, include_plotlyjs=True,
                   default_width="100%", default_height="860px")
    return html_path