# IO/dashboard.py
import os
import webbrowser

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>VCH Simulation Dashboard</title>
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;800&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-color: #08090a;
            --tab-bg: rgba(255, 255, 255, 0.03);
            --border-color: rgba(255, 255, 255, 0.08);
            --cyan: #00e5ff;
            --text-main: #f0f0f0;
            --text-muted: #8892b0;
        }

        body {
            font-family: 'Poppins', sans-serif;
            background-color: var(--bg-color);
            color: var(--text-main);
            margin: 0;
            padding: 0;
            height: 100vh;
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }

        .header {
            text-align: center;
            padding: 20px;
            background: linear-gradient(180deg, rgba(0,0,0,0.8) 0%, rgba(8,9,10,0) 100%);
            z-index: 10;
        }

        h1 {
            font-weight: 800;
            font-size: 1.8rem;
            margin: 0;
            background: -webkit-linear-gradient(45deg, var(--cyan), #ff2a75);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            letter-spacing: 1px;
        }

        .subtitle {
            font-size: 0.9rem;
            color: var(--text-muted);
            margin-top: 5px;
        }

        /* Tab Container */
        .tab-container {
            display: flex;
            justify-content: center;
            gap: 15px;
            padding: 10px 20px;
            z-index: 10;
        }

        .tab-btn {
            background: var(--tab-bg);
            border: 1px solid var(--border-color);
            color: var(--text-muted);
            padding: 12px 30px;
            border-radius: 30px;
            font-family: inherit;
            font-size: 1rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
            backdrop-filter: blur(10px);
        }

        .tab-btn:hover {
            color: var(--text-main);
            border-color: rgba(0, 229, 255, 0.4);
            box-shadow: 0 0 15px rgba(0, 229, 255, 0.1);
        }

        .tab-btn.active {
            background: rgba(0, 229, 255, 0.1);
            color: var(--cyan);
            border-color: var(--cyan);
            box-shadow: 0 0 20px rgba(0, 229, 255, 0.3);
        }

        /* Content Area */
        .content-area {
            flex-grow: 1;
            position: relative;
            width: 100%;
        }

        .tab-content {
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            opacity: 0;
            pointer-events: none;
            transition: opacity 0.4s ease;
        }

        .tab-content.active {
            opacity: 1;
            pointer-events: auto;
        }

        iframe {
            width: 100%;
            height: 100%;
            border: none;
            background-color: transparent;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>VCH SIMULATION DASHBOARD</h1>
        <div class="subtitle">{subtitle}</div>
    </div>

    <div class="tab-container">
        <button class="tab-btn active" onclick="openTab('viewer', this)">3D Interactive View</button>
        <button class="tab-btn" onclick="openTab('report', this)">Telemetry Report</button>
    </div>

    <div class="content-area">
        <div id="viewer" class="tab-content active">
            <iframe src="interactive_viewer.html"></iframe>
        </div>
        <div id="report" class="tab-content">
            <iframe src="report.html"></iframe>
        </div>
    </div>

    <script>
        function openTab(tabName, btnElement) {
            // Hide all tabs
            var contents = document.getElementsByClassName("tab-content");
            for (var i = 0; i < contents.length; i++) {
                contents[i].classList.remove("active");
            }
            
            // Deactivate all buttons
            var btns = document.getElementsByClassName("tab-btn");
            for (var i = 0; i < btns.length; i++) {
                btns[i].classList.remove("active");
            }
            
            // Show selected tab
            document.getElementById(tabName).classList.add("active");
            btnElement.classList.add("active");
        }
    </script>
</body>
</html>
"""

def create_dashboard(folder_path, title_context="Simulation Run"):
    """Generates a unified tabbed dashboard for a specific folder."""
    # Ensure both files exist
    viewer_file = os.path.join(folder_path, "interactive_viewer.html")
    report_file = os.path.join(folder_path, "report.html")
    
    if not os.path.exists(viewer_file):
        print(f"Warning: {viewer_file} not found. Skipping 3D viewer tab.")
    if not os.path.exists(report_file):
        print(f"Warning: {report_file} not found. Skipping report tab.")
        
    html_content = HTML_TEMPLATE.replace("{subtitle}", title_context)
    
    out_path = os.path.join(folder_path, "dashboard.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html_content)
        
    print(f"Unified Dashboard generated: {out_path}")
    webbrowser.open('file://' + os.path.realpath(out_path))