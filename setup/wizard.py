# setup/wizard.py
import os
from datetime import datetime

from setup import cli, runner

def main():
    print("=== 3D TANK SIMULATION WIZARD (NEXT-GEN KERNEL) ===")
    
    # 1. Create Output Directory
    outdir = os.path.join("testout", f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    os.makedirs(outdir, exist_ok=True)
    
    # 2. Gather User Inputs (Handled by cli.py)
    # Returns the config, materials, coil choices, and geometric metrics
    cfg, mat_tank, mat_coil, mat_tube, mat_wall, R_coil, n_turns, slice_angles, weight_tube, L_total = cli.get_user_inputs(outdir)
    
    # 3. Run the Simulation (Handled by runner.py)
    # Runs the Numba loop, handles memory, and generates reports
    runner.run_simulation(
        cfg, mat_tank, mat_coil, mat_tube, mat_wall, 
        R_coil, n_turns, slice_angles, weight_tube, L_total, outdir
    )

if __name__ == "__main__":
    main()