import psycopg2
from psycopg2.pool import SimpleConnectionPool
import os

# Neon-Specific Settings
NEON_CONFIG = {
    "host": os.getenv("NEON_HOST", "ep-cold-grass-abiz6twt-pooler.eu-west-2.aws.neon.tech"),
    "database": os.getenv("NEON_DB", "Job-TrackingDataBase"),
    "user": os.getenv("NEON_USER", "neondb_owner"),
    "password": os.getenv("NEON_PASSWORD", "npg_Ut8s9TLJEVRq"),
    "sslmode": "require"
}

class NeonDB:
    _pool = None

    @classmethod
    def get_pool(cls):
        if cls._pool is None:
            cls._pool = SimpleConnectionPool(
                minconn=1,
                maxconn=5,
                **NEON_CONFIG
            )
        return cls._pool

    @classmethod
    def execute(cls, query, params=None):
        conn = cls.get_pool().getconn()
        try:
            with conn.cursor() as cur:
                cur.execute(query, params or ())
                if cur.description:  # For SELECT queries
                    return cur.fetchall()
                conn.commit()
        except psycopg2.Error as e:
            conn.rollback()
            raise
        finally:
            cls.get_pool().putconn(conn)

# Schema Initialization
# Replace your existing table creation with this:
# Replace your existing table creation with this:
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
        status TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT now()
    )
""")
