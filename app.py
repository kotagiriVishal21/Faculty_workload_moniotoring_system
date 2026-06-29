from flask import Flask, render_template, request, jsonify, session, redirect, url_for, g
import sqlite3
import os

app = Flask(__name__)
app.secret_key = 'super_secret_key'

DATABASE = 'faculty_workload.db'

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

def get_faculty_workload(db, faculty_id, start_date=None, end_date=None):
    """Calculates total workload credits for a given faculty member."""
    # Date Filtering Clauses 
    t_date_clause = ""
    a_date_clause = ""
    r_date_clause = ""
    params_t = [faculty_id]
    params_tw = [faculty_id]
    params_a = [faculty_id]
    params_r = [faculty_id]

    if start_date and end_date:
        t_date_clause = " AND date BETWEEN ? AND ?"
        a_date_clause = " AND date BETWEEN ? AND ?"
        r_date_clause = " AND created_at BETWEEN ? AND ?"
        params_tw.extend([start_date, end_date])
        params_a.extend([start_date, end_date])
        params_r.extend([start_date + " 00:00:00", end_date + " 23:59:59"])
        
    # Teaching Credits (from Timetable AND Logged Workload)
    # 1. Scheduled from Timetable 
    t_rows = db.execute('''
        SELECT c.is_lab, COUNT(*) as slots
        FROM timetable t
        JOIN courses c ON t.course_id = c.id
        WHERE t.faculty_id = ?
        GROUP BY c.is_lab
    ''', params_t).fetchall()
    
    # 2. Manually Logged (uses new is_lab column)
    l_rows = db.execute(f'''
        SELECT is_lab, SUM(hours_per_week) as total_hours
        FROM teaching_workload 
        WHERE faculty_id = ? {t_date_clause}
        GROUP BY is_lab
    ''', params_tw).fetchall()
    
    teaching_credits = 0.0
    for row in t_rows:
        slots_val = row['slots']
        is_lab_val = row['is_lab']
        if slots_val is not None:
            teaching_credits += float(slots_val) * (4.0 if int(is_lab_val) == 1 else 3.0)
            
    for row in l_rows:
        hours_val = row['total_hours']
        is_lab_val = row['is_lab']
        if hours_val is not None:
            teaching_credits += float(hours_val) * (4.0 if int(is_lab_val) == 1 else 3.0)
    
    # Academic & Mentoring contributions (1 credit per hour)
    academic_row = db.execute(f'SELECT SUM(hours) as total FROM academic_activities WHERE faculty_id = ? AND status = "Approved" {a_date_clause}', 
                           params_a).fetchone()
    academic = float((academic_row['total'] if academic_row and academic_row['total'] is not None else 0))
    
    # Research contributions (weighted count)
    research_row = db.execute(f'SELECT COUNT(*) as count FROM research_activities WHERE faculty_id = ? AND status = "Approved" {r_date_clause}', 
                          params_r).fetchone()
    research = float((research_row['count'] if research_row and research_row['count'] is not None else 0) * 5)
    
    return {
        "teaching": float(teaching_credits),
        "academic": float(academic),
        "research": float(research),
        "total": float(teaching_credits + academic + research)
    }

def get_department_stats(db, dept_id, start_date=None, end_date=None):
    """Calculates aggregated stats for an entire department."""
    faculties = db.execute('SELECT id FROM users WHERE department_id = ? AND role = "faculty"', (dept_id,)).fetchall()
    total_teaching = 0
    total_research = 0
    
    for f in faculties:
        w = get_faculty_workload(db, f['id'], start_date, end_date)
        total_teaching += w['teaching']
        total_research += (w['research'] / 5) # Convert back to count
        
    return {
        "teaching_hours": float(total_teaching),
        "research_papers": float(total_research),
        "faculty_count": len(faculties)
    }

def get_daily_workload(db, faculty_id, target_date_str):
    """Calculates workload for a specific date (YYYY-MM-DD), returning structured metrics."""
    from datetime import datetime
    target_date = datetime.strptime(target_date_str, '%Y-%m-%d')
    day_abbr = target_date.strftime('%a').upper() # 'MON', 'TUE', etc.
    
    total_hours = 0.0
    
    # 1. Timetable Hours (Matching day of week)
    teaching_rows = db.execute('''
        SELECT ts.start_time, ts.end_time
        FROM timetable t
        JOIN timeslots ts ON t.timeslot_id = ts.id
        WHERE t.faculty_id = ? AND t.day = ?
    ''', (faculty_id, day_abbr)).fetchall()
    
    teaching_hours = 0.0
    for r in teaching_rows:
        # Simplification: assume 1 period = 1 hour for display if parsing time is tricky, 
        # or parse AM/PM cleanly. 
        teaching_hours += 1.0 # default to 1 hour per slot for simplicity here
    
    total_hours += teaching_hours
    
    # 2. Academic/Mentoring Hours (Matching exact date)
    academic_row = db.execute('''
        SELECT SUM(hours) as total 
        FROM academic_activities 
        WHERE faculty_id = ? AND date = ? AND status = "Approved"
    ''', (faculty_id, target_date_str)).fetchone()
    
    academic_hours = float(academic_row['total'] or 0)
    total_hours += academic_hours
    
    # 3. Weekly Schedules entered by HOD (matching exact date)
    ws_row = db.execute('''
        SELECT SUM(duration) as total
        FROM weekly_schedules
        WHERE faculty_id = ? AND date = ?
    ''', (faculty_id, target_date_str)).fetchone()
    
    ws_hours = float(ws_row['total'] or 0) if ws_row else 0.0
    total_hours += ws_hours
    
    # Workload Percentage capping at 8 hours (100%)
    percentage = (total_hours / 8.0) * 100
    
    status_indicator = "green"
    if percentage >= 80: status_indicator = "red"
    elif percentage >= 50: status_indicator = "yellow"
        
    return {
        "date": target_date_str,
        "day": day_abbr,
        "teaching_hours": teaching_hours,
        "academic_hours": academic_hours,
        "total_hours": total_hours,
        "percentage": min(round(percentage, 1), 100), # Cap visually at 100 or let it exceed
        "status": status_indicator
    }

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

# Initialize Database
def init_db():
    if not os.path.exists(DATABASE):
        with app.app_context():
            db = get_db()
            with open('schema_sqlite.sql', mode='r') as f:
                db.cursor().executescript(f.read())
            db.commit()

@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # Role-based redirection
    if session.get('role') == 'hod':
        return redirect(url_for('hod_dashboard'))
    if session.get('role') == 'admin':
        return redirect(url_for('manage_users'))
    
    db = get_db()
    profile_row = db.execute('SELECT * FROM faculty_details WHERE faculty_id = ?', (session['user_id'],)).fetchone()
    profile = dict(profile_row) if profile_row else {}
    
    workload = 0
    if session['role'] == 'faculty':
        # Teaching Credits (from Timetable AND Logged Workload)
        # 1. Scheduled from Timetable
        t_rows = db.execute('''
            SELECT c.is_lab, COUNT(*) as slots
            FROM timetable t
            JOIN courses c ON t.course_id = c.id
            WHERE t.faculty_id = ?
            GROUP BY c.is_lab
        ''', (session['user_id'],)).fetchall()
        
        # 2. Manually Logged
        l_rows = db.execute('''
            SELECT is_lab, SUM(hours_per_week) as total_hours
            FROM teaching_workload 
            WHERE faculty_id = ?
            GROUP BY is_lab
        ''', (session['user_id'],)).fetchall()
        
        teaching_credits = 0.0
        for row in t_rows:
            slots_val = row['slots']
            is_lab_val = row['is_lab']
            if slots_val is not None:
                teaching_credits += float(slots_val) * (4.0 if int(is_lab_val) == 1 else 3.0)
                
        for row in l_rows:
            hours_val = row['total_hours']
            is_lab_val = row['is_lab']
            if hours_val is not None:
                teaching_credits += float(hours_val) * (4.0 if int(is_lab_val) == 1 else 3.0)
        
        # Academic & Mentoring contributions (1 credit per hour)
        cursor = db.cursor()
        academic_row = cursor.execute('SELECT SUM(hours) as total FROM academic_activities WHERE faculty_id = ? AND status = "Approved"', 
                               (session['user_id'],)).fetchone()
        academic = float((academic_row['total'] if academic_row else 0) or 0)
        
        # Research contributions (weighted count)
        research_row = cursor.execute('SELECT COUNT(*) as count FROM research_activities WHERE faculty_id = ? AND status = "Approved"', 
                              (session['user_id'],)).fetchone()
        research = float((research_row['count'] if research_row else 0) * 5)
        
        workload = teaching_credits + academic + research

    return render_template('dashboard.html', user=session['name'], role=session['role'], profile=profile, 
                           workload=workload, teaching=teaching_credits, academic=academic, research=research)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        requested_role = request.form.get('role')

        db = get_db()
        account = db.execute('SELECT * FROM users WHERE email = ? AND password = ? AND role = ?', 
                             (email, password, requested_role)).fetchone()
        
        if account:
            session['user_id'] = account['id']
            session['name'] = account['name']
            session['role'] = account['role']
            session['dept_id'] = account['department_id']
            return redirect(url_for('index'))
        return "Invalid credentials", 401
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# Admin Management
@app.route('/admin/departments', methods=['GET', 'POST'])
def manage_departments():
    if session.get('role') != 'admin': return redirect(url_for('index'))
    db = get_db()
    if request.method == 'POST':
        db.execute('INSERT INTO departments (name) VALUES (?)', (request.form.get('name'),))
        db.commit()
    depts = db.execute('SELECT * FROM departments').fetchall()
    
    processed_depts = []
    for d in depts:
        d_dict = dict(d)
        # Generate initials e.g. 'Computer Science and Engineering' -> 'CSE'
        words = d_dict['name'].replace(' and ', ' ').replace(' AND ', ' ').split()
        code = ''.join([w[0].upper() for w in words if w])
        d_dict['code'] = code
        processed_depts.append(d_dict)
        
    return render_template('admin_departments.html', departments=processed_depts)

