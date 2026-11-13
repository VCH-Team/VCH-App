import os
import sqlite3
import hashlib
import numpy as np
import pandas as pd
from scipy.interpolate import PchipInterpolator
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, 'data', 'VCH_Data.db')
CACHE_DIR = os.path.join(BASE_DIR, 'setup', 'cache')
PLOTS_DIR = os.path.join(BASE_DIR, 'data', 'plots')

def get_db_hash():
    if not os.path.exists(DB_PATH):
        raise FileNotFoundError(f"Database not found at {DB_PATH}. Please run the SQL script first.")
    with open(DB_PATH, 'rb') as f:
        return hashlib.md5(f.read()).hexdigest()

def _fit_material(df, T_min=-50.0, T_max=200.0, n_points=400):
    df = df.sort_values('Temperature_C').drop_duplicates('Temperature_C')
    T_data = df['Temperature_C'].values.astype(float)
    T_grid = np.linspace(T_min, T_max, n_points)

    def fit_col(col_name, default_val, log_space=False):
        if col_name not in df.columns: return np.full(n_points, default_val)
        y = df[col_name].values.astype(float)
        if log_space: y = np.log(np.maximum(y, 1e-6))
        f = PchipInterpolator(T_data, y)
        res = f(T_grid)
        if log_space: res = np.exp(res)
        return res

    rho_grid = fit_col('Density_kgm3', 1000.0)
    cp_sens_grid = fit_col('Cp_JkgK', 1000.0)
    k_grid = fit_col('k_WmK', 1.0)
    mu_grid = fit_col('Viscosity_Pas', 1e5, log_space=True)
    
    if 'Latent_kJkg' in df.columns:
        latent_J = df['Latent_kJkg'].values.astype(float) * 1000.0
        f_lat = PchipInterpolator(T_data, latent_J)
        latent_grid = f_lat(T_grid)
    else:
        latent_grid = np.zeros(n_points)

    T_ms, T_me = np.nan, np.nan
    if 'Phase' in df.columns:
        solid_df = df[df['Phase'] == 'Solid']
        liquid_df = df[df['Phase'].isin(['Liquid', 'Gas'])]
        if not solid_df.empty and not liquid_df.empty:
            T_ms = solid_df['Temperature_C'].max()
            T_me = liquid_df['Temperature_C'].min()
            if T_me - T_ms < 0.5: T_ms -= 0.1; T_me += 0.1
        elif not solid_df.empty:
            T_ms = solid_df['Temperature_C'].max(); T_me = T_ms
        elif not liquid_df.empty:
            T_ms = liquid_df['Temperature_C'].min(); T_me = T_ms
            
    dLdT = np.abs(np.gradient(latent_grid, T_grid))
    cp_eff_grid = cp_sens_grid + dLdT
    min_cp = 0.05 * cp_sens_grid
    cp_eff_grid = np.maximum(cp_eff_grid, min_cp)
    
    H_grid = np.zeros(n_points)
    for i in range(1, n_points):
        cp_mid = 0.5 * (cp_eff_grid[i-1] + cp_eff_grid[i])
        H_grid[i] = H_grid[i-1] + cp_mid * (T_grid[i] - T_grid[i-1])
    H_grid -= H_grid[0]
    
    fs_grid = np.zeros(n_points)
    if not np.isnan(T_ms) and not np.isnan(T_me):
        below, above = T_grid <= T_ms, T_grid >= T_me
        between = ~(below | above)
        fs_grid[below], fs_grid[above] = 1.0, 0.0
        if T_me > T_ms: fs_grid[between] = (T_me - T_grid[between]) / (T_me - T_ms)
    
    return {
        'T_grid': T_grid, 'rho_grid': rho_grid, 'cp_sens_grid': cp_sens_grid,
        'cp_eff_grid': cp_eff_grid, 'k_grid': k_grid, 'mu_grid': mu_grid,
        'H_grid': H_grid, 'fs_grid': fs_grid, 'latent_grid': latent_grid,
        'T_ms': float(T_ms) if not np.isnan(T_ms) else np.nan,
        'T_me': float(T_me) if not np.isnan(T_me) else np.nan
    }

