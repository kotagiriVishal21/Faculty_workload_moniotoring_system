-- SQLite Schema for Faculty Workload & Activity Tracking System

-- Departments Table
CREATE TABLE IF NOT EXISTS departments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL
);

-- Sections Table (IT-A, IT-B, IT-C)
CREATE TABLE IF NOT EXISTS sections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    department_id INTEGER,
    FOREIGN KEY (department_id) REFERENCES departments(id)
);

-- Timeslots Table (Period structure)
CREATE TABLE IF NOT EXISTS timeslots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    period_number INTEGER,
    start_time TEXT,
    end_time TEXT,
    is_break INTEGER DEFAULT 0 -- 1 for Break/Lunch
);

-- Users Table
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    name TEXT NOT NULL,
    role TEXT CHECK(role IN ('admin', 'hod', 'faculty')) NOT NULL,
    department_id INTEGER,
    FOREIGN KEY (department_id) REFERENCES departments(id)
);

-- Faculty Profiles Table (Accreditation Focused)
CREATE TABLE IF NOT EXISTS faculty_details (
    faculty_id INTEGER PRIMARY KEY,
    designation TEXT,
    qualification TEXT,
    experience TEXT,
    domain TEXT,
    joining_date TEXT,
    pan_number TEXT,
    specialization TEXT,
    FOREIGN KEY (faculty_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Courses Table
CREATE TABLE IF NOT EXISTS courses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    course_name TEXT NOT NULL,
    subject_code TEXT UNIQUE NOT NULL,
    department_id INTEGER,
    credits INTEGER DEFAULT 0,
    is_lab INTEGER DEFAULT 0, -- 1 for Lab
    FOREIGN KEY (department_id) REFERENCES departments(id)
);

-- Timetable Table (Unified Temporal Schedule)
CREATE TABLE IF NOT EXISTS timetable (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    day TEXT CHECK(day IN ('MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT')),
    timeslot_id INTEGER,
    section_id INTEGER,
    course_id INTEGER,
    faculty_id INTEGER,
    room_no TEXT,
    FOREIGN KEY (timeslot_id) REFERENCES timeslots(id),
    FOREIGN KEY (section_id) REFERENCES sections(id),
    FOREIGN KEY (course_id) REFERENCES courses(id),
    FOREIGN KEY (faculty_id) REFERENCES users(id)
);

-- Teaching Workload Table (Aggregate totals)
CREATE TABLE IF NOT EXISTS teaching_workload (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    faculty_id INTEGER,
    course_id INTEGER,
    section_id INTEGER,
    hours_per_week INTEGER DEFAULT 0,
    semester TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (faculty_id) REFERENCES users(id),
    FOREIGN KEY (course_id) REFERENCES courses(id),
    FOREIGN KEY (section_id) REFERENCES sections(id)
);

-- Academic Activities Table
CREATE TABLE IF NOT EXISTS academic_activities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    faculty_id INTEGER,
    activity_type TEXT,
    description TEXT,
    hours INTEGER DEFAULT 0,
    date TEXT,
    status TEXT DEFAULT 'Pending' CHECK(status IN ('Pending', 'Approved', 'Rejected')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (faculty_id) REFERENCES users(id)
);

-- Research Activities Table
CREATE TABLE IF NOT EXISTS research_activities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    faculty_id INTEGER,
    title TEXT,
    type TEXT,
    journal TEXT,
    year TEXT,
    status TEXT DEFAULT 'Pending' CHECK(status IN ('Pending', 'Approved', 'Rejected')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (faculty_id) REFERENCES users(id)
);

-- Administrative Roles Table
CREATE TABLE IF NOT EXISTS admin_roles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    faculty_id INTEGER,
    role_name TEXT,
    description TEXT,
    status TEXT DEFAULT 'Pending' CHECK(status IN ('Pending', 'Approved', 'Rejected')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (faculty_id) REFERENCES users(id)
);

-- Seed Data
INSERT OR IGNORE INTO departments (id, name) VALUES (1, 'Information Technology');

INSERT OR IGNORE INTO sections (id, name, department_id) VALUES (1, 'IT-A', 1);
INSERT OR IGNORE INTO sections (id, name, department_id) VALUES (2, 'IT-B', 1);
INSERT OR IGNORE INTO sections (id, name, department_id) VALUES (3, 'IT-C', 1);

INSERT OR IGNORE INTO timeslots (period_number, start_time, end_time, is_break) VALUES 
(1, '09:10 AM', '10:10 AM', 0),
(2, '10:10 AM', '11:00 AM', 0),
(0, '11:00 AM', '11:10 AM', 1), -- Break
(3, '11:10 AM', '12:00 PM', 0),
(4, '12:00 PM', '12:50 PM', 0),
(0, '12:50 PM', '01:40 PM', 1), -- Lunch
(5, '01:40 PM', '02:40 PM', 0),
(6, '02:40 PM', '03:30 PM', 0),
(7, '03:30 PM', '04:20 PM', 0);

INSERT OR IGNORE INTO users (id, email, password, name, role, department_id) 
VALUES (1, 'admin@example.com', 'admin', 'System Admin', 'admin', NULL);

INSERT OR IGNORE INTO users (id, email, password, name, role, department_id) 
VALUES (2, 'hod@example.com', 'hod', 'Dr. Aris (HOD)', 'hod', 1);

INSERT OR IGNORE INTO users (id, email, password, name, role, department_id) 
VALUES (3, 'faculty1@example.com', 'faculty', 'Prof. John', 'faculty', 1);

INSERT OR IGNORE INTO users (id, email, password, name, role, department_id) 
VALUES (4, 'ganesh@gmail.com', 'Ganesh@93982', 'DR.Ganesh Bhaiyya Regulwar', 'faculty', 1);

INSERT OR IGNORE INTO courses (course_name, subject_code, department_id, credits, is_lab) VALUES 
('Cloud Computing and Virtualization', 'A8522', 1, 4, 0),
('Information Security', 'A8607', 1, 4, 0),
('Compiler Design', 'A8523', 1, 4, 0),
('Cloud Computing and Virtualization Lab', 'A8524', 1, 2, 1),
('Network and Information Security Lab', 'A8612', 1, 2, 1);

-- Fair Workload Distribution: Tasks
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT,
    category TEXT, /* e.g., 'Academic', 'Administrative', 'Mentoring' */
    effort_weight INTEGER DEFAULT 1,
    status TEXT DEFAULT 'Unassigned' CHECK(status IN ('Unassigned', 'Assigned', 'Completed')),
    assigned_to INTEGER,
    department_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (assigned_to) REFERENCES users(id),
    FOREIGN KEY (department_id) REFERENCES departments(id)
);

-- Weekly Schedules (Optimization engine)
CREATE TABLE IF NOT EXISTS weekly_schedules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    faculty_id INTEGER NOT NULL,
    department_id INTEGER NOT NULL,
    activity_type VARCHAR(50) NOT NULL,
    task_name VARCHAR(255) NOT NULL,
    date DATE NOT NULL,
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    duration REAL NOT NULL,
    FOREIGN KEY (faculty_id) REFERENCES users(id),
    FOREIGN KEY (department_id) REFERENCES departments(id)
);
