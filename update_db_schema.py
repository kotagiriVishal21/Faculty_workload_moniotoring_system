import sqlite3
import datetime

DATABASE = 'faculty_workload.db'

def update_db():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    tables = [
        'teaching_workload',
        'academic_activities',
        'research_activities'
    ]
    
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for table in tables:
        try:
            # SQLite doesn't allow ALTER TABLE ADD COLUMN with CURRENT_TIMESTAMP or functional defaults for existing rows 
            # if we don't specify a constant. We can add it with a constant string default, or allow NULL.
            # Allowing NULL or setting a constant string default works.
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN created_at TIMESTAMP DEFAULT '{current_time}';")
            print(f"Added created_at to {table}")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e):
                print(f"Column created_at already exists in {table}")
            else:
                print(f"Error on {table}: {e}")
                
    conn.commit()
    conn.close()

if __name__ == '__main__':
    update_db()