@app.route('/admin/courses', methods=['GET', 'POST'])
def manage_courses():
    if session.get('role') != 'admin': return redirect(url_for('index'))
    db = get_db()
    if request.method == 'POST':
        db.execute('INSERT INTO courses (course_name, subject_code, credits, department_id, is_lab) VALUES (?, ?, ?, ?, ?)', 
                   (request.form.get('course_name'), request.form.get('subject_code'), 
                    request.form.get('credits'), request.form.get('dept_id'), 
                    1 if request.form.get('type') == 'lab' else 0))
        db.commit()
    courses = db.execute('SELECT c.*, d.name as dept_name FROM courses c JOIN departments d ON c.department_id = d.id').fetchall()
    depts = db.execute('SELECT * FROM departments').fetchall()
    return render_template('admin_courses.html', courses=courses, departments=depts)

@app.route('/admin/users', methods=['GET', 'POST'])
def manage_users():
    if session.get('role') != 'admin': return redirect(url_for('index'))
    db = get_db()
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add':
            name = request.form.get('name')
            email = request.form.get('email')
            password = request.form.get('password')
            role = request.form.get('role')
            dept_id = request.form.get('dept_id')
            
            cursor = db.execute('INSERT INTO users (name, email, password, role, department_id) VALUES (?, ?, ?, ?, ?)',
                       (name, email, password, role, dept_id))
            new_id = cursor.lastrowid
            
            if role == 'faculty':
                db.execute('INSERT INTO faculty_details (faculty_id) VALUES (?)', (new_id,))
            
            db.commit()
        elif action == 'update':
            db.execute('UPDATE users SET role = ?, department_id = ? WHERE id = ?', 
                       (request.form.get('role'), request.form.get('dept_id'), request.form.get('user_id')))
            db.commit()
        elif action == 'remove':
            user_id = request.form.get('user_id')
            db.execute('DELETE FROM faculty_details WHERE faculty_id = ?', (user_id,))
            db.execute('DELETE FROM users WHERE id = ?', (user_id,))
            db.commit()
    users = db.execute('SELECT u.*, d.name as dept_name FROM users u LEFT JOIN departments d ON u.department_id = d.id').fetchall()
    depts = db.execute('SELECT * FROM departments').fetchall()
    return render_template('admin_users.html', users=users, departments=depts)


@app.route('/admin/faculty_domain', methods=['GET', 'POST'])
def faculty_domain():
    if session.get('role') != 'admin': return redirect(url_for('index'))
    db = get_db()
    if request.method == 'POST':
        db.execute('''
            INSERT INTO faculty_details (faculty_id, designation, qualification, experience, domain, pan_number, joining_date)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(faculty_id) DO UPDATE SET 
            designation=excluded.designation, qualification=excluded.qualification, 
            experience=excluded.experience, domain=excluded.domain, pan_number=excluded.pan_number, joining_date=excluded.joining_date
        ''', (request.form.get('faculty_id'), request.form.get('designation'), request.form.get('qualification'), 
              request.form.get('experience'), request.form.get('domain'), request.form.get('pan'), request.form.get('joining')))
        db.commit()
    faculty = db.execute('SELECT u.id, u.name, d.domain FROM users u LEFT JOIN faculty_details d ON u.id = d.faculty_id WHERE u.role = "faculty"').fetchall()
    return render_template('admin_faculty_domain.html', faculty=faculty)

# Timetable & Scheduling (HoD Control)
@app.route('/hod/timetable', methods=['GET', 'POST'])
def manage_timetable():
    if session.get('role') != 'hod': return redirect(url_for('index'))
    db = get_db()
    
    selected_section = int(request.args.get('section_id') or 1)
    
    if request.method == 'POST':
        try:
            day = request.form.get('day')
            slot_id = int(request.form.get('timeslot_id'))
            course_id = request.form.get('course_id')
            faculty_id = request.form.get('faculty_id')
            room = request.form.get('room')
            
            if not all([day, slot_id, course_id, faculty_id, room]):
                return "Missing required fields", 400

            course = db.execute('SELECT * FROM courses WHERE id = ?', (course_id,)).fetchone()
            if not course:
                return "Invalid course selected", 400
            
            # 1. Faculty Workload Constraint (18h max)
            # Physical hours = slots in timetable + logged hours
            t_hours = db.execute('SELECT COUNT(*) as total FROM timetable WHERE faculty_id = ?', (faculty_id,)).fetchone()['total'] or 0
            l_hours = db.execute('SELECT SUM(hours_per_week) as total FROM teaching_workload WHERE faculty_id = ?', (faculty_id,)).fetchone()['total'] or 0
            if (t_hours + l_hours) >= 18:
                return "Error: Faculty exceeds 18-hour physical work limit", 400
                
            # 2. Course Instructor Limit (At most 2 for same course)
            instructors = db.execute('SELECT DISTINCT faculty_id FROM timetable WHERE course_id = ? AND section_id IN (SELECT id FROM sections WHERE department_id = ?)', 
                                     (course_id, session['dept_id'])).fetchall()
            instructor_ids = [i['faculty_id'] for i in instructors]
            if len(instructor_ids) >= 2 and int(faculty_id) not in instructor_ids:
                return "Error: Max 2 instructors allowed for this course", 400

            # 0. Break Slot Protection
            slot = db.execute('SELECT * FROM timeslots WHERE id = ?', (slot_id,)).fetchone()
            if not slot or slot['is_break'] == 1:
                return "Error: Cannot assign classes to a break/lunch slot", 400

            # 1. Collision Checks (Faculty, Section, Room)
            def check_collision(d, sid, fid, r, current_section_id):
                # Faculty Busy?
                if db.execute('SELECT id FROM timetable WHERE day = ? AND timeslot_id = ? AND faculty_id = ?', (d, sid, fid)).fetchone():
                    return f"Error: Faculty is already busy in this slot"
                # Section Busy?
                if db.execute('SELECT id FROM timetable WHERE day = ? AND timeslot_id = ? AND section_id = ?', (d, sid, current_section_id)).fetchone():
                    return f"Error: Section already has a class in this slot"
                # Room Busy?
                if db.execute('SELECT id FROM timetable WHERE day = ? AND timeslot_id = ? AND room_no = ?', (d, sid, r)).fetchone():
                    return f"Error: Room {r} is already occupied in this slot"
                return None

            # 2. Lab Slot Continuity & Availability
            if course['is_lab'] == 1:
                slots = db.execute('SELECT * FROM timeslots WHERE id >= ? ORDER BY id LIMIT 3', (slot_id,)).fetchall()
                if len(slots) < 3 or any(s['is_break'] == 1 for s in slots):
                    return "Error: Lab requires 3 continuous non-break slots", 400
                
                for s in slots:
                    collision = check_collision(day, s['id'], faculty_id, room, selected_section)
                    if collision: return collision
                    
                for s in slots:
                    db.execute('INSERT INTO timetable (day, timeslot_id, section_id, course_id, faculty_id, room_no) VALUES (?, ?, ?, ?, ?, ?)',
                               (day, s['id'], selected_section, course_id, faculty_id, room))
            else:
                # 3. Theory Collision and Limit Check
                collision = check_collision(day, slot_id, faculty_id, room, selected_section)
                if collision: return collision

                t_row = db.execute('SELECT COUNT(*) as total FROM timetable WHERE course_id = ? AND section_id = ?', 
                                            (course_id, selected_section)).fetchone()
                current_theory = int(t_row['total'] if t_row else 0)
                if current_theory >= 4:
                    return "Error: Theory course already has 4 slots assigned to this section this week", 400

                db.execute('INSERT INTO timetable (day, timeslot_id, section_id, course_id, faculty_id, room_no) VALUES (?, ?, ?, ?, ?, ?)',
                           (day, slot_id, selected_section, course_id, faculty_id, room))
            
            db.commit()
            return redirect(url_for('manage_timetable', section_id=selected_section))
        except Exception as e:
            db.rollback()
            print(f"Timetable Error: {e}")
            return f"System Error: {e}", 500

    # Load timetable grid data
    days = ['MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT']
    timeslots = [dict(ts) for ts in db.execute('SELECT * FROM timeslots ORDER BY id').fetchall()]
    sections = [dict(s) for s in db.execute('SELECT * FROM sections WHERE department_id = ?', (session['dept_id'],)).fetchall()]
    courses = [dict(c) for c in db.execute('SELECT * FROM courses WHERE department_id = ?', (session['dept_id'],)).fetchall()]
    faculty = [dict(f) for f in db.execute('SELECT * FROM users WHERE department_id = ? AND role = "faculty"', (session['dept_id'],)).fetchall()]
    
    # Fetch existing assignments for the section
    assignments = [dict(a) for a in db.execute('''
        SELECT t.*, c.subject_code, u.name as faculty_name 
        FROM timetable t
        JOIN courses c ON t.course_id = c.id
        JOIN users u ON t.faculty_id = u.id
        WHERE t.section_id = ?
    ''', (selected_section,)).fetchall()]
    
    # Create a lookup map for assignments
    lookup = {}
    for a in assignments:
        k = (str(a['day']), int(a['timeslot_id']))
        lookup[k] = dict(a)
    
    timetable_grid = {}
    for d in days:
        d_grid = {}
        for ts in timeslots:
            ts_id = int(ts['id'])
            d_grid[ts_id] = lookup.get((d, ts_id))
        timetable_grid[d] = d_grid

    return render_template('hod_timetable.html', 
                           grid=timetable_grid, days=days, timeslots=timeslots, 
                           sections=sections, courses=courses, faculty=faculty, 
                           current_section=selected_section)

