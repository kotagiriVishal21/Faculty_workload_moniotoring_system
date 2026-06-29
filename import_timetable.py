import sqlite3

db = sqlite3.connect('faculty_workload.db')
db.row_factory = sqlite3.Row
cursor = db.cursor()

# Get department ID for IT
cursor.execute("SELECT id FROM departments WHERE name = 'Information Technology'")
dept_id = cursor.fetchone()['id']

# Get section ID for IT-C
cursor.execute("SELECT id FROM sections WHERE name = 'IT-C' AND department_id = ?", (dept_id,))
row = cursor.fetchone()
if not row:
    cursor.execute("INSERT INTO sections (name, department_id) VALUES ('IT-C', ?)", (dept_id,))
    section_id = cursor.lastrowid
else:
    section_id = row['id']

# Timeslot mapping
cursor.execute("SELECT id, period_number FROM timeslots WHERE is_break = 0")
ts_map = {row['period_number']: row['id'] for row in cursor.fetchall()}

# Ensure users exist and map them
faculty_data = [
    ('knk@it.edu', 'password', 'Dr. K Nikhila'),
    ('fbm@it.edu', 'password', 'Ms. Farhana Begum'),
    ('gbr@it.edu', 'password', 'Dr. Ganesh Bhayya R'),
    ('smk@it.edu', 'password', 'Ms. Sumaiya SK'),
    ('srj@it.edu', 'password', 'Mr. Shobanbabu R J'),
    ('rp@it.edu', 'password', 'Ms. Rukmita Pal'),
    ('bkm@it.edu', 'password', 'Dr. B K Madhavi'),
    ('nks@it.edu', 'password', 'Mr. Nirmal Keshari Swain'),
    ('lst@it.edu', 'password', 'Dr. L Sunitha'),
    ('sff@it.edu', 'password', 'Ms. Syeda Fatima Farheen'),
    ('pvr@it.edu', 'password', 'Mr. P Vijaya Raghavulu')
]

fac_map = {}
for email, pwd, name in faculty_data:
    cursor.execute("SELECT id FROM users WHERE name = ?", (name,))
    row = cursor.fetchone()
    if not row:
        cursor.execute("INSERT INTO users (email, password, name, role, department_id) VALUES (?, ?, ?, 'faculty', ?)",
                       (email, pwd, name, dept_id))
        f_id = cursor.lastrowid
        cursor.execute("INSERT INTO faculty_details (faculty_id) VALUES (?)", (f_id,))
    else:
        f_id = row['id']
    fac_map[name] = f_id

# Ensure courses exist and map them
course_data = [
    ('CCV', 'A8522', 0),
    ('INS', 'A8607', 0),
    ('CDN', 'A8523', 0),
    ('VAC', '3021', 0),
    ('NPSC', 'NPSC', 0),
    ('LSD', 'C1003', 0),
    ('CSY', 'A8652', 0),
    ('WDS', 'A8553', 0),
    ('DSA', 'DSA123', 0),
    ('CCL', 'A8524', 1),
    ('MAT', 'MAT123', 0),
    ('LSM', 'LSM123', 0),
    ('ICN', 'A8034', 0),
    ('NSL', 'A8612', 1),
    ('ACL', 'A8012', 1)
]

crs_map = {}
for c_name, c_code, is_lab in course_data:
    cursor.execute("SELECT id FROM courses WHERE subject_code = ?", (c_code,))
    row = cursor.fetchone()
    if not row:
        cursor.execute("INSERT INTO courses (course_name, subject_code, department_id, credits, is_lab) VALUES (?, ?, ?, 3, ?)",
                       (c_name, c_code, dept_id, is_lab))
        c_id = cursor.lastrowid
    else:
        c_id = row['id']
    crs_map[c_name] = c_id

# Clear existing IT-C timetable
cursor.execute("DELETE FROM timetable WHERE section_id = ?", (section_id,))

