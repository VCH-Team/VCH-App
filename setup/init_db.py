# setup/init_db.py
import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, 'data', 'VCH_Data.db')
SQL_PATH = os.path.join(BASE_DIR, 'data', 'VCH_Data.sql')

def build_db():
    if not os.path.exists(SQL_PATH):
        print(f"Error: SQL file not found at {SQL_PATH}")
        return
        
    print("Building SQLite Database from script...")
    with open(SQL_PATH, 'r', encoding='utf-8') as f:
        sql_script = f.read()
        
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.executescript(sql_script)
    conn.commit()
    conn.close()
    print(f"Success! Database created at {DB_PATH}")

if __name__ == "__main__":
    build_db()