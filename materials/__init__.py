import os
import hashlib
import pandas as pd
import numpy as np
import matplotlib

def _cache_valid(cache_file, current_hash):
    if not os.path.exists(cache_file):
        return False
    try:
        data = np.load(cache_file, allow_pickle=True)
        if str(data['hash']) != current_hash:
            return False
        if 'fs_grid' not in data.files:          # ← new line
            return False                          # old cache, regenerate
        return True
    except:
        return False