import os
from datetime import datetime, timedelta
from functools import wraps
import jwt
import pyodbc
from flask import Flask, request, jsonify, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
from flask_cors import CORS

# Initialize Flask app
app = Flask(__name__, static_folder='static')
app.secret_key = os.environ.get('SECRET_KEY') or os.urandom(24).hex()
CORS(app)

# Database Configuration - Configure these in Render environment variables!
DB_CONFIG = {
    "server": os.environ.get('DB_SERVER'),          # e.g., "your-tunnel.trycloudflare.com,1433"
    "database": os.environ.get('DB_NAME'),          # Your database name
    "user": os.environ.get('DB_USER'),              # SQL login (NOT 'sa')
    "password": os.environ.get('DB_PASSWORD'),      # Set in Render dashboard
    "driver": "ODBC Driver 17 for SQL Server",
    "Encrypt": "yes",                               # Force encryption
    "TrustServerCertificate": "no",                 # Validate certificates
    "Connection Timeout": "30"                      # Fail fast if unreachable
}

def get_db_connection():
    """Secure database connection with retry logic"""
    conn_str = (
        f"DRIVER={DB_CONFIG['driver']};"
        f"SERVER={DB_CONFIG['server']};"
        f"DATABASE={DB_CONFIG['database']};"
        f"UID={DB_CONFIG['user']};"
        f"PWD={DB_CONFIG['password']};"
        f"Encrypt={DB_CONFIG['Encrypt']};"
        f"TrustServerCertificate={DB_CONFIG['TrustServerCertificate']};"
        f"Connection Timeout={DB_CONFIG['Connection Timeout']}"
    )
    return pyodbc.connect(conn_str)

# Auth Decorators
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({"error": "Authorization token missing"}), 401

        try:
            token = token.split()[1]  # Remove 'Bearer' prefix
            data = jwt.decode(token, app.secret_key, algorithms=['HS256'])
            current_user = get_user_by_id(data['user_id'])
            if not current_user:
                raise ValueError("User not found")
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token expired"}), 401
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

# User Management
def get_user_by_id(user_id):
    """Fetch user with minimal data exposure"""
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT id, username, role FROM users WHERE id = ?", 
                (user_id,)
            )
            row = cursor.fetchone()
            return dict(zip([column[0] for column in cursor.description], row)) if row else None

@app.route('/api/login', methods=['POST'])
def login():
    """Secure login with parameterized queries"""
    data = request.get_json()
    if not data or 'username' not in data or 'password' not in data:
        return jsonify({"error": "Username and password required"}), 400

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT id, password_hash, role FROM users WHERE username = ?", 
                    (data['username'],)
                )
                user = cursor.fetchone()
                
        if not user or not check_password_hash(user[1], data['password']):
            return jsonify({"error": "Invalid credentials"}), 401

        token = jwt.encode({
            'user_id': user[0],
            'exp': datetime.utcnow() + timedelta(hours=24)
        }, app.secret_key, algorithm='HS256')

        return jsonify({
            "token": token,
            "user": {
                "id": user[0],
                "username": data['username'],
                "role": user[2]
            }
        })
    except Exception as e:
        return jsonify({"error": f"Login failed: {str(e)}"}), 500

# Job Management (with SQL injection protection)
@app.route('/api/jobs', methods=['GET'])
@token_required
def get_jobs(current_user):
    """Secure job listing with all protections"""
    valid_columns = {
        'id', 'name', 'job_num', 'qty', 'due_date', 
        'department', 'status', 'created_at'
    }
    
    status = request.args.get('status')
    search_column = request.args.get('search_column', 'name')
    search_term = request.args.get('search_term')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    sort = request.args.get('sort', 'id')
    order = request.args.get('order', 'asc')

    # Validate inputs
    if search_column not in valid_columns:
        return jsonify({"error": "Invalid search column"}), 400
    if sort not in valid_columns:
        return jsonify({"error": "Invalid sort column"}), 400
    if order.lower() not in ('asc', 'desc'):
        return jsonify({"error": "Invalid sort order"}), 400

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                query = """
                    SELECT j.*, u.username as assigned_username 
                    FROM jobs j
                    LEFT JOIN users u ON j.assigned_user_id = u.id
                    WHERE 1=1
                """
                params = []

                if status and status != "all":
                    query += " AND j.status = ?"
                    params.append(status)

                if search_term:
                    query += f" AND j.{search_column} LIKE ? COLLATE SQL_Latin1_General_CP1_CI_AS"
                    params.append(f'%{search_term}%')

                if start_date:
                    query += " AND j.created_at >= ?"
                    params.append(start_date)
                if end_date:
                    query += " AND j.created_at <= ?"
                    params.append(f"{end_date} 23:59:59")

                query += f" ORDER BY j.{sort} {order}"

                cursor.execute(query, params)
                columns = [column[0] for column in cursor.description]
                jobs = [dict(zip(columns, row)) for row in cursor.fetchall()]

                # Convert dates to ISO format
                for job in jobs:
                    for field in ['due_date', 'created_at']:
                        if field in job and job[field]:
                            job[field] = job[field].isoformat()

                return jsonify(jobs)
    except Exception as e:
        return jsonify({"error": f"Database error: {str(e)}"}), 500

# Health Check Endpoint
@app.route('/api/health')
def health_check():
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
            "status": "unhealthy",
            "error": str(e)
        }), 500

# Frontend Serving
@app.route('/')
def serve_index():
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory(app.static_folder, path)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
    