@app.route('/hod/auto_generate', methods=['POST'])
def auto_generate():
    if session.get('role') != 'hod': return redirect(url_for('index'))
    db = get_db()
    
    course_id = request.form.get('course_id')
    required_hours = int(request.form.get('hours') or 0)
    section_id = int(request.form.get('section_id'))
    
    course = db.execute('SELECT * FROM courses WHERE id = ?', (course_id,)).fetchone()
    if not course: return "Course not found", 400
    
    # 1. Find Faculty who teach this course or are in the same department
    # For simplicity, we'll look for faculty in the department who aren't at the 18h limit
    eligible_faculty = db.execute('''
        SELECT u.id, u.name 
        FROM users u
        WHERE u.department_id = ? AND u.role = 'faculty'
    ''', (session['dept_id'],)).fetchall()
    
    if not eligible_faculty:
        return "Error: No faculty found in this department", 400

    assigned_hours = int(0)
    days = ['MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT']
    timeslots = db.execute('SELECT * FROM timeslots WHERE is_break = 0 ORDER BY id').fetchall()
    
    errors = []
    
    # Try to assign hours
    for f in eligible_faculty:
        if int(assigned_hours) >= int(required_hours): break
        
        # Check current physical workload
        t_row = db.execute('SELECT COUNT(*) FROM timetable WHERE faculty_id = ?', (f['id'],)).fetchone()
        t_h = float(t_row[0] if t_row else 0)
        l_row = db.execute('SELECT SUM(hours_per_week) FROM teaching_workload WHERE faculty_id = ?', (f['id'],)).fetchone()
        l_h = float(l_row[0] if l_row else 0)
        remaining_capacity = 18.0 - (t_h + l_h)
        
        if remaining_capacity <= 0: continue
        
        # Iterate over schedule to find free slots
        for day in days:
            if int(assigned_hours) >= int(required_hours): break
            for ts in timeslots:
                if int(assigned_hours) >= int(required_hours): break
                
                # Check if section is free
                section_busy = db.execute('SELECT id FROM timetable WHERE day = ? AND timeslot_id = ? AND section_id = ?', (day, int(ts['id']), int(section_id))).fetchone()
                if section_busy: continue
                
                # Check if faculty is free
                faculty_busy = db.execute('SELECT id FROM timetable WHERE day = ? AND timeslot_id = ? AND faculty_id = ?', (day, ts['id'], f['id'])).fetchone()
                if faculty_busy: continue
                
                # Lab continuity check
                if course['is_lab'] == 1:
                    # Need 3 continuous slots
                    cont_slots = db.execute('SELECT * FROM timeslots WHERE id >= ? ORDER BY id LIMIT 3', (ts['id'],)).fetchall()
                    if len(cont_slots) < 3 or any(s['is_break'] == 1 for s in cont_slots): continue
                    
                    # Check occupancy for all 3 slots
                    busy_any = False
                    for cs in cont_slots:
                        if db.execute('SELECT id FROM timetable WHERE day = ? AND timeslot_id = ? AND (section_id = ? OR faculty_id = ?)', (day, cs['id'], section_id, f['id'])).fetchone():
                            busy_any = True; break
                    if busy_any: continue
                    
                    # Assign Lab block
                    for cs in cont_slots:
                        db.execute('INSERT INTO timetable (day, timeslot_id, section_id, course_id, faculty_id, room_no) VALUES (?, ?, ?, ?, ?, ?)',
                                   (day, int(cs['id']), int(section_id), int(course_id), int(f['id']), 'Auto'))
                    assigned_hours = int(assigned_hours) + 3
                    db.commit() # Commit each block
                else:
                    # Assign Theory slot
                    db.execute('INSERT INTO timetable (day, timeslot_id, section_id, course_id, faculty_id, room_no) VALUES (?, ?, ?, ?, ?, ?)',
                               (day, int(ts['id']), int(section_id), int(course_id), int(f['id']), 'Auto'))
                    assigned_hours = int(assigned_hours) + 1
                    db.commit()

    current_assigned = int(assigned_hours)
    if current_assigned < int(required_hours):
        return f"Warning: Only scheduled {current_assigned}/{required_hours} hours. Reason: Insufficient free faculty slots or capacity limits.", 200
    
    return redirect(url_for('manage_timetable', section_id=section_id))

# NBA/NAAC Reports
@app.route('/admin/reports')
def accreditation_reports():
    if session.get('role') not in ['admin', 'hod']: return redirect(url_for('index'))
    db = get_db()
    # Comprehensive workload audit for all faculty
    report_data = []
    faculty_list = db.execute('SELECT id, name, email FROM users WHERE role = "faculty"').fetchall()
    
    for f in faculty_list:
        details = db.execute('SELECT * FROM faculty_details WHERE faculty_id = ?', (f['id'],)).fetchone()
        
        # Teaching Credits (Both sources)
        t_rows = db.execute('SELECT c.is_lab, COUNT(*) as slots FROM timetable t JOIN courses c ON t.course_id = c.id WHERE t.faculty_id = ? GROUP BY c.is_lab', (f['id'],)).fetchall()
        l_rows = db.execute('SELECT c.is_lab, SUM(hours_per_week) as total_hours FROM teaching_workload tw JOIN courses c ON tw.course_id = c.id WHERE tw.faculty_id = ? GROUP BY c.is_lab', (f['id'],)).fetchall()
        
        teaching_credits = sum((4 if int(r['is_lab']) == 1 else 3) * int(r['slots'] or 0) for r in t_rows)
        teaching_credits += sum((4 if int(r['is_lab']) == 1 else 3) * int(r['total_hours'] or 0) for r in l_rows)
        
        # Academic
        academic = db.execute('SELECT SUM(hours) as total FROM academic_activities WHERE faculty_id = ? AND status = "Approved"', (f['id'],)).fetchone()['total'] or 0
        
        # Research
        research = db.execute('SELECT COUNT(*) as count FROM research_activities WHERE faculty_id = ? AND status = "Approved"', (f['id'],)).fetchone()['count']
        
        report_data.append({
            'name': f['name'],
            'email': f['email'],
            'designation': details['designation'] if details else '',
            'qualification': details['qualification'] if details else '',
            'domain': details['domain'] if details else '',
            'specialization': details['specialization'] if details else '',
            'teaching_hours': teaching_credits,
            'academic_hours': academic,
            'research_count': research
        })
    return render_template('admin_reports.html', data=report_data)

