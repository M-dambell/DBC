from flask import Flask, request, jsonify, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import psycopg2
from psycopg2.pool import SimpleConnectionPool
from psycopg2.extras import RealDictCursor
import os
from datetime import datetime, timedelta
import jwt
from flask_cors import CORS

# Initialize Flask app
app = Flask(__name__, static_folder='static')
app.secret_key = os.environ.get('SECRET_KEY') or os.urandom(24).hex()
CORS(app)

# Neon Database Configuration
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
    maxconn=10,
    **DB_CONFIG
)

# JWT Configuration
JWT_SECRET = os.environ.get('JWT_SECRET') or os.urandom(24).hex()
JWT_ALGORITHM = 'HS256'
JWT_EXPIRE_HOURS = 24

# Helper Functions
def get_db_connection():
    """Get a connection from the pool"""
    return connection_pool.getconn()

def return_db_connection(conn):
    """Return a connection to the pool"""
    connection_pool.putconn(conn)

def get_user_by_id(user_id):
    """Fetch user by ID"""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("SELECT id, username, role FROM users WHERE id = %s", (user_id,))
            return cursor.fetchone()
    finally:
        return_db_connection(conn)

# Auth Decorators
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

# API Routes
@app.route('/api/login', methods=['POST'])
def login():
    """Authenticate user and return JWT token"""
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({"error": "Username and password required"}), 400

    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("SELECT id, password_hash, role FROM users WHERE username = %s", (username,))
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
    finally:
        return_db_connection(conn)

@app.route('/api/jobs', methods=['GET'])
@token_required
def get_jobs(current_user):
    """Get all jobs"""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("SELECT * FROM jobs")
            jobs = cursor.fetchall()
            return jsonify(jobs)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        return_db_connection(conn)

# Frontend Serving (MUST BE LAST ROUTE)
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_frontend(path):
    """Serve static files or index.html for frontend routing"""
    if path and os.path.exists(os.path.join(app.static_folder, path)):
        return send_from_directory(app.static_folder, path)
    return send_from_directory(app.static_folder, 'index.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
    