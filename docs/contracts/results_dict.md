# Contract: Simulation Results Dictionary

This defines the structure of the dictionary returned by un_simulation() so the UI/CE team can build mocks against it immediately.

## Expected Keys
- T_mean: float — Mean temperature across the tank volume
- T_min: float — Minimum temperature
- T_max: float — Maximum temperature
- m_total: float — Total mass / fluid mass
- cycle_metrics: dict — Performance metrics for the current cycle
- snapshots: list of str — File paths to generated .npz state snapshots