# Faculty Activity Logging
@app.route('/faculty/add_teaching', methods=['GET', 'POST'])
def add_teaching():
    if session.get('role') != 'faculty': return redirect(url_for('index'))
    db = get_db()
    if request.method == 'POST':
        hours = int(request.form.get('hours') or 0)
        
        # Check 18h limit (sum of current scheduled and logged)
        t_hours = db.execute('SELECT COUNT(*) as total FROM timetable WHERE faculty_id = ?', (session['user_id'],)).fetchone()['total'] or 0
        l_hours = db.execute('SELECT SUM(hours_per_week) as total FROM teaching_workload WHERE faculty_id = ?', (session['user_id'],)).fetchone()['total'] or 0
        
        if (t_hours + l_hours + hours) > 18:
            return "Error: Total weekly teaching hours cannot exceed 18", 400

        # Resolve section name to ID
        section_name = request.form.get('section')
        section = db.execute('SELECT id FROM sections WHERE name = ?', (section_name,)).fetchone()
        section_id = section['id'] if section else 1
        
        db.execute('''
            INSERT INTO teaching_workload (faculty_id, course_id, section_id, hours_per_week, semester, date, is_lab)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (int(session['user_id']), int(request.form.get('course_id', 0)), int(section_id), 
              int(request.form.get('hours', 0)), request.form.get('semester'), request.form.get('date'), int(request.form.get('is_lab', 0))))
        db.commit()
        return redirect(url_for('index'))
    
    courses = db.execute('SELECT * FROM courses WHERE department_id = ?', (session['dept_id'],)).fetchall()
    return render_template('add_teaching.html', courses=courses)

@app.route('/faculty/add_activity', methods=['GET', 'POST'])
def add_activity():
    if session.get('role') != 'faculty': return redirect(url_for('index'))
    db = get_db()
    if request.method == 'POST':
        db.execute('''
            INSERT INTO academic_activities (faculty_id, activity_type, hours, date, description)
            VALUES (?, ?, ?, ?, ?)
        ''', (session['user_id'], request.form.get('type'), request.form.get('hours'), 
              request.form.get('date'), request.form.get('description')))
        db.commit()
        return redirect(url_for('index'))
    return render_template('add_activity.html')

@app.route('/faculty/add_research', methods=['GET', 'POST'])
def add_research():
    if session.get('role') != 'faculty': return redirect(url_for('index'))
    db = get_db()
    if request.method == 'POST':
        db.execute('''
            INSERT INTO research_activities (faculty_id, title, type, journal, year)
            VALUES (?, ?, ?, ?, ?)
        ''', (session['user_id'], request.form.get('title'), request.form.get('type'), 
              request.form.get('journal'), request.form.get('year')))
        db.commit()
        return redirect(url_for('index'))
    return render_template('add_research.html')

# Faculty Personal Schedule
@app.route('/faculty/timetable')
def faculty_personal_timetable():
    if 'user_id' not in session: return redirect(url_for('login'))
    db = get_db()
    days = ['MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT']
    timeslots = [dict(ts) for ts in db.execute('SELECT * FROM timeslots ORDER BY id').fetchall()]
    
    assignments = [dict(a) for a in db.execute('''
        SELECT t.*, c.course_name, s.name as section_name
        FROM timetable t
        JOIN courses c ON t.course_id = c.id
        JOIN sections s ON t.section_id = s.id
        WHERE t.faculty_id = ?
    ''', (session['user_id'],)).fetchall()]
    
    # Create a lookup map for assignments
    lookup = {}
    for a in assignments:
        k = (str(a['day']), int(a['timeslot_id']))
        lookup[k] = dict(a)
    
    grid = {}
    for d in days:
        d_grid = {}
        for ts in timeslots:
            ts_id = int(ts['id'])
            d_grid[ts_id] = lookup.get((d, ts_id))
        grid[d] = d_grid

    return render_template('faculty_timetable.html', grid=grid, days=days, timeslots=timeslots)

# HoD Dash & Approvals
@app.route('/hod/accreditation')
def hod_accreditation():
    if session.get('role') != 'hod': return redirect(url_for('index'))
    db = get_db()
    dept_id = session.get('dept_id')
    
    faculties = db.execute('SELECT id, name, email FROM users WHERE department_id = ? AND role = "faculty"', (dept_id,)).fetchall()
    
    report_data = []
    for f in faculties:
        faculty_rec = {
            'info': dict(f),
            'teaching': [],
            'academic': [],
            'research': []
        }
        
        # 1. Fetch all teaching logs
        t_logs = db.execute('''
            SELECT tw.*, c.course_name, s.name as section_name 
            FROM teaching_workload tw
            LEFT JOIN courses c ON tw.course_id = c.id
            LEFT JOIN sections s ON tw.section_id = s.id
            WHERE tw.faculty_id = ?
            ORDER BY tw.date DESC
        ''', (f['id'],)).fetchall()
        faculty_rec['teaching'] = [dict(t) for t in t_logs]
        
        # 2. Fetch all academic logs
        a_logs = db.execute('''
            SELECT * FROM academic_activities
            WHERE faculty_id = ?
            ORDER BY date DESC
        ''', (f['id'],)).fetchall()
        faculty_rec['academic'] = [dict(a) for a in a_logs]
        
        # 3. Fetch all research logs
        r_logs = db.execute('''
            SELECT * FROM research_activities
            WHERE faculty_id = ?
            ORDER BY created_at DESC
        ''', (f['id'],)).fetchall()
        faculty_rec['research'] = [dict(r) for r in r_logs]
        
        report_data.append(faculty_rec)
        report_data.append(faculty_rec)
        
    return render_template('hod_accreditation.html', report_data=report_data)

# Fair Workload Distribution Component
@app.route('/hod/task_distribution', methods=['GET'])
def task_distribution():
    if session.get('role') != 'hod': return redirect(url_for('index'))
    db = get_db()
    dept_id = session.get('dept_id')
    
    faculties = db.execute('SELECT id, name, email FROM users WHERE department_id = ? AND role = "faculty"', (dept_id,)).fetchall()
    
    distribution_list = []
    for f in faculties:
        # Utilize the existing logic to accurately gauge current exact workload
        w = get_faculty_workload(db, f['id'])
        teaching = w['teaching']
        academic = w['academic']
        research = w['research']
        
        # Pull any currently assigned unfinished tasks from the new Fair Distribution module
        assigned_tasks = db.execute('SELECT SUM(effort_weight) as effort FROM tasks WHERE assigned_to = ? AND status != "Completed"', (f['id'],)).fetchone()['effort'] or 0
        
        # Our "Fairness Score" is the aggregation of all their current responsibilities
        fairness_score = teaching + academic + research + float(assigned_tasks)
        
        distribution_list.append({
            'id': f['id'],
            'name': f['name'],
            'email': f['email'],
            'teaching': teaching,
            'academic': academic,
            'research': research,
            'assigned_effort': float(assigned_tasks),
            'fairness_score': fairness_score
        })
        
    # Sort faculty from lowest workload (healthiest) to highest workload
    distribution_list.sort(key=lambda x: x['fairness_score'])
    
    # Fetch existing tasks to show in the list
    all_tasks = db.execute('''
        SELECT t.*, u.name as assigned_name 
        FROM tasks t
        LEFT JOIN users u ON t.assigned_to = u.id
        WHERE t.department_id = ?
        ORDER BY t.created_at DESC
    ''', (dept_id,)).fetchall()
    
    return render_template('hod_task_distribution.html', faculty=distribution_list, tasks=all_tasks)

@app.route('/hod/assign_task', methods=['POST'])
def assign_task():
    if session.get('role') != 'hod': return redirect(url_for('index'))
    db = get_db()
    
    title = request.form.get('title')
    category = request.form.get('category')
    effort_weight = request.form.get('effort_weight')
    assigned_to = request.form.get('assigned_to')
    
    db.execute('''
        INSERT INTO tasks (title, description, category, effort_weight, status, assigned_to, department_id)
        VALUES (?, ?, ?, ?, 'Assigned', ?, ?)
    ''', (title, request.form.get('description', ''), category, effort_weight, assigned_to, session.get('dept_id')))
    db.commit()
    
    return redirect(url_for('task_distribution'))

# Weekly Schedule Optimization Routes
@app.route('/hod/schedule_optimization', methods=['GET'])
def schedule_optimization():
    if session.get('role') != 'hod': return redirect(url_for('index'))
    db = get_db()
    dept_id = session.get('dept_id')
    from datetime import datetime, timedelta
    today = datetime.now().date()
    
    # 7-day window: -3 to +3
    dates = [(today + timedelta(days=i)).strftime('%Y-%m-%d') for i in range(-3, 4)]
    
    faculties = db.execute('SELECT id, name FROM users WHERE department_id = ? AND role = "faculty"', (dept_id,)).fetchall()
    
    # Build per-faculty workload matrix
    faculty_matrix = []
    for f in faculties:
        row = {'id': f['id'], 'name': f['name'], 'days': []}
        for d in dates:
            stats = get_daily_workload(db, f['id'], d)
            row['days'].append({
                'date': d,
                'label': d,
                'percentage': stats['percentage'],
                'total_hours': stats['total_hours'],
                'status': stats['status']
            })
        row['avg'] = round(sum(d['percentage'] for d in row['days']) / 7, 1)
        row['overloaded'] = any(d['percentage'] >= 90 for d in row['days'])
        faculty_matrix.append(row)
    
    # All weekly schedule entries for this dept in the window
    schedules = db.execute('''
        SELECT ws.*, u.name as faculty_name 
        FROM weekly_schedules ws
        JOIN users u ON ws.faculty_id = u.id
        WHERE ws.department_id = ? AND ws.date BETWEEN ? AND ?
        ORDER BY ws.date, ws.start_time
    ''', (dept_id, dates[0], dates[-1])).fetchall()
    
    return render_template('hod_schedule_optimization.html',
                           faculty_matrix=faculty_matrix,
                           faculties=faculties,
                           schedules=[dict(s) for s in schedules],
                           dates=dates,
                           today=str(today))

@app.route('/hod/add_schedule', methods=['POST'])
def add_schedule():
    if session.get('role') != 'hod': return redirect(url_for('index'))
    db = get_db()
    
    faculty_id = request.form.get('faculty_id')
    activity_type = request.form.get('activity_type')
    task_name = request.form.get('task_name')
    date = request.form.get('date')
    start_time = request.form.get('start_time')
    end_time = request.form.get('end_time')
    duration = request.form.get('duration')
    
    db.execute('''
        INSERT INTO weekly_schedules (faculty_id, department_id, activity_type, task_name, date, start_time, end_time, duration)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (faculty_id, session.get('dept_id'), activity_type, task_name, date, start_time, end_time, duration))
    db.commit()
    return redirect(url_for('schedule_optimization'))

@app.route('/hod/delete_schedule/<int:schedule_id>', methods=['POST'])
def delete_schedule(schedule_id):
    if session.get('role') != 'hod': return redirect(url_for('index'))
    db = get_db()
    db.execute('DELETE FROM weekly_schedules WHERE id = ?', (schedule_id,))
    db.commit()
    return redirect(url_for('schedule_optimization'))

@app.route('/hod/reassign_schedule/<int:schedule_id>', methods=['POST'])
def reassign_schedule(schedule_id):
    if session.get('role') != 'hod': return redirect(url_for('index'))
    db = get_db()
    new_faculty_id = request.form.get('new_faculty_id')
    new_date = request.form.get('new_date')
    db.execute('UPDATE weekly_schedules SET faculty_id = ?, date = ? WHERE id = ?',
               (new_faculty_id, new_date, schedule_id))
    db.commit()
    return redirect(url_for('schedule_optimization'))

