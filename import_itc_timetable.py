import sqlite3

db = sqlite3.connect('faculty_workload.db')
db.row_factory = sqlite3.Row

# ── Dept & Section IDs ────────────────────────────────────────────────
DEPT_IT = 1
SECTION_C = 3   # IT-C

# ── Timeslot mapping (use existing IDs 1-9, skip breaks 3,6) ─────────
# slot_num → timeslot_id
TS = {1:1, 2:2, 3:4, 4:5, 5:7, 6:8, 7:9}  # image slots 1-7 (no breaks)

# ── Insert missing courses ────────────────────────────────────────────
courses_to_add = [
    ('A8652', 'Cyber Security (PE-II)', 0),
    ('A8804', 'Data Analytics (PE-II)', 0),
    ('A8658', 'Robotic Process Automation (PE-II)', 0),
    ('A8553', 'Web and Database Security (PE-III)', 0),
    ('A8707', 'Deep Learning (PE-III)', 0),
    ('A6559', 'Sales Force (PE-III)', 0),
    ('A8012', 'Advanced English Communication Skills Lab', 1),
    ('A8034', 'Indian Constitution', 0),
    ('C1003', 'Life Skill Development', 0),
    ('VAC',   'Value Added Course', 0),
    ('DSA',   'Data Structures and Algorithms', 0),
    ('NPSC',  'NASSCOM Prime Skills Certification', 0),
    ('LSM',   'Library Sports Mentoring', 0),
    ('MAT',   'Module Assessment Test', 0),
    ('ICN',   'Indian Constitution', 0),
    ('LSD',   'Life Skill Development', 0),
]
for code, name, is_lab in courses_to_add:
    existing = db.execute('SELECT id FROM courses WHERE subject_code=?', (code,)).fetchone()
    if not existing:
        db.execute('INSERT INTO courses (subject_code, course_name, is_lab, department_id) VALUES (?,?,?,?)',
                   (code, name, is_lab, DEPT_IT))

db.commit()
print('Courses inserted')

# ── Insert missing faculty ────────────────────────────────────────────
# From the timetable: Short Name → Full Name mapping
faculty_to_add = [
    ('Dr. K Nikhila',          'knk@it.edu'),
    ('Ms. Farhana Begum',      'fbm@it.edu'),   # may exist already
    ('Dr. Ganesh Bhaiyya R',   'gbr@it.edu'),   # may exist already
    ('Dr. B K Madhavi',        'bkm@it.edu'),
    ('Dr. G Srinivasulu',      'gsn@it.edu'),
    ('Ms. T Prashanthi',       'tps@it.edu'),
    ('Ms. P Swetha',           'pst@it.edu'),
    ('Mr. Nirmal Keshari Swain','nks@it.edu'),
    ('Ms. Sumaiya SK',         'smk@it.edu'),   # may exist already
    ('Mr. Shobanbabu R J',     'srj@it.edu'),   # may exist already
    ('Ms. Swati Singh',        'ssh@it.edu'),
    ('Mr. S Satheesh Kumar',   'ssk@it.edu'),
    ('Ms. Syeda Fatima Farheen','sff@it.edu'),
    ('Dr. Santhini M A',       'sma@it.edu'),
    ('Mr. P Vijaya Raghavulu', 'pvr@it.edu'),   # may exist already
    ('Ms. Rukmita Pal',        'rp@it.edu'),
    ('Ms. Asma Begum',         'abm@it.edu'),
    ('Dr. L Sunitha',          'lst@it.edu'),
]
for name, email in faculty_to_add:
    existing = db.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()
    if not existing:
        db.execute("INSERT INTO users (name, email, password, role, department_id) VALUES (?,?,?,?,?)",
                   (name, email, 'password', 'faculty', DEPT_IT))

db.commit()
print('Faculty inserted')

# ── Reload IDs after inserts ──────────────────────────────────────────
def cid(code):
    r = db.execute('SELECT id FROM courses WHERE subject_code=?', (code,)).fetchone()
    return r['id'] if r else None

def fid(email):
    r = db.execute('SELECT id FROM users WHERE email=?', (email,)).fetchone()
    return r['id'] if r else None

# ── Delete existing IT-C timetable entries (clean slate) ─────────────
existing_ids = db.execute(
    'SELECT DISTINCT t.faculty_id FROM timetable t JOIN users u ON t.faculty_id=u.id WHERE u.department_id=?',
    (DEPT_IT,)
).fetchall()
db.execute('DELETE FROM timetable WHERE section_id=?', (SECTION_C,))
db.commit()
print('Old IT-C timetable cleared')

