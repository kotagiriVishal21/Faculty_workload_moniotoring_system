import sqlite3
db = sqlite3.connect('faculty_workload.db')
db.row_factory = sqlite3.Row

sections = db.execute('SELECT id, name FROM sections').fetchall()
print('=SECTIONS=', [(r['id'],r['name']) for r in sections])

timeslots = db.execute('SELECT id, start_time, end_time, is_break FROM timeslots ORDER BY id').fetchall()
print('=TIMESLOTS=', [(r['id'],r['start_time'],r['end_time'],r['is_break']) for r in timeslots])

faculty = db.execute("SELECT id, name FROM users WHERE role='faculty' ORDER BY name").fetchall()
print('=FACULTY=', [(r['id'],r['name']) for r in faculty])

courses = db.execute('SELECT id, subject_code, course_name FROM courses ORDER BY subject_code').fetchall()
print('=COURSES=', [(r['id'],r['subject_code'],r['course_name']) for r in courses])

dept = db.execute("SELECT id, name FROM departments").fetchall()
print('=DEPARTMENTS=', [(r['id'],r['name']) for r in dept])
