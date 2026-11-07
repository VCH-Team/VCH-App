# report.py
import glob
import os
import json

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Tank Simulation Report</title>
    <style>
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #121212; color: #e0e0e0; margin: 40px; }}
        h1, h2 {{ color: #ffffff; border-bottom: 1px solid #333; padding-bottom: 10px; }}
        .container {{ max-width: 1000px; margin: 0 auto; }}
        .kpi-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px; margin-bottom: 40px; }}
        .kpi-card {{ background-color: #1e1e1e; padding: 20px; border-radius: 8px; text-align: center; border-top: 4px solid #4CAF50; }}
        .kpi-value {{ font-size: 24px; font-weight: bold; color: #4CAF50; margin-top: 10px; }}
        table {{ width: 100%; border-collapse: collapse; margin-bottom: 40px; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #333; }}
        th {{ background-color: #1e1e1e; color: #bbbbbb; }}
        tr:hover {{ background-color: #252525; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Simulation Report</h1>
        
        <h2>Overall Summary</h2>
        <div class="kpi-grid">
            <div class="kpi-card">
                <div>Total Time</div>
                <div class="kpi-value">{total_hr:.1f} hr</div>
            </div>
            <div class="kpi-card">
                <div>Final Mass</div>
                <div class="kpi-value">{final_mass:.1f} kg</div>
            </div>
            <div class="kpi-card">
                <div>Total Extracted</div>
                <div class="kpi-value">{total_extracted_kg:.1f} kg</div>
            </div>
            <div class="kpi-card">
                <div>Total Filled</div>
                <div class="kpi-value">{total_filled_kg:.1f} kg</div>
            </div>
        </div>

        <h2>Cycle Breakdown</h2>
        <table>
            <thead>
                <tr>
                    <th>Cycle</th>
                    <th>Start Temp (°C)</th>
                    <th>End Temp (°C)</th>
                    <th>Mass Extracted (kg)</th>
                    <th>Efficiency (%)</th>
                    <th>Energy Added (kWh)</th>
                    <th>Energy Lost (kWh)</th>
                </tr>
            </thead>
            <tbody>
                {cycle_rows}
            </tbody>
        </table>
    </div>
</body>
</html>
"""

def generate_report(run_folder):
    json_path = os.path.join(run_folder, "results.json")
    if not os.path.exists(json_path):
        print("No results.json found. Did the simulation finish?")
        return
        
    with open(json_path, "r") as f:
        data = json.load(f)
        
    rows = ""
    for c in data["cycle_metrics"]:
        rows += f"""
        <tr>
            <td><b>Cycle {c['cycle']}</b></td>
            <td>{c['start_temp']:.1f}</td>
            <td>{c['end_temp']:.1f}</td>
            <td>{c['extracted_kg']:.1f}</td>
            <td>{c['efficiency_pct']:.1f}%</td>
            <td>{c['E_coil_kwh']:.2f}</td>
            <td>{c['E_loss_kwh']:.2f}</td>
        </tr>
        """
        
    html_content = HTML_TEMPLATE.format(
        total_hr=data["total_hr"],
        final_mass=data["final_mass"],
        total_extracted_kg=data["total_extracted_kg"],
        total_filled_kg=data["total_filled_kg"],
        cycle_rows=rows
    )
    
    out_path = os.path.join(run_folder, "report.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html_content)
        
    print(f"Report generated: {out_path}")
    os.startfile(out_path) # Automatically opens in browser on Windows

if __name__ == "__main__":
    run_folders = sorted(glob.glob("testout/run_*"))
    if not run_folders:
        print("No runs found in testout/")
    else:
        generate_report(run_folders[-1])