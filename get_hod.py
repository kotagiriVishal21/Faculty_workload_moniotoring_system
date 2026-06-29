import sqlite3
import os

DATABASE = 'faculty_workload.db'

def get_hod():
    if not os.path.exists(DATABASE):
        print("Database not found")
        return
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    user = conn.execute("SELECT email, password, role FROM users WHERE role = 'hod' LIMIT 1").fetchone()
    if user:
        print(f"EMAIL: {user['email']}")
        print(f"PASSWORD: {user['password']}")
    else:
        print("No HOD found")
    conn.close()

if __name__ == "__main__":
    get_hod()
