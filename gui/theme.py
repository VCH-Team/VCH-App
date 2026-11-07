from tkinter import ttk


def apply(root):
    style = ttk.Style(root)
    # "clam" is the only built-in theme that looks decent on Linux/Windows/Mac.
    # If it's not available, silently fall back to default.
    try:
        style.theme_use("clam")
    except Exception:
        pass

    # Custom styles used by the dashboard summary cards.
    # These are referenced in dashboard.py as style="Card.TFrame", etc.
    style.configure("Card.TFrame", background="#f4f5f7", relief="flat")
    style.configure("CardTitle.TLabel", background="#f4f5f7",
                    font=("Helvetica", 9), foreground="#555")
    style.configure("CardValue.TLabel", background="#f4f5f7",
                    font=("Helvetica", 18, "bold"), foreground="#1a7f37")