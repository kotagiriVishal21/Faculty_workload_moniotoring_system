import sqlite3
import random

db = sqlite3.connect('faculty_workload.db')
db.row_factory = sqlite3.Row
cursor = db.cursor()

days = ['MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT']
periods = [1, 2, 3, 4, 5, 6, 7] # 1 to 7 corresponding to non-break timeslots

# Get department ID for IT
cursor.execute("SELECT id FROM departments WHERE name = 'Information Technology'")
dept_id = cursor.fetchone()['id']

# Get or create sections IT-A and IT-B
sections = {}
for sec_name in ['IT-A', 'IT-B']:
    cursor.execute("SELECT id FROM sections WHERE name = ? AND department_id = ?", (sec_name, dept_id))
    row = cursor.fetchone()
    if not row:
        cursor.execute("INSERT INTO sections (name, department_id) VALUES (?, ?)", (sec_name, dept_id))
        sections[sec_name] = cursor.lastrowid
    else:
        sections[sec_name] = row['id']

# Timeslot lookup (period_number -> timeslot_id)
cursor.execute("SELECT id, period_number FROM timeslots WHERE is_break = 0")
ts_map = {row['period_number']: row['id'] for row in cursor.fetchall()}
lookup_ts = {row['id']: row['period_number'] for row in cursor.fetchall()}

# Get IT-C's existing timetable to use as a template for requirements
cursor.execute("SELECT id FROM sections WHERE name = 'IT-C'")
itc_id = cursor.fetchone()['id']

cursor.execute("SELECT * FROM timetable WHERE section_id = ?", (itc_id,))
itc_schedule = cursor.fetchall()

# Determine number of slots needed per course per faculty week
# course_reqs = [ {course_id: X, faculty_id: Y, is_lab: Z, continuous_slots: N} ]
course_needs = {}
for entry in itc_schedule:
    key = (entry['course_id'], entry['faculty_id'])
    
    if key not in course_needs:
        cursor.execute("SELECT is_lab FROM courses WHERE id = ?", (entry['course_id'],))
        is_lab = cursor.fetchone()['is_lab']
        course_needs[key] = {'is_lab': is_lab, 'slots_needed': 0, 'sessions': []}
        
    course_needs[key]['slots_needed'] += 1

# Group lab sessions (they occur in blocks of 3)
requests = []
for (c_id, f_id), data in course_needs.items():
    if data['is_lab'] == 1:
        # A lab is 3 continuous slots, usually 1 session per week
        num_sessions = data['slots_needed'] // 3
        for _ in range(num_sessions):
            requests.append({'c_id': c_id, 'f_id': f_id, 'is_lab': 1, 'duration': 3})
    else:
        # Theory classes are 1 slot each, multiple per week
        for _ in range(data['slots_needed']):
            requests.append({'c_id': c_id, 'f_id': f_id, 'is_lab': 0, 'duration': 1})

# Clear old IT-A / IT-B timetables if any
for s_id in sections.values():
    cursor.execute("DELETE FROM timetable WHERE section_id = ?", (s_id,))

# Get existing occupied slots across all sections (so we don't double book faculty)
def get_faculty_schedule():
    cursor.execute("SELECT faculty_id, day, timeslot_id FROM timetable")
    busy = set()
    for row in cursor.fetchall():
        period = ts_map.get(row['timeslot_id'], -1)
        # We need period number to map easier, but let's just use timeslot_id
        busy.add((row['faculty_id'], row['day'], row['timeslot_id']))
    return busy

class ScheduleGenerator:
    def __init__(self, requests, ts_map):
        self.requests = requests
        self.ts_map = ts_map # period_number -> timeslot_id
        
    def generate(self, section_id, faculty_busy_set, room_base):
        schedule = []
        section_busy = set()
        
        # Sort requests - place labs (duration 3) first as they are hardest to fit
        reqs = sorted(self.requests, key=lambda x: x['duration'], reverse=True)
        
        for req in reqs:
            placed = False
            # Try random days/periods until we find a fit
            shuffled_days = list(days)
            random.shuffle(shuffled_days)
            
            for day in shuffled_days:
                if placed: break
                
                # Available periods that day for this section
                avail_periods = [p for p in periods if (day, self.ts_map[p]) not in section_busy]
                
                if req['duration'] == 3:
                    # Need 3 continuous periods
                    # Check e.g., 1-2-3 or 5-6-7
                    possible_start = [1, 5] # Only safe places for a 3-block without hitting lunch/breaks
                    random.shuffle(possible_start)
                    for start in possible_start:
                        block = [start, start+1, start+2]
                        if all(p in avail_periods for p in block):
                            # Check faculty availability
                            fac_free = all((req['f_id'], day, self.ts_map[p]) not in faculty_busy_set for p in block)
                            if fac_free:
                                # Place it
                                for p in block:
                                    t_id = self.ts_map[p]
                                    schedule.append((day, t_id, section_id, req['c_id'], req['f_id'], f"{room_base}"))
                                    section_busy.add((day, t_id))
                                    faculty_busy_set.add((req['f_id'], day, t_id))
                                placed = True
                                break
                else: # Theory
                    # Find any single free slot where faculty is free
                    random.shuffle(avail_periods)
                    for p in avail_periods:
                        t_id = self.ts_map[p]
                        if (req['f_id'], day, t_id) not in faculty_busy_set:
                            # Place it
                            schedule.append((day, t_id, section_id, req['c_id'], req['f_id'], f"{room_base}"))
                            section_busy.add((day, t_id))
                            faculty_busy_set.add((req['f_id'], day, t_id))
                            placed = True
                            break
                            
            if not placed:
                print(f"Warning: Could not place class {req['c_id']} for section {section_id}")
                
        return schedule, faculty_busy_set


print("Generating IT-A and IT-B Schedules...")
fac_busy = get_faculty_schedule()
generator = ScheduleGenerator(requests, ts_map)

# Generate IT-A
schedule_A, fac_busy = generator.generate(sections['IT-A'], fac_busy, "3018")
for entry in schedule_A:
    cursor.execute("""
        INSERT INTO timetable (day, timeslot_id, section_id, course_id, faculty_id, room_no)
        VALUES (?, ?, ?, ?, ?, ?)
    """, entry)

# Generate IT-B
schedule_B, fac_busy = generator.generate(sections['IT-B'], fac_busy, "3019")
for entry in schedule_B:
    cursor.execute("""
        INSERT INTO timetable (day, timeslot_id, section_id, course_id, faculty_id, room_no)
        VALUES (?, ?, ?, ?, ?, ?)
    """, entry)

db.commit()
print("Success! Generated schedules for IT-A and IT-B.")