# Fair Workload Redistribution Module
@app.route('/hod/redistribution')
def redistribution():
    if session.get('role') != 'hod': return redirect(url_for('index'))
    db = get_db()
    dept_id = session.get('dept_id')
    from datetime import datetime, timedelta

    today = datetime.now().date()
    today_str = today.strftime('%Y-%m-%d')

    faculties = db.execute(
        'SELECT id, name FROM users WHERE department_id = ? AND role = "faculty"', (dept_id,)
    ).fetchall()

    OVERLOAD_THRESHOLD = 90.0  # % of 8-hr day
    faculty_status = []
    overloaded = []
    available = []

    for f in faculties:
        stats = get_daily_workload(db, f['id'], today_str)
        pct = stats['percentage']
        capacity_left = max(0.0, round((100.0 - pct) / 100.0 * 8.0, 2))
        entry = {
            'id': f['id'],
            'name': f['name'],
            'percentage': round(pct, 1),
            'total_hours': stats['total_hours'],
            'capacity_left': capacity_left,
            'status': stats['status'],
        }
        faculty_status.append(entry)
        if pct >= OVERLOAD_THRESHOLD:
            overloaded.append(entry)
        else:
            available.append(entry)

    # Sort available by most capacity (lowest %)
    available.sort(key=lambda x: x['percentage'])

    # Get today's schedule entries for overloaded faculty that can be moved
    suggestions = []
    for ol in overloaded:
        ws_entries = db.execute('''
            SELECT * FROM weekly_schedules WHERE faculty_id = ? AND date = ?
            ORDER BY duration DESC
        ''', (ol['id'], today_str)).fetchall()

        for entry in ws_entries:
            # Find best recipient with enough capacity
            for av in available:
                if av['capacity_left'] >= entry['duration']:
                    suggestions.append({
                        'schedule_id': entry['id'],
                        'task_name': entry['task_name'],
                        'activity_type': entry['activity_type'],
                        'duration': entry['duration'],
                        'from_name': ol['name'],
                        'from_id': ol['id'],
                        'from_pct': ol['percentage'],
                        'to_name': av['name'],
                        'to_id': av['id'],
                        'to_pct': av['percentage'],
                        'new_from_pct': round(ol['percentage'] - (entry['duration'] / 8.0 * 100), 1),
                        'new_to_pct': round(av['percentage'] + (entry['duration'] / 8.0 * 100), 1),
                    })
                    break  # one suggestion per entry

    return render_template('hod_redistribution.html',
                           faculty_status=faculty_status,
                           overloaded=overloaded,
                           available=available,
                           suggestions=suggestions,
                           today=today_str)

@app.route('/hod/apply_redistribution/<int:schedule_id>', methods=['POST'])
def apply_redistribution(schedule_id):
    if session.get('role') != 'hod': return redirect(url_for('index'))
    db = get_db()
    new_faculty_id = request.form.get('new_faculty_id')
    db.execute('UPDATE weekly_schedules SET faculty_id = ? WHERE id = ?', (new_faculty_id, schedule_id))
    db.commit()
    return redirect(url_for('redistribution'))

@app.route('/hod/dashboard')
def hod_dashboard():
    if session.get('role') != 'hod': return redirect(url_for('index'))
    db = get_db()
    dept_filter = request.args.get('department_id', session.get('dept_id'))
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    pending_academic = db.execute('SELECT a.*, u.name as faculty_name FROM academic_activities a JOIN users u ON a.faculty_id = u.id WHERE u.department_id = ? AND a.status = "Pending"', (dept_filter,)).fetchall()
    pending_research = db.execute('SELECT r.*, u.name as faculty_name FROM research_activities r JOIN users u ON r.faculty_id = u.id WHERE u.department_id = ? AND r.status = "Pending"', (dept_filter,)).fetchall()
    pending_roles = db.execute('SELECT ar.*, u.name as faculty_name FROM admin_roles ar JOIN users u ON ar.faculty_id = u.id WHERE u.department_id = ? AND ar.status = "Pending"', (dept_filter,)).fetchall()
    
    dept_stats = get_department_stats(db, dept_filter, start_date, end_date)
    
    return render_template('hod_dashboard.html', 
                           pending_academic=pending_academic, 
                           pending_research=pending_research, 
                           pending_roles=pending_roles,
                           stats=dept_stats,
                           departments=db.execute('SELECT * FROM departments').fetchall(),
                           selected_dept=int(dept_filter))

@app.route('/hod/approve/<type>/<int:id>/<action>')
def hod_approve(type, id, action):
    if session.get('role') != 'hod': return redirect(url_for('index'))
    db = get_db()
    status = 'Approved' if action == 'approve' else 'Rejected'
    table = 'academic_activities' if type == 'academic' else ('research_activities' if type == 'research' else 'admin_roles')
    db.execute(f'UPDATE {table} SET status = ? WHERE id = ?', (status, id))
    db.commit()
    return redirect(url_for('hod_dashboard'))

# API for Charts
@app.route('/api/personal_workload')
def personal_workload():
    if 'user_id' not in session: return jsonify({})
    db = get_db()
    
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    w = get_faculty_workload(db, session['user_id'], start_date, end_date)
    
    return jsonify({
        "Teaching": w['teaching'],
        "Academic": w['academic'],
        "Research": w['research'],
        "Total": w['total']
    })

@app.route('/api/institutional_workload')
def institutional_workload():
    db = get_db()
    depts = db.execute('SELECT * FROM departments').fetchall()
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    data = []
    for d in depts:
        stats = get_department_stats(db, d['id'], start_date, end_date)
        teaching_credits = stats['teaching_hours']
        research_credits = stats['research_papers'] * 5
        
        # Academic for whole dept (Not fully encompassed by get_department_stats which only totals teaching and research papers)
        # Let's add academic to get_department_stats mentally, or just compute it cleanly by summing get_faculty_workload total
        
        faculties = db.execute('SELECT id FROM users WHERE department_id = ? AND role = "faculty"', (d['id'],)).fetchall()
        total_dept_workload = 0
        for f in faculties:
            w = get_faculty_workload(db, f['id'], start_date, end_date)
            total_dept_workload += w['total']
            
        data.append({'name': d['name'], 'workload': float(total_dept_workload)})
    return jsonify(data)

@app.route('/api/workload_comparison')
def workload_comparison():
    if 'dept_id' not in session: return jsonify([])
    db = get_db()
    
    dept_id = request.args.get('department_id', session['dept_id'])
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    faculties = db.execute('SELECT id, name FROM users WHERE department_id = ? AND role = "faculty"', (dept_id,)).fetchall()
    data = []
    for f in faculties:
        w = get_faculty_workload(db, f['id'], start_date, end_date)
        
        # Get pending activities count
        pending_academic = db.execute('SELECT COUNT(*) as count FROM academic_activities WHERE faculty_id = ? AND status = "Pending"', (f['id'],)).fetchone()['count']
        pending_research = db.execute('SELECT COUNT(*) as count FROM research_activities WHERE faculty_id = ? AND status = "Pending"', (f['id'],)).fetchone()['count']
        pending_total = pending_academic + pending_research
        
        data.append({
            'id': f['id'],
            'name': f['name'], 
            'workload': w['total'],
            'teaching': w['teaching'],
            'academic': w['academic'],
            'research': w['research'],
            'pending': pending_total
        })
    data.sort(key=lambda x: x['workload'], reverse=True)
    return jsonify(data)

@app.route('/api/time_analysis/<int:faculty_id>')
def time_analysis(faculty_id):
    if 'user_id' not in session: return jsonify({"error": "Unauthorized"}), 401
    # Only HOD or the faculty themselves can see this data
    if session.get('role') != 'hod' and session.get('user_id') != faculty_id:
        return jsonify({"error": "Unauthorized"}), 403
        
    db = get_db()
    from datetime import datetime, timedelta
    
    today = datetime.now().date()
    payload = []
    
    for i in range(-3, 4):
        target_date = today + timedelta(days=i)
        date_str = target_date.strftime('%Y-%m-%d')
        daily_stats = get_daily_workload(db, faculty_id, date_str)
        
        if i == -1:
            daily_stats['label'] = 'Yesterday'
        elif i == 0:
            daily_stats['label'] = 'Today'
        elif i == 1:
            daily_stats['label'] = 'Tomorrow'
        else:
            daily_stats['label'] = target_date.strftime('%b %d')
            
        payload.append(daily_stats)
        
    return jsonify(payload)

