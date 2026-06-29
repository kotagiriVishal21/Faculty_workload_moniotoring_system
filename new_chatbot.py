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

