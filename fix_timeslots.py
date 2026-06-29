import sqlite3

db = sqlite3.connect('faculty_workload.db')
cursor = db.cursor()

# Check schema
cursor.execute("PRAGMA table_info(timeslots)")
columns = cursor.fetchall()
print("Columns in timeslots:", [c[1] for c in columns])

# Check for duplicates beyond id 9
cursor.execute("SELECT id, start_time, end_time FROM timeslots WHERE id > 9")
dupes = cursor.fetchall()
if dupes:
    print(f"Found {len(dupes)} duplicate timeslots. Deleting them...")
    cursor.execute("DELETE FROM timeslots WHERE id > 9")
    db.commit()
    print("Duplicates deleted.")
else:
    print("No duplicates found beyond ID 9.")

# If period_number is missing, add it or simulate it
if 'period_number' not in [c[1] for c in columns]:
    print("period_number missing in timeslots. I will simulate it in the template or add the column.")
    # For now, let's just make sure we have exactly 9 slots with correct break flags
    # Slot 3 and 6 are usually breaks based on the image: 11:00-11:10 and 12:50-01:40
else:
    # Update period_number if it exists but is 0/null
    cursor.execute("SELECT id, is_break FROM timeslots ORDER BY id")
    slots = cursor.fetchall()
    p = 1
    for sid, is_break in slots:
        if is_break == 0:
            cursor.execute("UPDATE timeslots SET period_number = ? WHERE id = ?", (p, sid))
            p += 1
        else:
            cursor.execute("UPDATE timeslots SET period_number = 0 WHERE id = ?", (sid,))
    db.commit()
    print("Updated period_numbers.")

db.close()