# ── Define timetable from image ───────────────────────────────────────
# Format: (day, slot_num, course_code, faculty_email, room)
entries = [
    # MONDAY
    ('MON', 1, 'A8522', 'knk@it.edu',  '3017'),
    ('MON', 2, 'A8523', 'gbr@it.edu',  '3017'),
    ('MON', 3, 'VAC',   'smk@it.edu',  '3021'),
    ('MON', 4, 'VAC',   'smk@it.edu',  '3021'),
    ('MON', 5, 'A8607', 'fbm@it.edu',  '3017'),
    ('MON', 6, 'NPSC',  'srj@it.edu',  '3021'),
    ('MON', 7, 'NPSC',  'srj@it.edu',  '3021'),

    # TUESDAY
    ('TUE', 1, 'LSD',   'rp@it.edu',   '3017'),  # LSD (RP) spans slot 1+2
    ('TUE', 2, 'LSD',   'rp@it.edu',   '3017'),
    ('TUE', 3, 'A8804', 'tps@it.edu',  '3017'),  # DAS/CSY/RPA labs
    ('TUE', 4, 'A8707', 'smk@it.edu',  '3017'),  # DLG/WDS/SFC PE-III
    ('TUE', 5, 'A8523', 'gbr@it.edu',  '3017'),  # CDN*
    ('TUE', 6, 'DSA',   'lst@it.edu',  '3017'),
    ('TUE', 7, 'DSA',   'lst@it.edu',  '3017'),

    # WEDNESDAY
    ('WED', 1, 'A8804', 'gsn@it.edu',  '3017'),  # DAS/CSY/RPA
    ('WED', 2, 'A8607', 'fbm@it.edu',  '3017'),
    ('WED', 3, 'A8522', 'knk@it.edu',  '3017'),
    ('WED', 4, 'A8707', 'smk@it.edu',  '3017'),  # DLG/WDS/SFC
    ('WED', 5, 'A8524', 'knk@it.edu',  '3014'),  # CCL Lab / NSL Lab
    ('WED', 6, 'A8524', 'knk@it.edu',  '3014'),
    ('WED', 7, 'A8524', 'knk@it.edu',  '3014'),

    # THURSDAY
    ('THU', 1, 'A8607', 'fbm@it.edu',  '3017'),
    ('THU', 2, 'A8522', 'knk@it.edu',  '3017'),
    ('THU', 3, 'A8523', 'gbr@it.edu',  '3017'),
    ('THU', 4, 'A8707', 'smk@it.edu',  '3017'),  # DLG/WDS/SFC
    ('THU', 5, 'A8607', 'fbm@it.edu',  '3017'),  # INS
    ('THU', 6, 'MAT',   'fbm@it.edu',  '3017'),
    ('THU', 7, 'LSM',   'fbm@it.edu',  '3017'),

    # FRIDAY
    ('FRI', 1, 'A8804', 'tps@it.edu',  '3017'),  # DAS/CSY/RPA
    ('FRI', 2, 'A8523', 'gbr@it.edu',  '3017'),
    ('FRI', 3, 'ICN',   'pvr@it.edu',  '3017'),
    ('FRI', 4, 'A8522', 'knk@it.edu',  '3017'),
    ('FRI', 5, 'A8612', 'fbm@it.edu',  '3014'),  # NSL/CCL Lab
    ('FRI', 6, 'A8612', 'fbm@it.edu',  '3014'),
    ('FRI', 7, 'A8612', 'fbm@it.edu',  '3014'),

    # SATURDAY
    ('SAT', 1, 'A8012', 'sff@it.edu',  '5105'),  # ACL Lab
    ('SAT', 2, 'A8012', 'sff@it.edu',  '5105'),
    ('SAT', 3, 'A8804', 'tps@it.edu',  '3017'),  # DAS/CSY/RPA
    ('SAT', 4, 'A8523', 'gbr@it.edu',  '3017'),
    ('SAT', 5, 'A8707', 'smk@it.edu',  '3017'),  # DLG/WDS/SFC
    ('SAT', 6, 'A8522', 'knk@it.edu',  '3017'),  # CCV*
    ('SAT', 7, 'A8607', 'fbm@it.edu',  '3017'),  # INS*
]

inserted = 0
skipped  = 0
for day, slot, course_code, faculty_email, room in entries:
    c = cid(course_code)
    f = fid(faculty_email)
    ts = TS.get(slot)
    if not c:
        print(f'  SKIP: course {course_code} not found')
        skipped += 1; continue
    if not f:
        print(f'  SKIP: faculty {faculty_email} not found')
        skipped += 1; continue
    if not ts:
        print(f'  SKIP: slot {slot} not mapped')
        skipped += 1; continue
    db.execute('''
        INSERT OR IGNORE INTO timetable (faculty_id, course_id, section_id, timeslot_id, day, room_no)
        VALUES (?,?,?,?,?,?)
    ''', (f, c, SECTION_C, ts, day, room))
    inserted += 1

db.commit()
print(f'Done! Inserted: {inserted}, Skipped: {skipped}')
