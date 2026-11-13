# IO/report.py
import os
import json

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Tank Simulation Dashboard</title>
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600;800&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg-color: #08090a;
            --card-bg: rgba(255, 255, 255, 0.03);
            --border-color: rgba(255, 255, 255, 0.08);
            --cyan: #00e5ff;
            --yellow: #ffea00;
            --pink: #ff2a75;
            --green: #00ff88;
            --blue: #5C6BC0;
            --text-main: #f0f0f0;
            --text-muted: #8892b0;
        }}

        body {{
            font-family: 'Poppins', sans-serif;
            background-color: var(--bg-color);
            background-image: radial-gradient(circle at 15% 50%, rgba(0, 229, 255, 0.04) 0%, transparent 50%),
                              radial-gradient(circle at 85% 30%, rgba(255, 42, 117, 0.04) 0%, transparent 50%);
            color: var(--text-main);
            margin: 0;
            padding: 40px 20px;
            min-height: 100vh;
        }}

        .container {{
            max-width: 1100px;
            margin: 0 auto;
        }}

        h1 {{
            font-weight: 800;
            font-size: 2.5rem;
            text-align: center;
            margin-bottom: 50px;
            background: -webkit-linear-gradient(45deg, var(--cyan), var(--pink));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            letter-spacing: 1px;
        }}

        h2 {{
            font-weight: 600;
            font-size: 1.4rem;
            color: var(--text-main);
            margin-top: 40px;
            margin-bottom: 20px;
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        
        h2::before {{
            content: '';
            display: block;
            width: 4px;
            height: 24px;
            background: var(--cyan);
            border-radius: 2px;
            box-shadow: 0 0 10px var(--cyan);
        }}

        .kpi-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 20px;
            margin-bottom: 40px;
        }}

        .kpi-card {{
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 16px;
            padding: 25px;
            text-align: center;
            backdrop-filter: blur(10px);
            transition: transform 0.3s ease, box-shadow 0.3s ease;
        }}

        .kpi-card:hover {{
            transform: translateY(-5px);
            box-shadow: 0 10px 30px rgba(0, 229, 255, 0.1);
            border-color: rgba(0, 229, 255, 0.3);
        }}

        .kpi-label {{
            font-size: 0.85rem;
            text-transform: uppercase;
            letter-spacing: 2px;
            color: var(--text-muted);
            margin-bottom: 10px;
        }}

        .kpi-value {{
            font-size: 2rem;
            font-weight: 800;
            color: var(--cyan);
            text-shadow: 0 0 20px rgba(0, 229, 255, 0.3);
        }}

        .kpi-unit {{ font-size: 1rem; font-weight: 400; color: var(--text-muted); }}

        .cycle-card {{
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 20px;
            padding: 30px;
            margin-bottom: 30px;
            backdrop-filter: blur(10px);
        }}

        .cycle-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 25px;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 15px;
        }}

        .cycle-title {{
            font-size: 1.5rem;
            font-weight: 800;
            color: var(--yellow);
            text-shadow: 0 0 15px rgba(255, 234, 0, 0.3);
        }}

        .cycle-temps {{
            font-size: 1rem;
            color: var(--text-muted);
            font-weight: 600;
        }}
        .cycle-temps span {{ color: var(--text-main); }}

        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 15px;
            margin-bottom: 25px;
        }}

        .metric-box {{
            background: rgba(0, 0, 0, 0.2);
            border-radius: 12px;
            padding: 15px;
            text-align: center;
            border: 1px solid rgba(255, 255, 255, 0.03);
        }}

        .metric-label {{
            font-size: 0.75rem;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 5px;
        }}

        .metric-value {{ font-size: 1.2rem; font-weight: 600; }}

        .val-drained {{ color: var(--pink); text-shadow: 0 0 10px rgba(255, 42, 117, 0.2); }}
        .val-filled {{ color: var(--cyan); text-shadow: 0 0 10px rgba(0, 229, 255, 0.2); }}
        .val-util {{ color: var(--green); text-shadow: 0 0 10px rgba(0, 255, 136, 0.2); }}
        .val-dtemp {{ color: var(--yellow); text-shadow: 0 0 10px rgba(255, 234, 0, 0.2); }}

        .phase-container {{ margin-top: 20px; }}
        .phase-bar-wrapper {{
            height: 16px;
            width: 100%;
            background: rgba(255, 255, 255, 0.05);
            border-radius: 10px;
            display: flex;
            overflow: hidden;
            box-shadow: inset 0 2px 5px rgba(0,0,0,0.5);
        }}

        .phase-solid {{ background: var(--blue); box-shadow: 0 0 10px var(--blue); }}
        .phase-slurry {{ background: var(--yellow); box-shadow: 0 0 10px var(--yellow); }}
        .phase-liquid {{ background: var(--pink); box-shadow: 0 0 10px var(--pink); }}

        .phase-legend {{
            display: flex;
            justify-content: space-between;
            margin-top: 12px;
            font-size: 0.85rem;
            color: var(--text-muted);
        }}
        .legend-item {{ display: flex; align-items: center; gap: 8px; }}
        .legend-color {{ width: 10px; height: 10px; border-radius: 50%; }}

        .matrix-table {{
            width: 100%;
            border-collapse: separate;
            border-spacing: 0 10px;
            margin-top: 10px;
        }}
        .matrix-table th {{
            text-align: left;
            padding: 15px;
            font-size: 0.85rem;
            text-transform: uppercase;
            letter-spacing: 1px;
            color: var(--cyan);
            border-bottom: 1px solid var(--border-color);
        }}
        .matrix-table td {{
            padding: 15px;
            background: var(--card-bg);
            border-top: 1px solid var(--border-color);
            border-bottom: 1px solid var(--border-color);
        }}
        .matrix-table tr td:first-child {{
            border-left: 1px solid var(--border-color);
            border-top-left-radius: 12px;
            border-bottom-left-radius: 12px;
            font-weight: 800;
            color: var(--yellow);
        }}
        .matrix-table tr td:last-child {{
            border-right: 1px solid var(--border-color);
            border-top-right-radius: 12px;
            border-bottom-right-radius: 12px;
        }}
        .matrix-table tr:hover td {{
            background: rgba(0, 229, 255, 0.05);
            border-color: rgba(0, 229, 255, 0.3);
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>SIMULATION DASHBOARD</h1>
        
        <h2>System Overview</h2>
        <div class="kpi-grid">
            <div class="kpi-card">
                <div class="kpi-label">Total Runtime</div>
                <div class="kpi-value">{total_hr:.1f}<span class="kpi-unit"> hr</span></div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">Final Mass</div>
                <div class="kpi-value">{final_mass:,.1f}<span class="kpi-unit"> kg</span></div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">Total Drained</div>
                <div class="kpi-value" style="color: var(--pink); text-shadow: 0 0 20px rgba(255, 42, 117, 0.3);">{total_extracted_kg:,.1f}<span class="kpi-unit"> kg</span></div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">Total Filled</div>
                <div class="kpi-value" style="color: var(--cyan); text-shadow: 0 0 20px rgba(0, 229, 255, 0.3);">{total_filled_kg:,.1f}<span class="kpi-unit"> kg</span></div>
            </div>
        </div>

        <h2>Cycle Analysis</h2>
        {cycle_html}
        
        <h2>Telemetry Matrix</h2>
        <table class="matrix-table">
            <thead>
                <tr>
                    <th>Cycle</th>
                    <th>Avg Temp (°C)</th>
                    <th>Coil Energy (kWh)</th>
                    <th>Heat Loss (kWh)</th>
                </tr>
            </thead>
            <tbody>
                {matrix_rows}
            </tbody>
        </table>
    </div>
</body>
</html>
"""

def generate_report(run_folder):
    json_path = os.path.join(run_folder, "results.json")
    if not os.path.exists(json_path):
        print(f"  No results.json found in {run_folder}.")
        return
        
    with open(json_path, "r") as f:
        data = json.load(f)
        
    cycle_html = ""
    matrix_rows = ""
    
    for c in data["cycle_metrics"]:
        pd = c.get("phase_distribution", {"solid_pct": 0, "slurry_pct": 0, "liquid_pct": 0})
        solid = pd.get("solid_pct", 0)
        slurry = pd.get("slurry_pct", 0)
        liquid = pd.get("liquid_pct", 0)
        
        cycle_html += f"""
        <div class="cycle-card">
            <div class="cycle-header">
                <div class="cycle-title">CYCLE {c.get('cycle', '?')}</div>
                <div class="cycle-temps">Start: <span>{c.get('start_temp', 0.0):.1f}°C</span> &rarr; End: <span>{c.get('end_temp', 0.0):.1f}°C</span></div>
            </div>
            
            <div class="metrics-grid">
                <div class="metric-box">
                    <div class="metric-label">Drained</div>
                    <div class="metric-value val-drained">{c.get('drained_kg', 0.0):,.1f} kg</div>
                </div>
                <div class="metric-box">
                    <div class="metric-label">Filled</div>
                    <div class="metric-value val-filled">{c.get('filled_kg', 0.0):,.1f} kg</div>
                </div>
                <div class="metric-box">
                    <div class="metric-label">Utilisation</div>
                    <div class="metric-value val-util">{c.get('efficiency_pct', 0.0):.1f}%</div>
                </div>
                <div class="metric-box">
                    <div class="metric-label">Drain Temp</div>
                    <div class="metric-value val-dtemp">{c.get('drain_temp', 0.0):.1f}°C</div>
                </div>
            </div>

            <div class="phase-container">
                <div class="phase-bar-wrapper">
                    <div class="phase-solid" style="width: {solid}%;" title="Solid: {solid:.1f}%"></div>
                    <div class="phase-slurry" style="width: {slurry}%;" title="Slurry: {slurry:.1f}%"></div>
                    <div class="phase-liquid" style="width: {liquid}%;" title="Liquid: {liquid:.1f}%"></div>
                </div>
                <div class="phase-legend">
                    <div class="legend-item"><div class="legend-color" style="background: var(--blue);"></div> Solid ({solid:.1f}%)</div>
                    <div class="legend-item"><div class="legend-color" style="background: var(--yellow);"></div> Slurry ({slurry:.1f}%)</div>
                    <div class="legend-item"><div class="legend-color" style="background: var(--pink);"></div> Liquid ({liquid:.1f}%)</div>
                </div>
            </div>
        </div>
        """
        
        matrix_rows += f"""
        <tr>
            <td>Cycle {c.get('cycle', '?')}</td>
            <td>{c.get('avg_temp', 0.0):.1f} °C</td>
            <td style="color: var(--green);">{c.get('E_coil_kwh', 0.0):.2f} kWh</td>
            <td style="color: var(--pink);">{c.get('E_loss_kwh', 0.0):.2f} kWh</td>
        </tr>
        """
        
    html_content = HTML_TEMPLATE.format(
        total_hr=data.get("total_hr", 0.0),
        final_mass=data.get("final_mass", 0.0),
        total_extracted_kg=data.get("total_extracted_kg", 0.0),
        total_filled_kg=data.get("total_filled_kg", 0.0),
        cycle_html=cycle_html,
        matrix_rows=matrix_rows
    )
    
    out_path = os.path.join(run_folder, "report.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html_content)
        
    print(f"  Report generated: {out_path}")
    # Note: webbrowser.open() is removed. The dashboard will handle opening.