@app.route('/api/department_time_analysis')
def department_time_analysis():
    if session.get('role') != 'hod': return jsonify({"error": "Unauthorized"}), 403
        
    db = get_db()
    dept_id = session.get('dept_id')
    faculties = db.execute('SELECT id, name FROM users WHERE department_id = ? AND role = "faculty"', (dept_id,)).fetchall()
    
    from datetime import datetime, timedelta
    today = datetime.now().date()
    
    response_data = {'trend': [], 'faculty_table': []}
    
    for i in range(-3, 4):
        target_date = today + timedelta(days=i)
        date_str = target_date.strftime('%Y-%m-%d')
        
        day_total = 0.0
        for f in faculties:
            stats = get_daily_workload(db, f['id'], date_str)
            day_total += stats['total_hours']
            
        avg_percentage = (day_total / (max(len(faculties), 1) * 8.0)) * 100
        
        label = target_date.strftime('%b %d')
        if i == -1: label = 'Yesterday'
        elif i == 0: label = 'Today'
        elif i == 1: label = 'Tomorrow'
            
        response_data['trend'].append({
            'label': label,
            'percentage': round(avg_percentage, 1),
            'total_hours': round(day_total, 1)
        })
        
    yesterday_str = (today + timedelta(days=-1)).strftime('%Y-%m-%d')
    today_str = today.strftime('%Y-%m-%d')
    tomorrow_str = (today + timedelta(days=1)).strftime('%Y-%m-%d')
    
    for f in faculties:
        y_stats = get_daily_workload(db, f['id'], yesterday_str)
        t_stats = get_daily_workload(db, f['id'], today_str)
        tm_stats = get_daily_workload(db, f['id'], tomorrow_str)
        
        avg_workload = (y_stats['percentage'] + t_stats['percentage'] + tm_stats['percentage']) / 3.0
        color = 'green'
        if avg_workload >= 80: color = 'red'
        elif avg_workload >= 50: color = 'yellow'
            
        response_data['faculty_table'].append({
            'name': f['name'],
            'yesterday': y_stats['percentage'],
            'today': t_stats['percentage'],
            'tomorrow': tm_stats['percentage'],
            'avg_workload': round(avg_workload, 1),
            'status': color
        })
        
    return jsonify(response_data)

# ══════ CLASS CONDUCT TRACKING SYSTEM ══════════════════════════════════

def seed_today_conduct(db, faculty_id):
    """Ensure all of today's timetable slots have a Pending record in class_conduct."""
    from datetime import datetime
    today_str = datetime.now().strftime('%Y-%m-%d')
    today_day = datetime.now().strftime('%a').upper()
    slots = db.execute('''
        SELECT t.id FROM timetable t
        JOIN timeslots ts ON t.timeslot_id = ts.id
        WHERE t.faculty_id = ? AND t.day = ? AND ts.is_break = 0
    ''', (faculty_id, today_day)).fetchall()
    for s in slots:
        db.execute('''
            INSERT OR IGNORE INTO class_conduct (faculty_id, timetable_id, date, status, points)
            VALUES (?, ?, ?, 'Pending', 0)
        ''', (faculty_id, s['id'], today_str))
    db.commit()

@app.route('/api/today_conduct_schedule')
def today_conduct_schedule():
    if 'user_id' not in session:
        return jsonify([]), 401
    db = get_db()
    faculty_id = session['user_id']
    from datetime import datetime
    today_str = datetime.now().strftime('%Y-%m-%d')
    today_day = datetime.now().strftime('%a').upper()

    seed_today_conduct(db, faculty_id)

    rows = db.execute('''
        SELECT t.id as timetable_id, ts.start_time, ts.end_time, c.course_name,
               c.subject_code, c.is_lab, s.name as section_name, t.room_no,
               COALESCE(cc.status, 'Pending') as status,
               COALESCE(cc.reason, '') as reason,
               COALESCE(cc.points, 0) as points,
               cc.id as conduct_id
        FROM timetable t
        JOIN timeslots ts ON t.timeslot_id = ts.id
        JOIN courses c ON t.course_id = c.id
        JOIN sections s ON t.section_id = s.id
        LEFT JOIN class_conduct cc ON cc.timetable_id = t.id AND cc.faculty_id = ? AND cc.date = ?
        WHERE t.faculty_id = ? AND t.day = ? AND ts.is_break = 0
        ORDER BY ts.start_time
    ''', (faculty_id, today_str, faculty_id, today_day)).fetchall()

    return jsonify([dict(r) for r in rows])

@app.route('/faculty/mark_conduct', methods=['POST'])
def mark_conduct():
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    db = get_db()
    faculty_id = session['user_id']
    data = request.json
    timetable_id = data.get('timetable_id')
    status = data.get('status')  # 'Conducted' or 'Not Conducted'
    reason = data.get('reason', '')
    from datetime import datetime
    today_str = datetime.now().strftime('%Y-%m-%d')

    # Determine workload points
    is_lab = db.execute('SELECT c.is_lab FROM timetable t JOIN courses c ON t.course_id=c.id WHERE t.id=?', (timetable_id,)).fetchone()
    points = 0.0
    if status == 'Conducted':
        points = 1.5 if (is_lab and is_lab['is_lab']) else 1.0

    db.execute('''
        INSERT INTO class_conduct (faculty_id, timetable_id, date, status, reason, conducted_at, points)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(faculty_id, timetable_id, date) DO UPDATE SET
            status=excluded.status, reason=excluded.reason,
            conducted_at=excluded.conducted_at, points=excluded.points
    ''', (faculty_id, timetable_id, today_str, status, reason,
          datetime.now().strftime('%Y-%m-%d %H:%M:%S') if status == 'Conducted' else None,
          points))
    db.commit()

    # Build updated totals for the response
    total_today = db.execute(
        'SELECT SUM(points) as t FROM class_conduct WHERE faculty_id=? AND date=? AND status="Conducted"',
        (faculty_id, today_str)
    ).fetchone()['t'] or 0

    return jsonify({"success": True, "points": points, "total_today": round(total_today, 1)})

@app.route('/api/conduct_leaderboard')
def conduct_leaderboard():
    """Department-wide workload leaderboard for HOD dashboard."""
    if 'user_id' not in session:
        return jsonify([]), 401
    db = get_db()
    dept_id = session.get('dept_id') if session.get('role') == 'hod' else None
    from datetime import datetime
    today_str = datetime.now().strftime('%Y-%m-%d')

    if dept_id:
        faculties = db.execute('SELECT id, name FROM users WHERE department_id=? AND role="faculty"', (dept_id,)).fetchall()
    else:
        faculties = db.execute('SELECT id, name FROM users WHERE role="faculty"', ()).fetchall()

    board = []
    for f in faculties:
        w = get_faculty_workload(db, f['id'])
        conduct_pts = db.execute(
            'SELECT COALESCE(SUM(points),0) as p FROM class_conduct WHERE faculty_id=? AND status="Conducted"',
            (f['id'],)
        ).fetchone()['p']
        today_pts = db.execute(
            'SELECT COALESCE(SUM(points),0) as p FROM class_conduct WHERE faculty_id=? AND date=? AND status="Conducted"',
            (f['id'], today_str)
        ).fetchone()['p']
        board.append({
            'name': f['name'],
            'workload_score': w['total'],
            'conduct_points': round(float(conduct_pts), 1),
            'today_points': round(float(today_pts), 1)
        })

    board.sort(key=lambda x: x['workload_score'], reverse=True)
    return jsonify(board)

@app.route('/api/class_alerts')
def class_alerts():
    """Returns today's upcoming classes for the logged-in faculty within the alert window."""
    if 'user_id' not in session:
        return jsonify([]), 401

    db = get_db()
    faculty_id = session['user_id']
    advance_minutes = int(request.args.get('advance', 30))  # default: 30 min before

    from datetime import datetime, timedelta
    now = datetime.now()
    today_day = now.strftime('%a').upper()  # 'MON','TUE', etc.
    today_str = now.strftime('%Y-%m-%d')

    # Fetch today's scheduled classes from timetable
    classes = db.execute('''
        SELECT ts.start_time, ts.end_time, c.course_name, c.subject_code, c.is_lab,
               t.room_no, s.name as section_name
        FROM timetable t
        JOIN timeslots ts ON t.timeslot_id = ts.id
        JOIN courses c ON t.course_id = c.id
        JOIN sections s ON t.section_id = s.id
        WHERE t.faculty_id = ? AND t.day = ? AND ts.is_break = 0
        ORDER BY ts.start_time
    ''', (faculty_id, today_day)).fetchall()

    alerts = []
    for cls in classes:
        # Parse start_time — handle "HH:MM AM/PM" or "HH:MM"
        try:
            st = cls['start_time'].strip()
            if 'AM' in st.upper() or 'PM' in st.upper():
                class_time = datetime.strptime(f"{today_str} {st}", '%Y-%m-%d %I:%M %p')
            else:
                class_time = datetime.strptime(f"{today_str} {st}", '%Y-%m-%d %H:%M')
        except Exception:
            continue  # skip unparseable times

        minutes_until = (class_time - now).total_seconds() / 60

        status = None
        if 0 <= minutes_until <= advance_minutes:
            status = 'upcoming'
        elif -30 <= minutes_until < 0:
            status = 'starting_now'
        elif minutes_until > advance_minutes:
            status = 'later'

        if status in ('upcoming', 'starting_now'):
            alerts.append({
                'course_name': cls['course_name'],
                'subject_code': cls['subject_code'],
                'section': cls['section_name'],
                'room': cls['room_no'],
                'start_time': cls['start_time'],
                'end_time': cls['end_time'],
                'is_lab': bool(cls['is_lab']),
                'minutes_until': round(minutes_until, 1),
                'status': status
            })

    return jsonify(alerts)

