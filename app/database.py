import psycopg2
from psycopg2.pool import SimpleConnectionPool
import os

# Neon configuration
DB_CONFIG = {
    "dbname": os.getenv("DB_NAME", "Job-TrackingDataBase"),
    "user": os.getenv("DB_USER", "neondb_owner"),
    "password": os.getenv("DB_PASSWORD", "npg_Ut8s9TLJEVRq"),
    "host": os.getenv("DB_HOST", "ep-cold-grass-abiz6twt-pooler.eu-west-2.aws.neon.tech"),
    "port": os.getenv("DB_PORT", "5432"),
    "sslmode": os.getenv("DB_SSLMODE", "require")
}

# Create connection pool
connection_pool = SimpleConnectionPool(
    minconn=1,
    maxconn=5,
    **DB_CONFIG
)

def get_connection():
    """Get a connection from the pool"""
    return connection_pool.getconn()

def return_connection(conn):
    """Return a connection to the pool"""
    connection_pool.putconn(conn)

def create_table():
    """Create database tables if they don't exist"""
    conn = None
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL CHECK (role IN ('admin', 'manager', 'user')),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE TABLE IF NOT EXISTS jobs (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL,
                    job_num TEXT NOT NULL,
                    qty INTEGER DEFAULT 1,
                    details_of_job TEXT,
                    due_date DATE,
                    department TEXT,
                    person_in_charge TEXT,
                    status TEXT CHECK (status IN ('designing', 'in progress', 'waiting on approval', 'completed', 'on hold', 'to be fixed')),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    assigned_user_id INTEGER REFERENCES users(id)
                );
                
                CREATE INDEX IF NOT EXISTS idx_jobs_assigned_user ON jobs(assigned_user_id);
                CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
                CREATE INDEX IF NOT EXISTS idx_jobs_created_at ON jobs(created_at);
            """)
            conn.commit()
    finally:
        if conn:
            return_connection(conn)

def get_jobs():
    """Get all jobs from the database"""
    conn = None
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM jobs;")
            return cursor.fetchall()
    finally:
        if conn:
            return_connection(conn)

# Initialize the database when this module is imported
create_table()
