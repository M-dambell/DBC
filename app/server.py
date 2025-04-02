from flask import Flask, jsonify, request, send_from_directory
from psycopg2.pool import SimpleConnectionPool
import os
from psycopg2.extras import RealDictCursor

app = Flask(__name__)

# Database configuration - Move these to environment variables in production
DB_NAME = "dbc_jtdb"
DB_USER = "dbc_jtdb_user"
DB_PASSWORD = "eBH1D0XF5oAMNt1cuU5sXyob9YzivI0m"
DB_HOST = "dpg-cvd9jlhu0jms739lbnug-a.oregon-postgres.render.com"
DB_PORT = 5432

# Connection pool setup
pool = SimpleConnectionPool(
    minconn=1,
    maxconn=20,
    dbname=DB_NAME,
    user=DB_USER,
    password=DB_PASSWORD,
    host=DB_HOST,
    port=DB_PORT,
    sslmode="require"
)

def get_db_connection():
    return pool.getconn()

def return_db_connection(conn):
    pool.putconn(conn)

@app.route('/')
def serve_frontend():
    return send_from_directory(os.path.join(app.root_path, 'static'), 'index.html')

@app.route('/jobs', methods=['GET'])
def get_jobs():
    status = request.args.get('status')
    sort_column = request.args.get('sort')
    sort_order = request.args.get('order', 'asc')
    
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        query = "SELECT * FROM jobs"
        params = []
        
        if status and status != "all":
            query += " WHERE status = %s"
            params.append(status)
        
        if sort_column in ['id', 'name', 'job_num', 'qty', 'details_of_job', 'due_date', 'department', 'person_in_charge', 'status', 'created_at']:
            query += f" ORDER BY {sort_column} {sort_order}"
        
        cursor.execute(query, params)
        jobs = cursor.fetchall()
        
        # Format dates
        for job in jobs:
            if job['due_date']:
                job['due_date'] = job['due_date'].strftime('%Y-%m-%d')
            if job['created_at']:
                job['created_at'] = job['created_at'].strftime('%Y-%m-%d %H:%M')
        
        return jsonify(jobs)
        
    finally:
        cursor.close()
        return_db_connection(conn)

# SEARCH - Find jobs
@app.route('/jobs/search', methods=['GET'])
def search_jobs():
    column = request.args.get('column')
    term = request.args.get('term')
    
    if not column or not term:
        return jsonify({"error": "Missing search parameters"}), 400
    
    valid_columns = ['name', 'job_num', 'department', 'person_in_charge', 'status']
    if column not in valid_columns:
        return jsonify({"error": "Invalid search column"}), 400
    
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        query = f"SELECT * FROM jobs WHERE {column} ILIKE %s"
        cursor.execute(query, (f'%{term}%',))
        jobs = cursor.fetchall()
        
        for job in jobs:
            if job['due_date']:
                job['due_date'] = job['due_date'].strftime('%Y-%m-%d')
            if job['created_at']:
                job['created_at'] = job['created_at'].strftime('%Y-%m-%d %H:%M')
        
        return jsonify(jobs)
        
    finally:
        cursor.close()
        return_db_connection(conn)

# UPDATE - Edit job
@app.route('/jobs/<int:job_id>', methods=['PUT'])
def update_job(job_id):
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        data = request.get_json()
        
        cursor.execute("""
            UPDATE jobs 
            SET name = %s, job_num = %s, status = %s
            WHERE id = %s
            RETURNING *
        """, (data['name'], data['job_num'], data['status'], job_id))
        
        updated_job = cursor.fetchone()
        conn.commit()
        
        # Format dates
        updated_job['due_date'] = updated_job['due_date'].strftime('%Y-%m-%d') if updated_job['due_date'] else None
        updated_job['created_at'] = updated_job['created_at'].strftime('%Y-%m-%d %H:%M:%S') if updated_job['created_at'] else None
        
        return jsonify(updated_job)
        
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 400
    finally:
        cursor.close()
        return_db_connection(conn)


@app.route('/jobs/filter-by-date', methods=['GET'])
def filter_jobs_by_date():
    start_date = request.args.get('start')
    end_date = request.args.get('end')
    
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        query = "SELECT * FROM jobs WHERE TRUE"
        params = []
        
        if start_date:
            query += " AND created_at >= %s"
            params.append(start_date)
        if end_date:
            query += " AND created_at <= %s"
            params.append(end_date + " 23:59:59")  # Include entire end day
        
        cursor.execute(query, params)
        jobs = cursor.fetchall()
        
        # Format dates
        for job in jobs:
            if job['due_date']:
                job['due_date'] = job['due_date'].strftime('%Y-%m-%d')
            if job['created_at']:
                job['created_at'] = job['created_at'].strftime('%Y-%m-%d %H:%M')
        
        return jsonify(jobs)
        
    finally:
        cursor.close()
        return_db_connection(conn)


if __name__ == '__main__':
    # Create database indexes on startup
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
                CREATE INDEX IF NOT EXISTS idx_jobs_name ON jobs(name);
                CREATE INDEX IF NOT EXISTS idx_jobs_job_num ON jobs(job_num);
            """)
        conn.commit()
    finally:
        return_db_connection(conn)
    
    app.run(debug=False)  # Disable debug mode for production
    