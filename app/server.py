
from flask import Flask, request, jsonify, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import psycopg2
from psycopg2.extras import RealDictCursor
import os
from datetime import datetime, timedelta
import jwt
from flask_cors import CORS
import openai
from datetime import datetime, timedelta


# Initialize Flask app
app = Flask(__name__, static_folder='static')
app.secret_key = os.environ.get('SECRET_KEY') or os.urandom(24).hex()
CORS(app)  # Enable CORS for all routes

# Database configuration
DB_CONFIG = {
    "dbname": "dbc_jtdb",
    "user": "dbc_jtdb_user",
    "password": "eBH1D0XF5oAMNt1cuU5sXyob9YzivI0m",
    "host": "dpg-cvd9jlhu0jms739lbnug-a.oregon-postgres.render.com",
    "port": "5432",
    "sslmode": "require"
}

# JWT configuration
JWT_SECRET = os.environ.get('JWT_SECRET') or os.urandom(24).hex()
JWT_ALGORITHM = 'HS256'
JWT_EXPIRE_HOURS = 24

# --- Helper Functions ---
def get_db_connection():
    """Get a new database connection with autocommit disabled"""
    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = False
    return conn

# --- Auth Decorators ---
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({"error": "Authorization token is missing"}), 401

        try:
            token = token.split()[1]  # Extract token from 'Bearer <token>'
            data = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            current_user = get_user_by_id(data['user_id'])
            if not current_user:
                raise ValueError("User not found")
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token has expired"}), 401
        except Exception as e:
            return jsonify({"error": f"Invalid token: {str(e)}"}), 401

        return f(current_user, *args, **kwargs)
    return decorated

def role_required(allowed_roles):
    def decorator(f):
        @wraps(f)
        def wrapped(current_user, *args, **kwargs):
            if current_user['role'] not in allowed_roles:
                return jsonify({"error": "Insufficient permissions"}), 403
            return f(current_user, *args, **kwargs)
        return wrapped
    return decorator

# --- User Management ---
def get_user_by_id(user_id):
    """Fetch user by ID from database"""
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("""
                SELECT id, username, role FROM users WHERE id = %s
            """, (user_id,))
            return cursor.fetchone()

@app.route('/api/register', methods=['POST'])
@token_required
@role_required(['admin'])  # Only admins can register users
def register(current_user):
    """Register a new user"""
    data = request.get_json()
    required_fields = ['username', 'password', 'role']
    if not all(field in data for field in required_fields):
        return jsonify({"error": "Missing required fields"}), 400

    if data['role'] not in ['admin', 'manager', 'user']:
        return jsonify({"error": "Invalid role specified"}), 400

    hashed_pw = generate_password_hash(data['password'])

    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    INSERT INTO users (username, password_hash, role)
                    VALUES (%s, %s, %s)
                    RETURNING id, username, role
                """, (data['username'], hashed_pw, data['role']))
                new_user = cursor.fetchone()
                conn.commit()
                return jsonify({
                    "success": True,
                    "message": "Registration successful",
                    "user": {
                        "id": new_user['id'],
                        "username": new_user['username'],
                        "role": new_user['role']
                    }
                }), 201
    except psycopg2.IntegrityError:
        return jsonify({
            "success": False,
            "error": "Username already exists"
        }), 409
    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"Registration failed: {str(e)}"
        }), 500

@app.route('/api/login', methods=['POST'])
def login():
    """Authenticate user and return JWT token"""
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({"error": "Username and password required"}), 400

    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT id, password_hash, role FROM users WHERE username = %s
                """, (username,))
                user = cursor.fetchone()

        if not user or not check_password_hash(user['password_hash'], password):
            return jsonify({"error": "Invalid credentials"}), 401

        token = jwt.encode({
            'user_id': user['id'],
            'exp': datetime.utcnow() + timedelta(hours=JWT_EXPIRE_HOURS)
        }, JWT_SECRET, algorithm=JWT_ALGORITHM)

        return jsonify({
            "token": token,
            "user": {
                "id": user['id'],
                "username": username,
                "role": user['role']
            }
        })
    except Exception as e:
        return jsonify({"error": f"Login failed: {str(e)}"}), 500

# --- Job Management ---
@app.route('/api/jobs', methods=['GET'])
@token_required
def get_jobs(current_user):
    """Get jobs list - all users can view all jobs"""
    status = request.args.get('status')
    search_column = request.args.get('search_column')
    search_term = request.args.get('search_term')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    sort_column = request.args.get('sort')
    sort_order = request.args.get('order', 'asc')
    
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                base_query = """
                    SELECT j.*, u.username as assigned_username 
                    FROM jobs j
                    LEFT JOIN users u ON j.assigned_user_id = u.id
                    WHERE TRUE
                """
                
                params = []
                
                # Status filter
                if status and status != "all":
                    base_query += " AND j.status = %s"
                    params.append(status)
                
                # Search filter
                if search_column and search_term:
                    base_query += f" AND j.{search_column} ILIKE %s"
                    params.append(f'%{search_term}%')
                
                # Date range filter
                if start_date:
                    base_query += " AND j.created_at >= %s"
                    params.append(start_date)
                if end_date:
                    base_query += " AND j.created_at <= %s"
                    params.append(end_date + " 23:59:59")
                
                # Sorting
                if sort_column:
                    base_query += f" ORDER BY j.{sort_column} {sort_order}"
                
                cursor.execute(base_query, params)
                jobs = cursor.fetchall()
                
                for job in jobs:
                    for date_field in ['due_date', 'created_at']:
                        if job.get(date_field):
                            job[date_field] = job[date_field].isoformat()
                
                return jsonify(jobs)
    except Exception as e:
        return jsonify({"error": f"Failed to fetch jobs: {str(e)}"}), 500    