@app.route('/api/todays_schedule')
def todays_schedule():
    """Returns all of today's classes for the faculty (for the full schedule panel)."""
    if 'user_id' not in session:
        return jsonify([]), 401

    db = get_db()
    faculty_id = session['user_id']
    from datetime import datetime
    today_day = datetime.now().strftime('%a').upper()

    classes = db.execute('''
        SELECT ts.start_time, ts.end_time, c.course_name, c.subject_code, c.is_lab,
               t.room_no, s.name as section_name
        FROM timetable t
        JOIN timeslots ts ON t.timeslot_id = ts.id
        JOIN courses c ON t.course_id = c.id
        JOIN sections s ON t.section_id = s.id
        WHERE t.faculty_id = ? AND t.day = ? AND ts.is_break = 0
        ORDER BY ts.start_time
    ''', (faculty_id, today_day)).fetchall()

    return jsonify([dict(c) for c in classes])

@app.route('/api/workload_trends')
def workload_trends():
    db = get_db()
    
    # 1. Determine entity scope (HOD sees dept trends by default, faculty sees personal trends)
    dept_id = request.args.get('department_id', session.get('dept_id')) if session.get('role') == 'hod' else session.get('dept_id')
    user_id = request.args.get('user_id', session.get('user_id')) if session.get('role') != 'faculty' else session.get('user_id')
    
    if session.get('role') == 'hod' and not request.args.get('user_id'):
        # Department wide trends
        users = db.execute('SELECT id FROM users WHERE department_id = ? AND role = "faculty"', (dept_id,)).fetchall()
        user_ids = [u['id'] for u in users]
    else:
        # Specific user trends
        user_ids = [user_id]
        
    if not user_ids:
        return jsonify({"labels": [], "data": []})

    # Prepare user_ids for SQL IN clause
    placeholders = ','.join('?' * len(user_ids))
    
    # We want a 6-month trailing window natively
    # Query Academic & Mentoring
    academic = db.execute(f'''
        SELECT substr(date, 1, 7) as month, SUM(hours) as total
        FROM academic_activities
        WHERE faculty_id IN ({placeholders}) AND status = 'Approved'
        GROUP BY month
        ORDER BY month DESC LIMIT 6
    ''', user_ids).fetchall()

    # Query Teaching (using date)
    teaching = db.execute(f'''
        SELECT substr(tw.date, 1, 7) as month, SUM(tw.hours_per_week * (CASE WHEN c.is_lab = 1 THEN 4 ELSE 3 END)) as total
        FROM teaching_workload tw
        JOIN courses c ON tw.course_id = c.id
        WHERE tw.faculty_id IN ({placeholders})
        GROUP BY month
        ORDER BY month DESC LIMIT 6
    ''', user_ids).fetchall()

    # Query Research (using created_at)
    research = db.execute(f'''
        SELECT substr(created_at, 1, 7) as month, COUNT(*) * 5 as total
        FROM research_activities
        WHERE faculty_id IN ({placeholders}) AND status = 'Approved'
        GROUP BY month
        ORDER BY month DESC LIMIT 6
    ''', user_ids).fetchall()

    # Combine data into an aggregated dictionary
    monthly_data = {}
    
    for record in academic:
        m = record['month']
        monthly_data[m] = monthly_data.get(m, 0) + record['total']
        
    for record in teaching:
        m = record['month']
        monthly_data[m] = monthly_data.get(m, 0) + record['total']
        
    for record in research:
        m = record['month']
        monthly_data[m] = monthly_data.get(m, 0) + record['total']

    # Sort months chronologically
    sorted_months = sorted(monthly_data.keys())
    
    labels = []
    data = []
    for month in sorted_months:
        labels.append(month)
        data.append(monthly_data[month])
        
    if not labels:
        import datetime
        cur_month = datetime.datetime.now().strftime('%Y-%m')
        labels = [cur_month]
        data = [0]
        
    return jsonify({"labels": labels, "data": data})