# Insert timetable logic
timetable_entries = [
    # MON
    ('MON', 1, 'CCV', 'Dr. K Nikhila', '3017'),
    ('MON', 2, 'CDN', 'Dr. Ganesh Bhayya R', '3017'),
    ('MON', 3, 'VAC', 'Ms. Sumaiya SK', '3021'),
    ('MON', 4, 'VAC', 'Ms. Sumaiya SK', '3021'),
    ('MON', 5, 'INS', 'Ms. Farhana Begum', '3017'),
    ('MON', 6, 'NPSC', 'Mr. Shobanbabu R J', '3021'),
    ('MON', 7, 'NPSC', 'Mr. Shobanbabu R J', '3021'),
    
    # TUE
    ('TUE', 1, 'LSD', 'Ms. Rukmita Pal', '1020'),
    ('TUE', 2, 'LSD', 'Ms. Rukmita Pal', '1020'),
    ('TUE', 3, 'CSY', 'Dr. B K Madhavi', '3017'),
    ('TUE', 4, 'WDS', 'Mr. Nirmal Keshari Swain', '3017'),
    ('TUE', 5, 'CDN', 'Dr. Ganesh Bhayya R', '3017'),
    ('TUE', 6, 'DSA', 'Dr. L Sunitha', '3017'),
    ('TUE', 7, 'DSA', 'Dr. L Sunitha', '3017'),
    
    # WED
    ('WED', 1, 'CSY', 'Dr. B K Madhavi', '3017'),
    ('WED', 2, 'CSY', 'Dr. B K Madhavi', '3017'),
    ('WED', 3, 'CCV', 'Dr. K Nikhila', '3017'),
    ('WED', 4, 'WDS', 'Mr. Nirmal Keshari Swain', '3017'),
    ('WED', 5, 'CCL', 'Dr. K Nikhila', '3014-B'),
    ('WED', 6, 'CCL', 'Dr. K Nikhila', '3014-B'),
    ('WED', 7, 'CCL', 'Dr. K Nikhila', '3014-B'),
    
    # THU
    ('THU', 1, 'INS', 'Ms. Farhana Begum', '3017'),
    ('THU', 2, 'CCV', 'Dr. K Nikhila', '3017'),
    ('THU', 3, 'CDN', 'Dr. Ganesh Bhayya R', '3017'),
    ('THU', 4, 'WDS', 'Mr. Nirmal Keshari Swain', '3017'),
    ('THU', 5, 'INS', 'Ms. Farhana Begum', '3017'),
    ('THU', 6, 'MAT', 'Ms. Farhana Begum', '3017'),
    ('THU', 7, 'LSM', 'Ms. Farhana Begum', '3017'),
    
    # FRI
    ('FRI', 1, 'CSY', 'Dr. B K Madhavi', '3017'),
    ('FRI', 2, 'CDN', 'Dr. Ganesh Bhayya R', '3017'),
    ('FRI', 3, 'ICN', 'Mr. P Vijaya Raghavulu', '3017'),
    ('FRI', 4, 'CCV', 'Dr. K Nikhila', '3017'),
    ('FRI', 5, 'NSL', 'Ms. Farhana Begum', '3014-A'),
    ('FRI', 6, 'NSL', 'Ms. Farhana Begum', '3014-A'),
    ('FRI', 7, 'NSL', 'Ms. Farhana Begum', '3014-A'),
    
    # SAT
    ('SAT', 1, 'ACL', 'Ms. Syeda Fatima Farheen', '5105'),
    ('SAT', 2, 'ACL', 'Ms. Syeda Fatima Farheen', '5105'),
    ('SAT', 3, 'CSY', 'Dr. B K Madhavi', '3017'),
    ('SAT', 4, 'CDN', 'Dr. Ganesh Bhayya R', '3017'),
    ('SAT', 5, 'WDS', 'Mr. Nirmal Keshari Swain', '3017'),
    ('SAT', 6, 'CCV', 'Dr. K Nikhila', '3017'),
    ('SAT', 7, 'INS', 'Ms. Farhana Begum', '3017')
]

for day, period, c_name, f_name, room in timetable_entries:
    t_id = ts_map[period]
    f_id = fac_map[f_name]
    c_id = crs_map[c_name]
    
    cursor.execute("""
        INSERT INTO timetable (day, timeslot_id, section_id, course_id, faculty_id, room_no)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (day, t_id, section_id, c_id, f_id, room))

db.commit()
print("Timetable successfully imported for IT-C section.")
