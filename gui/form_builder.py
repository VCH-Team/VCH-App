# IO/form_builder.py
"""Reads IO.schema.SCHEMA and generates Tk widgets. Returns getters/setters
for reading the form state and updating fields programmatically."""

import tkinter as tk
from tkinter import ttk

from gui.schema import SCHEMA
from gui import pipeline_bridge as pb


def build_form(parent):
    # Scrollable canvas — the input list gets long with 7 tabs.
    # This wrapper lets the user scroll if the window is small.
    canvas = tk.Canvas(parent, highlightthickness=0)
    scroll = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
    canvas.configure(yscrollcommand=scroll.set)
    scroll.pack(side="right", fill="y")
    canvas.pack(side="left", fill="both", expand=True)

    inner = ttk.Frame(canvas)
    win = canvas.create_window((0, 0), window=inner, anchor="nw")

    # When the inner frame resizes, tell the canvas how big to be.
    def _on_configure(_):
        canvas.configure(scrollregion=canvas.bbox("all"))
        canvas.itemconfigure(win, width=canvas.winfo_width())

    inner.bind("<Configure>", _on_configure)
    canvas.bind("<Configure>", _on_configure)

    # The notebook (tabbed view). One tab per SCHEMA group.
    nb = ttk.Notebook(inner)
    nb.pack(fill="both", expand=True, padx=4, pady=4)

    # Two parallel dicts, both keyed by the schema's `key` field.
    # vars_by_key holds the tk.Variable objects (what actually stores state).
    # spec_by_key holds the schema dict (for type info during get/set).
    vars_by_key, spec_by_key = {}, {}

    for _group_key, group_label, fields in SCHEMA:
        tab = ttk.Frame(nb, padding=8)
        nb.add(tab, text=group_label)

        for spec in fields:
            key, t, default = spec["key"], spec["type"], spec["default"]
            spec_by_key[key] = spec

            # One row per field: label on the left, widget on the right.
            row = ttk.Frame(tab)
            row.pack(fill="x", pady=2)
            ttk.Label(row, text=spec["label"], anchor="w").pack(
                side="left", fill="x", expand=True)

            # Create the right widget for this field's type.
            if t == "bool":
                var = tk.BooleanVar(value=bool(default))
                ttk.Checkbutton(row, variable=var).pack(side="right")
            elif t == "choice":
                # Combobox shows labels, stores the label string.
                # get_values() converts back to the underlying value.
                reprs = [lbl for _, lbl in spec["choices"]]
                cur = next(lbl for v, lbl in spec["choices"] if v == default)
                var = tk.StringVar(value=cur)
                ttk.Combobox(row, textvariable=var, state="readonly",
                             width=18, values=reprs).pack(side="right")
            elif t == "material":
                # Options come from pipeline_bridge, based on the role
                # (fluid/metal/insulation).
                options = pb.list_for_role(spec["role"])
                default_val = default if default in options else (
                    options[0] if options else "")
                var = tk.StringVar(value=default_val)
                ttk.Combobox(row, textvariable=var, state="readonly",
                             width=24, values=options).pack(side="right")
            else:
                # float / int — plain entry, parsed on read.
                var = tk.StringVar(value=str(default))
                ttk.Entry(row, textvariable=var, width=14).pack(side="right")

            vars_by_key[key] = var

    def get_values():
        """Read all widgets → flat dict of properly-typed values.
        app.py calls this on Run click."""
        out = {}
        for key, var in vars_by_key.items():
            spec = spec_by_key[key]
            t, raw = spec["type"], var.get()
            if t == "bool":
                out[key] = bool(raw)
            elif t == "choice":
                # Map label back to underlying value.
                for v, lbl in spec["choices"]:
                    if lbl == raw:
                        out[key] = v
                        break
                else:
                    out[key] = raw
            elif t == "material":
                out[key] = raw or None
            elif t == "int":
                out[key] = int(float(raw))
            else:
                out[key] = float(raw)
        return out

    def set_value(key, value):
        """Update a field from outside (used after Phase A to fill in
        R_coil/n_turns, and by any future 'reset to defaults' button)."""
        spec = spec_by_key.get(key)
        if spec is None:
            return
        if spec["type"] == "choice":
            for v, lbl in spec["choices"]:
                if v == value:
                    vars_by_key[key].set(lbl)
                    return
        vars_by_key[key].set(str(value))

    # The widget to pack, plus the two closures.
    return inner, get_values, set_value