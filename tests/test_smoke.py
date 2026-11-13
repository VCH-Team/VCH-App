# tests/test_smoke.py
def test_imports():
    from engine.operators import heat, drain, fill, settle, flatten
    from kernel import numba_kernel_cycle
    from setup import cli, runner, grid_builder
    assert True