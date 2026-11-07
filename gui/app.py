# IO/app.py
"""The main window. Left half: input form. Right half: dashboard.
Bottom strip: Run/Cancel buttons + progress bar."""

import os
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime

from .form_builder import build_form
from .dashboard import Dashboard
from .runner import run_phase_a_job, run_3d_job
from . import theme


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("PCM Tank Simulator")
        self.geometry("1500x920")
        theme.apply(self)
        self.outdir = None             # one output folder shared by Phase A + 3D
        self.cancel_flag = None        # threading.Event, set by Cancel button
        self._build()

    def _build(self):
        # ── bottom strip: progress bar + status text ────────────────
        self.status_var = tk.StringVar(value="Ready.")
        self.progress_var = tk.DoubleVar(value=0.0)

        bottom = ttk.Frame(self)
        bottom.pack(side="bottom", fill="x", padx=8, pady=4)
        ttk.Progressbar(bottom, variable=self.progress_var,
                        maximum=100).pack(side="left", fill="x", expand=True)
        ttk.Label(bottom, textvariable=self.status_var,
                  anchor="w", width=55).pack(side="left", padx=(8, 0))

        # ── split view: inputs left, dashboard right ────────────────
        pane = ttk.PanedWindow(self, orient="horizontal")
        pane.pack(fill="both", expand=True, padx=6, pady=6)

        # LEFT side: input form + button row
        left = ttk.Frame(pane)
        pane.add(left, weight=0)

        btn_row = ttk.Frame(left)
        btn_row.pack(side="bottom", fill="x", padx=4, pady=(0, 4))
        self.phase_a_btn = ttk.Button(btn_row, text="Run Phase A",
                                      command=self._on_phase_a)
        self.phase_a_btn.pack(side="left", expand=True, fill="x")
        self.run_btn = ttk.Button(btn_row, text="Run 3D Simulation",
                                  command=self._on_run_3d)
        self.run_btn.pack(side="left", expand=True, fill="x", padx=(6, 0))
        self.cancel_btn = ttk.Button(btn_row, text="Cancel",
                                     command=self._on_cancel, state="disabled")
        self.cancel_btn.pack(side="left", padx=(6, 0))

        content = ttk.Frame(left)
        content.pack(side="top", fill="both", expand=True)
        # build_form returns three things:
        #   widget (packed into content), get_values(), set_value()
        _, self.get_values, self.set_value = build_form(content)

        # RIGHT side: dashboard
        right = ttk.Frame(pane)
        pane.add(right, weight=1)
        self.dashboard = Dashboard(right)
        self.dashboard.pack(fill="both", expand=True)

    # ── helpers ───────────────────────────────────────────────────
    def _ensure_outdir(self):
        """Lazily create a run folder on first Run click.
        Both Phase A and 3D write into the same folder."""
        if self.outdir and os.path.isdir(self.outdir):
            return self.outdir
        self.outdir = os.path.join(
            "testout", datetime.now().strftime("run_%Y%m%d_%H%M%S"))
        os.makedirs(self.outdir, exist_ok=True)
        return self.outdir

    def _busy(self, busy):
        """Toggle button enable states during a run."""
        state = "disabled" if busy else "normal"
        self.phase_a_btn.config(state=state)
        self.run_btn.config(state=state)
        self.cancel_btn.config(state="normal" if busy else "disabled")

    # ── button handlers ───────────────────────────────────────────
    def _on_phase_a(self):
        # 1. Read form; if a value isn't a number, show an error and bail.
        try:
            inputs = self.get_values()
        except Exception as e:
            messagebox.showerror("Invalid inputs", str(e))
            return

        # 2. Prepare the run folder + disable buttons during the job.
        outdir = self._ensure_outdir()
        self._busy(True)
        self.status_var.set("Running Phase A…")
        self.progress_var.set(0)

        # 3. Callback that runs on the WORKER thread when Phase A finishes.
        def done(payload, error):
            # Wrap in self.after(0, ...) so widget updates happen on main thread.
            def _finish():
                self._busy(False)
                if error:
                    self.status_var.set("Phase A failed.")
                    messagebox.showerror("Phase A failed", str(error))
                    return

                # Auto-fill the Coil Selection tab so the user can
                # immediately click Run 3D without editing anything.
                radii = payload["radii"]
                self.set_value("R_coil", round(radii[-1], 3))
                self.set_value("max_turns", inputs["max_turns"])
                self.set_value("n_turns", max(1, inputs["max_turns"] // 2))

                # Show Phase A results in the dashboard.
                self.dashboard.show_phase_a(radii, payload["chart_path"])
                self.status_var.set(
                    f"Phase A done. {len(radii)} radii charted. "
                    f"Pick R_coil + n_turns, then Run 3D.")
            self.after(0, _finish)

        # 4. Kick off the background thread.
        run_phase_a_job(inputs, outdir, done)

    def _on_run_3d(self):
        try:
            inputs = self.get_values()
        except Exception as e:
            messagebox.showerror("Invalid inputs", str(e))
            return

        outdir = self._ensure_outdir()
        self._busy(True)
        self.status_var.set("Running 3D simulation…")
        self.progress_var.set(0)
        # Fresh Event each run so Cancel works per-run, not globally.
        self.cancel_flag = threading.Event()

        # phase_3d calls this from its inner loop, once per N steps.
        def progress(evt):
            self.after(0, lambda: (
                self.status_var.set(
                    f"Running… t = {evt.get('t_hr', 0):.2f} h "
                    f"({evt.get('pct', 0):.1f}%)"),
                self.progress_var.set(evt.get("pct", 0.0)),
            ))

        def done(payload, error):
            def _finish():
                self._busy(False)
                if error:
                    self.status_var.set("3D simulation failed.")
                    messagebox.showerror("3D simulation failed", str(error))
                    return
                r = payload["results"]
                if r.get("cancelled"):
                    self.status_var.set(
                        f"Cancelled. Partial = {r['total_hr']:.2f} h.")
                else:
                    self.progress_var.set(100)
                    self.status_var.set(
                        f"Done. {r['total_hr']:.2f} h, "
                        f"{r['total_extracted_kg']:.1f} kg extracted.")
                self.dashboard.show_results(r, payload["outdir"])
            self.after(0, _finish)

        run_3d_job(inputs, outdir, progress, self.cancel_flag, done)

    def _on_cancel(self):
        # Sets the Event that phase_3d.run_simulation checks each step.
        if self.cancel_flag:
            self.cancel_flag.set()
            self.status_var.set("Cancelling…")


def launch():
    App().mainloop()