@app.route('/api/jobs', methods=['POST'])
@token_required
@role_required(['admin'])
def create_job(current_user):
    """Create a new job (admin only)"""
    data = request.get_json()
    required_fields = ['name', 'job_num', 'status', 'assigned_user_id']
    if not all(field in data for field in required_fields):
        return jsonify({"error": "Missing required fields"}), 400

    valid_statuses = ['designing', 'in progress', 'waiting on approval', 'completed', 'on hold', 'to be fixed']
    if data.get('status') not in valid_statuses:
        return jsonify({"error": "Invalid status"}), 400

    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    INSERT INTO jobs (
                        name, job_num, qty, details_of_job, 
                        due_date, department, person_in_charge, 
                        status, assigned_user_id
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING *
                """, (
                    data.get('name'),
                    data.get('job_num'),
                    data.get('qty', 1),
                    data.get('details_of_job'),
                    data.get('due_date'),
                    data.get('department'),
                    data.get('person_in_charge'),
                    data.get('status'),
                    data.get('assigned_user_id')
                ))
                new_job = cursor.fetchone()
                conn.commit()
                
                for date_field in ['due_date', 'created_at']:
                    if new_job.get(date_field):
                        new_job[date_field] = new_job[date_field].isoformat()
                
                return jsonify(new_job), 201
    except Exception as e:
        return jsonify({"error": f"Failed to create job: {str(e)}"}), 500

@app.route('/api/jobs/<int:job_id>', methods=['PUT'])
@token_required
@role_required(['admin'])
def update_job(current_user, job_id):
    """Update job details (admin only)"""
    data = request.get_json()
    
    if 'status' in data:
        valid_statuses = ['designing', 'in progress', 'waiting on approval', 'completed', 'on hold', 'to be fixed']
        if data['status'] not in valid_statuses:
            return jsonify({"error": "Invalid status"}), 400

    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    UPDATE jobs 
                    SET 
                        name = COALESCE(%s, name),
                        job_num = COALESCE(%s, job_num),
                        qty = COALESCE(%s, qty),
                        details_of_job = COALESCE(%s, details_of_job),
                        due_date = COALESCE(%s, due_date),
                        department = COALESCE(%s, department),
                        person_in_charge = COALESCE(%s, person_in_charge),
                        status = COALESCE(%s, status),
                        assigned_user_id = COALESCE(%s, assigned_user_id)
                    WHERE id = %s
                    RETURNING *
                """, (
                    data.get('name'),
                    data.get('job_num'),
                    data.get('qty'),
                    data.get('details_of_job'),
                    data.get('due_date'),
                    data.get('department'),
                    data.get('person_in_charge'),
                    data.get('status'),
                    data.get('assigned_user_id'),
                    job_id
                ))
                updated_job = cursor.fetchone()
                conn.commit()
                
                if not updated_job:
                    return jsonify({"error": "Job not found"}), 404
                
                for date_field in ['due_date', 'created_at']:
                    if updated_job.get(date_field):
                        updated_job[date_field] = updated_job[date_field].isoformat()
                
                return jsonify(updated_job)
    except Exception as e:
        return jsonify({"error": f"Failed to update job: {str(e)}"}), 500

@app.route('/api/jobs/<int:job_id>', methods=['DELETE'])
@token_required
@role_required(['admin'])
def delete_job(current_user, job_id):
    """Delete a job"""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    DELETE FROM jobs 
                    WHERE id = %s
                    RETURNING id
                """, (job_id,))
                deleted_job = cursor.fetchone()
                conn.commit()
                
                if not deleted_job:
                    return jsonify({"error": "Job not found"}), 404
                
                return jsonify({"message": "Job deleted successfully"})
    except Exception as e:
        return jsonify({"error": f"Failed to delete job: {str(e)}"}), 500

# --- Frontend Serving ---
@app.route('/')
def serve_index():
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory(app.static_folder, path)

# --- Health Check ---
@app.route('/api/health')
def health_check():
    """Service health check endpoint"""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT 1")
        return jsonify({
            "status": "healthy",
            "database": "connected",
            "timestamp": datetime.utcnow().isoformat()
        })
    except Exception as e:
        return jsonify({
            "status": "degraded",
            "database": "disconnected",
            "error": str(e)
        }), 500

# --- Database Initialization ---
def initialize_database():
    """Create database tables if they don't exist"""
    with get_db_connection() as conn:
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


# Add these new routes right after your existing routes (before the frontend serving section)