def _plot_properties(name, data):
    fig, axes = plt.subplots(2, 3, figsize=(15, 8))
    T = data['T_grid']
    axes[0, 0].plot(T, data['rho_grid'], 'b-'); axes[0, 0].set_title('Density')
    axes[0, 1].plot(T, data['cp_sens_grid'], 'b-'); axes[0, 1].plot(T, data['cp_eff_grid'], 'r--'); axes[0, 1].set_title('Cp')
    axes[0, 2].plot(T, data['latent_grid'], 'g-'); axes[0, 2].set_title('Latent Heat')
    axes[1, 0].plot(T, data['k_grid'], 'b-'); axes[1, 0].set_title('Conductivity')
    axes[1, 1].semilogy(T, data['mu_grid'], 'b-'); axes[1, 1].set_title('Viscosity')
    axes[1, 2].plot(T, data['fs_grid'], 'k-'); axes[1, 2].set_title('Solid Fraction')
    for ax in axes.flatten(): ax.grid(True, alpha=0.3); ax.set_xlabel('Temp (°C)')
    fig.suptitle(name); fig.tight_layout()
    fig.savefig(os.path.join(PLOTS_DIR, f'{name}_properties.png'), dpi=100); plt.close(fig)

def check_and_build_cache():
    os.makedirs(CACHE_DIR, exist_ok=True)
    os.makedirs(PLOTS_DIR, exist_ok=True)
    current_hash = get_db_hash()
    conn = sqlite3.connect(DB_PATH)
    
    for table in ["Fluids", "Metals"]:
        df = pd.read_sql_query(f"SELECT * FROM {table}", conn)
        for mat in df['Material'].unique():
            cache_file = os.path.join(CACHE_DIR, f'{mat}.npz')
            if _cache_valid(cache_file, current_hash): continue
            print(f"  Generating properties for {mat}...")
            data = _fit_material(df[df['Material'] == mat])
            np.savez(cache_file, hash=current_hash, **data)
            _plot_properties(mat, data)

    df_insul = pd.read_sql_query("SELECT * FROM Insulation", conn)
    for _, row in df_insul.iterrows():
        mat = row['Material']
        cache_file = os.path.join(CACHE_DIR, f'{mat}.npz')
        if _cache_valid(cache_file, current_hash): continue
        data = {'T_grid': np.array([0.0]), 'rho_grid': np.array([1000.0]), 'cp_sens_grid': np.array([1000.0]),
                'cp_eff_grid': np.array([1000.0]), 'k_grid': np.array([float(row['k_WmK'])]), 'mu_grid': np.array([1e5]),
                'H_grid': np.array([0.0]), 'fs_grid': np.array([0.0]), 'latent_grid': np.array([0.0]),
                'T_ms': np.array([np.nan]), 'T_me': np.array([np.nan])}
        np.savez(cache_file, hash=current_hash, **data)
    conn.close()

def _cache_valid(cache_file, current_hash):
    if not os.path.exists(cache_file): return False
    try:
        data = np.load(cache_file, allow_pickle=True)
        return str(data['hash']) == current_hash
    except: return False

def load(name):
    """Loads the cached .npz dictionary for a material."""
    cache_file = os.path.join(CACHE_DIR, f'{name}.npz')
    if not os.path.exists(cache_file):
        for f in os.listdir(CACHE_DIR):
            if f.lower() == f'{name.lower()}.npz':
                cache_file = os.path.join(CACHE_DIR, f); break
        else: raise FileNotFoundError(f"Material '{name}' not found in cache.")
    
    data = np.load(cache_file, allow_pickle=True)
    return {k: data[k] for k in data.files if k != 'hash'}

def load_settings():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT Parameter, Value FROM Settings", conn)
    conn.close()
    return float(df[df['Parameter'] == 'LiquidFraction_Threshold']['Value'].values[0]), float(df[df['Parameter'] == 'Viscosity_Threshold']['Value'].values[0])