import psycopg2
from psycopg2.pool import SimpleConnectionPool
import os
import time

# Neon Configuration
NEON_CONFIG = {
    "host": os.getenv("NEON_HOST", "ep-cold-grass-abiz6twt-pooler.eu-west-2.aws.neon.tech"),
    "database": os.getenv("NEON_DB", "Job-TrackingDataBase"),
    "user": os.getenv("NEON_USER", "neondb_owner"),
    "password": os.getenv("NEON_PASSWORD", "npg_Ut8s9TLJEVRq"),
    "sslmode": "require",
    "connect_timeout": 5,
    "keepalives": 1,
    "keepalives_idle": 30,
    "keepalives_interval": 10,
    "keepalives_count": 5
}

class NeonDB:
    _pool = None

    @classmethod
    def get_pool(cls):
        if cls._pool is None or cls._pool.closed:
            cls._pool = SimpleConnectionPool(
                minconn=1,
                maxconn=5,
                **NEON_CONFIG
            )
        return cls._pool

    @classmethod
    def execute(cls, query, params=None):
        conn = None
        try:
            conn = cls.get_pool().getconn()
            with conn.cursor() as cur:
                # Set statement timeout
                cur.execute("SET statement_timeout = 5000")
                # Execute the actual query
                cur.execute(query, params or ())
                if cur.description:  # For SELECT queries
                    return cur.fetchall()
                conn.commit()
            return None
        except psycopg2.Error as e:
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                try:
                    cls.get_pool().putconn(conn)
                except Exception as e:
                    print(f"Error returning connection to pool: {e}")
                    if conn and not conn.closed:
                        conn.close()

# Initialize database schema
def initialize_db():
    try:
        NeonDB.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT now()
            )
        """)

        NeonDB.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                job_num TEXT NOT NULL,
                qty INTEGER DEFAULT 1,
                details_of_job TEXT,
                due_date TIMESTAMP,
                department TEXT,
                person_in_charge TEXT,
                status TEXT NOT NULL,
                assigned_user_id INTEGER REFERENCES users(id),
                created_at TIMESTAMP DEFAULT now()
            )
        """)
        print("Database initialized successfully")
    except Exception as e:
        print(f"Error initializing database: {e}")

# Initialize the database when this module is imported
initialize_db()
