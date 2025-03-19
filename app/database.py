# database.py
import psycopg2
from psycopg2 import sql

# Replace these with your Render PostgreSQL credentials
DB_NAME = "dbc_jtdb"
DB_USER = "dbc_jtdb_user"
DB_PASSWORD = "eBH1D0XF5oAMNt1cuU5sXyob9YzivI0m"
DB_HOST = "dpg-cvd9jlhu0jms739lbnug-a.oregon-postgres.render.com"
DB_PORT = 5432

def connect_db():
    return psycopg2.connect(
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST,
        port=DB_PORT,
        sslmode="require"
    )

def create_table():
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id SERIAL PRIMARY KEY,
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

# Run this once to create the table
create_table()
