-- Database Schema for Faculty Workload System

CREATE DATABASE IF NOT EXISTS faculty_workload;
USE faculty_workload;

-- Users Table
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    name VARCHAR(255) NOT NULL,
    role ENUM('admin', 'hod', 'faculty') NOT NULL,
    department_id INT DEFAULT NULL
);

-- Departments Table
CREATE TABLE IF NOT EXISTS departments (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL
);

-- Faculty Profiles Table
CREATE TABLE IF NOT EXISTS faculty_profiles (
    user_id INT PRIMARY KEY,
    about TEXT,
    spending_time_teaching INT DEFAULT 0,
    spending_time_research INT DEFAULT 0,
    spending_time_admin INT DEFAULT 0,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Courses Table (for Timetable Generation)
CREATE TABLE IF NOT EXISTS courses (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    weekly_hours INT NOT NULL,
    department_id INT,
    FOREIGN KEY (department_id) REFERENCES departments(id)
);

-- Timetable Table
CREATE TABLE IF NOT EXISTS timetable (
    id INT AUTO_INCREMENT PRIMARY KEY,
    day VARCHAR(20),
    slot VARCHAR(50),
    faculty_id INT,
    course_name VARCHAR(255),
    FOREIGN KEY (faculty_id) REFERENCES users(id)
);

-- Seed Initial Data
INSERT IGNORE INTO departments (name) VALUES ('Computer Science'), ('Electrical Engineering');

-- Admin User (Password: admin)
INSERT IGNORE INTO users (email, password, name, role) 
VALUES ('admin@example.com', 'admin', 'System Admin', 'admin');

-- HOD User (Password: hod)
INSERT IGNORE INTO users (email, password, name, role, department_id) 
VALUES ('hod@example.com', 'hod', 'Dr. Aris (HOD)', 'hod', 1);

-- Faculty Users (Password: faculty)
INSERT IGNORE INTO users (email, password, name, role, department_id) 
VALUES ('faculty1@example.com', 'faculty', 'Prof. John', 'faculty', 1),
       ('faculty2@example.com', 'faculty', 'Prof. Sarah', 'faculty', 1);

-- Faculty Profiles
INSERT IGNORE INTO faculty_profiles (user_id, about, spending_time_teaching, spending_time_research, spending_time_admin)
VALUES (3, 'Experienced in AI and Machine Learning.', 12, 8, 4),
       (4, 'Researcher in Database Systems.', 10, 12, 2);
