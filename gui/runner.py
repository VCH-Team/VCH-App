# IO/runner.py
"""Runs pipeline_bridge functions in background threads.
Without this, clicking Run would freeze the window until the sim finishes."""

import os
import threading
import traceback

from gui import pipeline_bridge as pb


def run_phase_a_job(inputs, outdir, on_done):
    """Runs Phase A on a background thread.
    on_done(payload, error) is called when finished — from the worker thread,
    so the caller must hop back to the main thread (via self.after) before
    touching any widgets."""

    def work():
        try:
            os.makedirs(outdir, exist_ok=True)

            # Load all 4 materials the sim needs (Phase A only uses mat_tank,
            # but we load all so build_cfg succeeds — it needs coil/tube/wall
            # property arrays for cfg).
            mat_tank = pb.load_material(inputs["mat_tank"])
            mat_coil = pb.load_material(inputs["mat_coil"])
            mat_tube = pb.load_material(inputs["mat_tube"])
            mat_wall = pb.load_material(inputs["mat_wall"])

            cfg = pb.build_cfg(inputs, mat_coil, mat_tube, mat_wall)

            radii, chart_path = pb.run_phase_a(
                cfg, mat_tank,
                inputs["min_R"], inputs["max_R"],
                inputs["num_R"], inputs["max_turns"],
                outdir,
            )
            on_done({"radii": radii, "chart_path": chart_path,
                     "cfg": cfg, "mat_tank": mat_tank}, None)
        except Exception as e:
            # Print full traceback to terminal (for debugging),
            # but send a compact exception to the GUI.
            traceback.print_exc()
            on_done(None, e)

    threading.Thread(target=work, daemon=True).start()


def run_3d_job(inputs, outdir, progress_cb, cancel_flag, on_done):
    """Same idea, but for the 3D run. Passes progress_cb and cancel_flag
    down to phase_3d so the GUI can update the progress bar / cancel."""

    def work():
        try:
            os.makedirs(outdir, exist_ok=True)
            mat_tank = pb.load_material(inputs["mat_tank"])
            mat_coil = pb.load_material(inputs["mat_coil"])
            mat_tube = pb.load_material(inputs["mat_tube"])
            mat_wall = pb.load_material(inputs["mat_wall"])

            cfg = pb.build_cfg(inputs, mat_coil, mat_tube, mat_wall)

            results = pb.run_3d(
                cfg, mat_tank,
                float(inputs["R_coil"]), int(inputs["n_turns"]),
                outdir,
                progress_cb=progress_cb,   # bounces progress events to the GUI
                cancel_flag=cancel_flag,   # lets Cancel button stop the run
            )
            on_done({"results": results, "outdir": outdir}, None)
        except Exception as e:
            traceback.print_exc()
            on_done(None, e)

    threading.Thread(target=work, daemon=True).start()