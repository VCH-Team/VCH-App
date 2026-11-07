# IO/dashboard.py
"""The results panel that shows up on the right side of the window.
Three states: empty, after Phase A, after 3D simulation."""

import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from gui import pipeline_bridge as pb


class Dashboard(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self._results = None
        self._outdir = None
        self._show_empty()          # start with "Run Phase A..." message

    # ── public API ────────────────────────────────────────────────
    def show_empty(self):
        """Externally-triggerable reset (unused for now, but handy)."""
        self._show_empty()

    def show_phase_a(self, radii, chart_path):
        """Called by app.py after Phase A finishes.
        Shows which radii were tested + button to open the chart PNG."""
        self._clear()

        # Header row: title + "Open chart" button.
        hdr = ttk.Frame(self)
        hdr.pack(fill="x", padx=10, pady=(10, 4))
        ttk.Label(hdr, text="Phase A — Design Chart",
                  font=("Helvetica", 14, "bold")).pack(side="left")
        ttk.Button(hdr, text="Open chart",
                   command=lambda: pb.open_path(chart_path)).pack(side="right")

        # Body: which radii were tested + where the file is.
        ttk.Label(self,
                  text=f"Radii tested (m): "
                       f"{', '.join(f'{r:.2f}' for r in radii)}",
                  foreground="#444").pack(anchor="w", padx=14, pady=6)
        ttk.Label(self, text=f"Saved to: {chart_path}",
                  foreground="#888").pack(anchor="w", padx=14)

    def show_results(self, results, outdir):
        """Called by app.py after 3D finishes.
        `results` is the dict returned by phase_3d.run_simulation."""
        self._results, self._outdir = results, outdir
        self._clear()

        # Header row: title + optional "(cancelled)" + two buttons.
        hdr = ttk.Frame(self)
        hdr.pack(fill="x", padx=10, pady=(10, 4))
        ttk.Label(hdr, text="3D Simulation — Results",
                  font=("Helvetica", 14, "bold")).pack(side="left")
        if results.get("cancelled"):
            ttk.Label(hdr, text="(cancelled)",
                      foreground="#c00").pack(side="left", padx=6)

        btns = ttk.Frame(hdr)
        btns.pack(side="right")
        ttk.Button(btns, text="Open 3D Viewer",
                   command=self._open_viewer).pack(side="left", padx=4)
        ttk.Button(btns, text="Export summary…",
                   command=self._export).pack(side="left")

        # Summary cards.
        cards = ttk.Frame(self)
        cards.pack(fill="x", padx=10, pady=6)
        self._card(cards, "Total time", f"{results.get('total_hr', 0):.2f} h")
        self._card(cards, "Extracted", f"{results.get('total_extracted_kg', 0):.1f} kg")
        self._card(cards, "Filled",    f"{results.get('total_filled_kg', 0):.1f} kg")
        self._card(cards, "Final mass", f"{results.get('final_mass', 0):.1f} kg")
        self._card(cards, "Snapshots", str(len(results.get("snapshots", []))))

        self._cycle_table(results.get("cycle_metrics", []))
        self._snapshot_list(results.get("snapshots", []))

    # ── internals ─────────────────────────────────────────────────
    def _show_empty(self):
        self._clear()
        ttk.Label(self, text="Dashboard",
                  font=("Helvetica", 16, "bold")).pack(pady=20)
        ttk.Label(self, text="Run Phase A to see the design chart, "
                             "then run the 3D simulation.",
                  foreground="#666").pack()

    def _clear(self):
        """Wipe all children so we can rebuild for a new state."""
        for w in self.winfo_children():
            w.destroy()

    def _card(self, parent, title, value):
        """One summary card: small gray title, big green number."""
        card = ttk.Frame(parent, style="Card.TFrame", padding=10)
        card.pack(side="left", padx=5, expand=True, fill="x")
        ttk.Label(card, text=title, style="CardTitle.TLabel").pack(anchor="w")
        ttk.Label(card, text=value, style="CardValue.TLabel").pack(anchor="w")

    def _cycle_table(self, cycles):
        """Treeview table with one row per cycle."""
        if not cycles:
            return
        frame = ttk.LabelFrame(self, text="Per-cycle metrics", padding=8)
        frame.pack(fill="both", expand=True, padx=10, pady=8)

        cols = ("cycle", "start", "remain", "extracted",
                "filled", "eff", "coil_out")
        heads = ("Cycle", "Start (kg)", "Remaining (kg)",
                 "Extracted (kg)", "Filled (kg)",
                 "Efficiency %", "Coil outlet (°C)")

        tree = ttk.Treeview(frame, columns=cols, show="headings",
                            height=min(len(cycles), 8))
        for c, h in zip(cols, heads):
            tree.heading(c, text=h)
            tree.column(c, width=110, anchor="center")

        for cyc in cycles:
            tree.insert("", "end", values=(
                cyc.get("cycle"),
                f"{cyc.get('start_mass', 0):.1f}",
                f"{cyc.get('remaining_mass', 0):.1f}",
                f"{cyc.get('extracted_kg', 0):.2f}",
                f"{cyc.get('filled_kg', 0):.2f}",
                f"{cyc.get('efficiency_pct', 0):.1f}",
                f"{cyc.get('extracted_temp_avg', 0):.1f}",
            ))
        tree.pack(fill="both", expand=True)

    def _snapshot_list(self, snaps):
        """Scrollable text list of snapshot file paths."""
        if not snaps:
            return
        frame = ttk.LabelFrame(self, text="Snapshots", padding=8)
        frame.pack(fill="x", padx=10, pady=(0, 10))
        txt = tk.Text(frame, height=min(len(snaps), 5), wrap="none")
        for s in snaps:
            txt.insert("end", s + "\n")
        txt.configure(state="disabled")
        txt.pack(fill="x")

    def _open_viewer(self):
        """Launches your existing viewer.py on the run folder.
        viewer.py builds the interactive Plotly HTML and opens it in a browser."""
        try:
            import viewer
            viewer.create_interactive_viewer(self._outdir)
        except Exception as e:
            messagebox.showerror("Viewer error", str(e))

    def _export(self):
        """Save the summary as a plain text file."""
        if not self._results:
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text", "*.txt"), ("All files", "*.*")],
            initialfile="simulation_summary.txt",
        )
        if not path:
            return
        try:
            with open(path, "w") as f:
                f.write(self._format(self._results))
            messagebox.showinfo("Exported", f"Saved to {path}")
        except Exception as e:
            messagebox.showerror("Export failed", str(e))

    @staticmethod
    def _format(r):
        """Plain-text summary used by _export()."""
        lines = ["PCM Tank Simulation — Summary", "=" * 40, ""]
        lines.append(f"Total time       : {r.get('total_hr', 0):.2f} h")
        lines.append(f"Total extracted  : {r.get('total_extracted_kg', 0):.2f} kg")
        lines.append(f"Total filled     : {r.get('total_filled_kg', 0):.2f} kg")
        lines.append(f"Final mass       : {r.get('final_mass', 0):.2f} kg")
        lines.append("")
        for cyc in r.get("cycle_metrics", []):
            lines.append(
                f"Cycle {cyc['cycle']}: start={cyc['start_mass']:.1f}, "
                f"remaining={cyc['remaining_mass']:.1f}, "
                f"extracted={cyc['extracted_kg']:.2f}, "
                f"filled={cyc['filled_kg']:.2f}, "
                f"eff={cyc['efficiency_pct']:.1f}%, "
                f"T_out={cyc['extracted_temp_avg']:.1f}°C")
        return "\n".join(lines) + "\n"