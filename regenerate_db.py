import sqlite3
import os

DATABASE = 'faculty_workload.db'
SCHEMA_FILE = 'schema_sqlite.sql'

def regenerate_db():
    if os.path.exists(DATABASE):
        os.remove(DATABASE)
    
    conn = sqlite3.connect(DATABASE)
    with open(SCHEMA_FILE, 'r') as f:
        conn.executescript(f.read())
    conn.commit()
    conn.close()
    print("Database regenerated successfully with new schema.")

if __name__ == "__main__":
    regenerate_db()