@app.route('/api/chatbot', methods=['POST'])
def chatbot_query():
    if 'user_id' not in session:
        return jsonify({"response": "Please login first."}), 401

    role = session['role']
    raw_data = request.json
    query = raw_data.get('query', '').lower().strip()
    db = get_db()
    user_id = session['user_id']
    dept_id = session.get('dept_id')

    from datetime import datetime, timedelta
    now = datetime.now()
    today_str = now.strftime('%Y-%m-%d')
    yesterday_str = (now - timedelta(days=1)).strftime('%Y-%m-%d')
    today_day = now.strftime('%a').upper()

    def find_faculty_in_query(scope_dept_id=None):
        where = 'role = "faculty"' + (f' AND department_id = {scope_dept_id}' if scope_dept_id else '')
        all_f = db.execute(f'SELECT id, name FROM users WHERE {where}').fetchall()
        for f in all_f:
            parts = f['name'].lower().split()
            if any(p in query for p in parts if len(p) > 2):
                return dict(f)
        return None

    def fmt_workload(name, w):
        return (f"📊 **{name}**\n"
                f"• Teaching: {w['teaching']} credits\n"
                f"• Academic: {w['academic']} credits\n"
                f"• Research: {w['research']} credits\n"
                f"• **Total: {w['total']} credits**")

    # INTENT 1: TIMETABLE
    timetable_kw = ['timetable','schedule','class','classes','slot','next class','today class','when is']
    if any(k in query for k in timetable_kw):
        target_id, target_name = user_id, session['name']
        if role in ('hod', 'admin'):
            found = find_faculty_in_query(dept_id if role == 'hod' else None)
            if found:
                target_id, target_name = found['id'], found['name']

        target_day = today_day
        if 'tomorrow' in query:
            target_day = (now + timedelta(days=1)).strftime('%a').upper()
        elif 'yesterday' in query:
            target_day = (now - timedelta(days=1)).strftime('%a').upper()
        for day_full, day_abbr in [('monday','MON'),('tuesday','TUE'),('wednesday','WED'),
                                    ('thursday','THU'),('friday','FRI'),('saturday','SAT')]:
            if day_full in query:
                target_day = day_abbr

        classes = db.execute('''
            SELECT ts.start_time, ts.end_time, c.course_name, c.subject_code, t.room_no, s.name as sec
            FROM timetable t
            JOIN timeslots ts ON t.timeslot_id = ts.id
            JOIN courses c ON t.course_id = c.id
            JOIN sections s ON t.section_id = s.id
            WHERE t.faculty_id = ? AND t.day = ? AND ts.is_break = 0
            ORDER BY ts.start_time
        ''', (target_id, target_day)).fetchall()

        day_label = {'MON':'Monday','TUE':'Tuesday','WED':'Wednesday','THU':'Thursday',
                     'FRI':'Friday','SAT':'Saturday'}.get(target_day, target_day)
        if not classes:
            return jsonify({"response": f"📅 No classes for **{target_name}** on {day_label}."})
        lines = [f"📅 **{target_name}'s {day_label} Schedule:**"]
        for c in classes:
            lines.append(f"• {c['start_time']}–{c['end_time']} | {c['course_name']} ({c['subject_code']}) | Room {c['room_no']} | {c['sec']}")
        return jsonify({"response": "\n".join(lines)})

    # INTENT 2: FACULTY PROFILE
    profile_kw = ['profile','info','details','who is','tell me about','show me']
    if any(k in query for k in profile_kw):
        if role in ('hod', 'admin'):
            found = find_faculty_in_query(dept_id if role == 'hod' else None)
            if found:
                fd = db.execute('SELECT * FROM faculty_details WHERE faculty_id = ?', (found['id'],)).fetchone()
                dept_row = db.execute('SELECT name FROM departments WHERE id = (SELECT department_id FROM users WHERE id = ?)', (found['id'],)).fetchone()
                lines = [f"👤 **Profile: {found['name']}**"]
                if fd:
                    lines.append(f"• Designation: {fd['designation'] or 'N/A'}")
                    lines.append(f"• Qualification: {fd['qualification'] or 'N/A'}")
                    lines.append(f"• Experience: {fd['experience'] or 'N/A'} years")
                lines.append(f"• Department: {dept_row['name'] if dept_row else 'N/A'}")
                return jsonify({"response": "\n".join(lines)})
        fd = db.execute('SELECT * FROM faculty_details WHERE faculty_id = ?', (user_id,)).fetchone()
        if fd:
            return jsonify({"response": f"👤 **Your Profile**\n• Designation: {fd['designation']}\n• Qualification: {fd['qualification']}\n• Experience: {fd['experience']} years"})
        return jsonify({"response": "No profile details found. Please update your profile."})

    # INTENT 3: WORKLOAD
    workload_kw = ['workload','credits','load','teaching load']
    if any(k in query for k in workload_kw):
        rank_kw = ['highest','most','top','who has','ranking','list','compare','all']
        avail_kw = ['available','can take','additional','free','capacity','light']

        if any(k in query for k in avail_kw) and role in ('hod','admin'):
            faculties = db.execute('SELECT id, name FROM users WHERE department_id = ? AND role="faculty"', (dept_id,)).fetchall()
            available = []
            for f in faculties:
                w = get_faculty_workload(db, f['id'])
                if w['total'] < 30:
                    available.append(f"• {f['name']}: {w['total']} credits")
            if available:
                return jsonify({"response": "✅ **Faculty with available capacity:**\n" + "\n".join(available)})
            return jsonify({"response": "All faculty currently have high workloads."})

        if any(k in query for k in rank_kw) and role in ('hod','admin'):
            faculties = db.execute('SELECT id, name FROM users WHERE department_id = ? AND role="faculty"', (dept_id,)).fetchall()
            stats = sorted([{"name": f['name'], "total": get_faculty_workload(db, f['id'])['total']} for f in faculties],
                           key=lambda x: x['total'], reverse=True)
            if any(k in query for k in ['highest','top','most']):
                top = stats[0]
                return jsonify({"response": f"🏆 **{top['name']}** has the highest workload with **{top['total']} credits**."})
            lines = ["📋 **Department Workload Ranking:**"]
            for i, s in enumerate(stats[:8]):
                lines.append(f"{i+1}. {s['name']}: {s['total']} credits")
            return jsonify({"response": "\n".join(lines)})

        if role in ('hod', 'admin'):
            found = find_faculty_in_query(dept_id if role == 'hod' else None)
            if found:
                w = get_faculty_workload(db, found['id'])
                return jsonify({"response": fmt_workload(found['name'], w)})

        w = get_faculty_workload(db, user_id)
        return jsonify({"response": fmt_workload(session['name'], w)})

    # INTENT 4: DAILY WORKLOAD
    daily_kw = ['yesterday','today workload','hours today','hours yesterday','daily workload']
    if any(k in query for k in daily_kw):
        target_date = today_str
        date_label = "Today"
        if 'yesterday' in query:
            target_date = yesterday_str
            date_label = "Yesterday"
        target_id, target_name = user_id, session['name']
        if role in ('hod','admin'):
            found = find_faculty_in_query(dept_id if role == 'hod' else None)
            if found:
                target_id, target_name = found['id'], found['name']
        stats = get_daily_workload(db, target_id, target_date)
        icons = {"green":"🟢","yellow":"🟡","red":"🔴"}
        icon = icons.get(stats['status'], "⚪")
        return jsonify({"response":
            f"📆 **{date_label} — {target_name}**\n"
            f"• Teaching: {stats['teaching_hours']}h\n"
            f"• Academic: {stats['academic_hours']}h\n"
            f"• Total: **{stats['total_hours']}h / 8h ({stats['percentage']}%)**\n"
            f"• Status: {icon} {stats['status'].title()}"
        })

    # INTENT 5: ACTIVITIES
    activity_kw = ['activity','activities','mentoring','academic task','assignment']
    if any(k in query for k in activity_kw):
        target_id, target_name = user_id, session['name']
        if role in ('hod','admin'):
            found = find_faculty_in_query(dept_id if role == 'hod' else None)
            if found:
                target_id, target_name = found['id'], found['name']
        filter_date = None
        if 'yesterday' in query: filter_date = yesterday_str
        elif 'today' in query: filter_date = today_str
        where_date = f' AND date = "{filter_date}"' if filter_date else ''
        rows = db.execute(f'SELECT title, activity_type, hours, status, date FROM academic_activities WHERE faculty_id = ? {where_date} ORDER BY date DESC LIMIT 8', (target_id,)).fetchall()
        if not rows:
            return jsonify({"response": f"No activities found for **{target_name}**."})
        label = "Yesterday" if filter_date == yesterday_str else ("Today" if filter_date else "Recent")
        lines = [f"📋 **{label} Activities — {target_name}:**"]
        for r in rows:
            lines.append(f"• [{r['status']}] {r['title']} ({r['activity_type']}) — {r['hours']}h on {r['date']}")
        return jsonify({"response": "\n".join(lines)})

    # INTENT 6: RESEARCH
    research_kw = ['research','paper','publication','journal','conference']
    if any(k in query for k in research_kw):
        if role in ('hod','admin'):
            found = find_faculty_in_query(dept_id if role == 'hod' else None)
            if found:
                rows = db.execute('SELECT title, status FROM research_activities WHERE faculty_id = ? ORDER BY created_at DESC LIMIT 5', (found['id'],)).fetchall()
                lines = [f"🔬 **Research: {found['name']}**"]
                for r in rows:
                    lines.append(f"• [{r['status']}] {r['title']}")
                return jsonify({"response": "\n".join(lines) if rows else f"No research records for {found['name']}."})
            faculties = db.execute('SELECT id, name FROM users WHERE department_id = ? AND role="faculty"', (dept_id,)).fetchall()
            stats = []
            for f in faculties:
                cnt = db.execute('SELECT COUNT(*) as c FROM research_activities WHERE faculty_id = ? AND status="Approved"', (f['id'],)).fetchone()['c']
                stats.append({'name': f['name'], 'count': cnt})
            stats.sort(key=lambda x: x['count'], reverse=True)
            lines = ["🔬 **Department Research Output:**"]
            for s in stats[:8]:
                lines.append(f"• {s['name']}: {s['count']} papers")
            return jsonify({"response": "\n".join(lines)})
        cnt = db.execute('SELECT COUNT(*) as c FROM research_activities WHERE faculty_id = ? AND status="Approved"', (user_id,)).fetchone()['c']
        return jsonify({"response": f"🔬 You have **{cnt} approved research papers**."})

    # INTENT 7: PENDING / APPROVALS
    pending_kw = ['pending','approve','approval','waiting','submitted']
    if any(k in query for k in pending_kw):
        if role == 'hod':
            a = db.execute('SELECT COUNT(*) as c FROM academic_activities a JOIN users u ON a.faculty_id=u.id WHERE u.department_id=? AND a.status="Pending"', (dept_id,)).fetchone()['c']
            r = db.execute('SELECT COUNT(*) as c FROM research_activities r JOIN users u ON r.faculty_id=u.id WHERE u.department_id=? AND r.status="Pending"', (dept_id,)).fetchone()['c']
            return jsonify({"response": f"📨 **Pending Approvals:**\n• Academic: {a}\n• Research: {r}\n• **Total: {a+r} items**"})
        total = db.execute('SELECT (SELECT COUNT(*) FROM academic_activities WHERE faculty_id=? AND status="Pending") + (SELECT COUNT(*) FROM research_activities WHERE faculty_id=? AND status="Pending") as t', (user_id, user_id)).fetchone()['t']
        return jsonify({"response": f"📨 You have **{total} items** pending HOD approval."})

    # INTENT 8: REDISTRIBUTION
    redist_kw = ['redistribute','redistribution','overloaded','who can take','fair distribution','suggest']
    if any(k in query for k in redist_kw) and role in ('hod','admin'):
        faculties = db.execute('SELECT id, name FROM users WHERE department_id=? AND role="faculty"', (dept_id,)).fetchall()
        overloaded, available = [], []
        for f in faculties:
            s = get_daily_workload(db, f['id'], today_str)
            e = f"{f['name']} ({s['percentage']}%)"
            if s['percentage'] >= 90: overloaded.append(e)
            elif s['percentage'] < 60: available.append(e)
        lines = ["⚖️ **Workload Redistribution Analysis (Today):**"]
        if overloaded:
            lines.append(f"\n🔴 **Overloaded:**")
            lines.extend([f"  • {x}" for x in overloaded])
        if available:
            lines.append(f"\n🟢 **Available for more work:**")
            lines.extend([f"  • {x}" for x in available])
        if not overloaded and not available:
            lines.append("All faculty are balanced today.")
        lines.append("\n👉 Go to the **Redistribution** page to apply changes.")
        return jsonify({"response": "\n".join(lines)})

    # INTENT 9: DEPARTMENT REPORT
    report_kw = ['report','summary','department report','analytics','generate report','overview']
    if any(k in query for k in report_kw) and role in ('hod','admin'):
        faculty_count = db.execute('SELECT COUNT(*) as c FROM users WHERE department_id=? AND role="faculty"', (dept_id,)).fetchone()['c']
        approved_research = db.execute('SELECT COUNT(*) as c FROM research_activities r JOIN users u ON r.faculty_id=u.id WHERE u.department_id=? AND r.status="Approved"', (dept_id,)).fetchone()['c']
        pending_total = db.execute('SELECT (SELECT COUNT(*) FROM academic_activities a JOIN users u ON a.faculty_id=u.id WHERE u.department_id=? AND a.status="Pending") + (SELECT COUNT(*) FROM research_activities r JOIN users u ON r.faculty_id=u.id WHERE u.department_id=? AND r.status="Pending") as t', (dept_id, dept_id)).fetchone()['t']
        timetable_slots = db.execute('SELECT COUNT(*) as c FROM timetable t JOIN users u ON t.faculty_id=u.id WHERE u.department_id=?', (dept_id,)).fetchone()['c']
        return jsonify({"response":
            f"📑 **Department Summary**\n• Faculty: {faculty_count}\n• Timetable Slots: {timetable_slots}\n• Research Papers: {approved_research}\n• Pending Approvals: {pending_total}\n\n👉 Visit **Reports** for the full accreditation export."
        })

    # INTENT 10: HELP
    help_kw = ['help','what can you','capabilities','commands','options']
    if any(k in query for k in help_kw):
        if role == 'faculty':
            return jsonify({"response": "👋 **I can help you with:**\n• Show today's timetable\n• What is my workload?\n• Show yesterday's workload\n• How many pending approvals?\n• Show my research papers\n• Show my activities"})
        return jsonify({"response": "👋 **I can help you with:**\n• Who has the highest workload?\n• Show timetable of [name]\n• Show workload of [name]\n• Which faculty can take additional workload?\n• Show yesterday's activities of [name]\n• How many pending approvals?\n• Generate department report\n• Suggest fair workload redistribution"})

    return jsonify({"response": "🤔 I didn't understand that. Type **help** to see what I can do."})


if __name__ == '__main__':
    init_db()
    app.run(debug=True, use_reloader=False, port=5002)
