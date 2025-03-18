import sqlite3

def connect_db():
    return sqlite3.connect("jobs.db")  # Creates a local SQLite file

def create_table():
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_name TEXT,
            job_num TEXT UNIQUE,
            qty INTEGER,
            department TEXT,
            person TEXT,
            status TEXT
        )
    """)
    conn.commit()
    conn.close()

def get_jobs():
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM jobs;")
    jobs = cursor.fetchall()
    conn.close()
    return jobs

# Run this once to create the database
create_table()