# --- User Management Routes ---
@app.route('/api/users', methods=['GET'])
@token_required
@role_required(['admin'])
def get_users(current_user):
    """Get all users (admin only)"""
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT id, username, role, created_at 
                    FROM users 
                    ORDER BY created_at DESC
                """)
                users = cursor.fetchall()
                
                # Convert datetime to ISO format
                for user in users:
                    if user.get('created_at'):
                        user['created_at'] = user['created_at'].isoformat()
                
                return jsonify(users)
    except Exception as e:
        return jsonify({"error": f"Failed to fetch users: {str(e)}"}), 500

@app.route('/api/users/<int:user_id>', methods=['PUT'])
@token_required
@role_required(['admin'])
def update_user(current_user, user_id):
    """Update user details (admin only)"""
    if current_user['id'] == user_id:
        return jsonify({"error": "Cannot modify your own account"}), 400
    
    data = request.get_json()
    
    # Validate input
    if 'role' in data and data['role'] not in ['admin', 'manager', 'user']:
        return jsonify({"error": "Invalid role specified"}), 400
    
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                # Check if user exists
                cursor.execute("SELECT id FROM users WHERE id = %s", (user_id,))
                if not cursor.fetchone():
                    return jsonify({"error": "User not found"}), 404
                
                # Build update query
                update_fields = []
                params = []
                
                if 'username' in data:
                    update_fields.append("username = %s")
                    params.append(data['username'])
                
                if 'role' in data:
                    update_fields.append("role = %s")
                    params.append(data['role'])
                
                if 'password' in data and data['password']:
                    update_fields.append("password_hash = %s")
                    params.append(generate_password_hash(data['password']))
                
                if not update_fields:
                    return jsonify({"error": "No fields to update"}), 400
                
                params.append(user_id)
                query = f"""
                    UPDATE users 
                    SET {', '.join(update_fields)}
                    WHERE id = %s
                    RETURNING id, username, role, created_at
                """
                
                cursor.execute(query, params)
                updated_user = cursor.fetchone()
                conn.commit()
                
                if updated_user.get('created_at'):
                    updated_user['created_at'] = updated_user['created_at'].isoformat()
                
                return jsonify(updated_user)
    except psycopg2.IntegrityError:
        return jsonify({"error": "Username already exists"}), 409
    except Exception as e:
        return jsonify({"error": f"Failed to update user: {str(e)}"}), 500

@app.route('/api/users/<int:user_id>', methods=['DELETE'])
@token_required
@role_required(['admin'])
def delete_user(current_user, user_id):
    """Delete a user (admin only)"""
    if current_user['id'] == user_id:
        return jsonify({"error": "Cannot delete your own account"}), 400
    
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                # Check if user exists
                cursor.execute("SELECT id FROM users WHERE id = %s", (user_id,))
                if not cursor.fetchone():
                    return jsonify({"error": "User not found"}), 404
                
                # Check if user has assigned jobs
                cursor.execute("""
                    SELECT COUNT(*) as job_count 
                    FROM jobs 
                    WHERE assigned_user_id = %s
                """, (user_id,))
                job_count = cursor.fetchone()['job_count']
                
                if job_count > 0:
                    return jsonify({
                        "error": "Cannot delete user with assigned jobs",
                        "job_count": job_count
                    }), 400
                
                # Delete the user
                cursor.execute("DELETE FROM users WHERE id = %s RETURNING id", (user_id,))
                if not cursor.fetchone():
                    return jsonify({"error": "User not found"}), 404
                
                conn.commit()
                return jsonify({"success": True, "message": "User deleted successfully"})
    except Exception as e:
        return jsonify({"error": f"Failed to delete user: {str(e)}"}), 500


# Add this configuration (replace with your OpenAI API key)
OPENAI_API_KEY = "your-openai-api-key"
openai.api_key = OPENAI_API_KEY

# Add this route to your Flask app
@app.route('/api/chatbot', methods=['POST'])
@token_required
def chatbot(current_user):
    data = request.get_json()
    question = data.get('question')
    
    if not question:
        return jsonify({"error": "Question is required"}), 400
    
    try:
        # Step 1: Convert natural language to SQL using OpenAI
        prompt = f"""
        You are a senior database administrator. Convert this natural language question into a PostgreSQL SQL query.
        Database schema:
        - jobs (id, name, job_num, qty, details_of_job, due_date, department, person_in_charge, status, created_at, assigned_user_id)
        - users (id, username, password_hash, role, created_at)
        
        Question: "{question}"
        
        Return ONLY the SQL query, nothing else.
        """
        
        response = openai.Completion.create(
            engine="text-davinci-003",
            prompt=prompt,
            max_tokens=150,
            temperature=0.3
        )
        
        sql_query = response.choices[0].text.strip()
        
        # Step 2: Execute the SQL query
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(sql_query)
                results = cursor.fetchall()
                
        return jsonify({
            "question": question,
            "sql": sql_query,
            "results": results
        })
        
    except Exception as e:
        return jsonify({
            "error": str(e),
            "message": "Failed to process your question"
        }), 500

if __name__ == '__main__':
    initialize_database()
    app.run(host='0.0.0.0', port=5000, debug=False)
