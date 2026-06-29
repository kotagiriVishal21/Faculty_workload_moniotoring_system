import sqlite3
DATABASE = 'faculty_workload.db'
conn = sqlite3.connect(DATABASE)
conn.row_factory = sqlite3.Row
print("--- Timeslots ---")
for r in conn.execute("SELECT * FROM timeslots").fetchall():
    print(dict(r))
print("--- Sections ---")
for r in conn.execute("SELECT * FROM sections").fetchall():
    print(dict(r))
print("--- Courses ---")
for r in conn.execute("SELECT * FROM courses").fetchall():
    print(dict(r))
conn.close()
