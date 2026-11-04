# physics/__init__.py
import os
os.environ["NUMBA_NUM_THREADS"] = "6"
import numba
numba.set_num_threads(6)