from flask import Flask, jsonify, request, send_from_directory
import psycopg2
from psycopg2.extras import DictCursor
from datetime import datetime
import os
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # Enable CORS

# Database configuration
DB_CONFIG = {
    "dbname": "dbc_jtdb",
    "user": "dbc_jtdb_user",
    "password": "eBH1D0XF5oAMNt1cuU5sXyob9YzivI0m",
    "host": "dpg-cvd9jlhu0jms739lbnug-a.oregon-postgres.render.com",
    "port": "5432",
    "sslmode": "require"
}

def get_db_connection():
    return psycopg2.connect(**DB_CONFIG)

@app.route('/')
def serve_frontend():
    return send_from_directory('static', 'index.html')

@app.route('/jobs', methods=['GET'])
def get_jobs():
    status = request.args.get('status')
    sort = request.args.get('sort', 'id')
    order = request.args.get('order', 'asc')
    
    valid_columns = ['id', 'name', 'job_num', 'qty', 'details_of_job', 
                   'due_date', 'department', 'person_in_charge', 'status', 'created_at']
    
    if sort not in valid_columns:
        sort = 'id'
    if order.upper() not in ['ASC', 'DESC']:
        order = 'ASC'
    
<<<<<<< Updated upstream
    # Format dates properly
    job_list = [{
        "id": j[0],
        "name": j[1],
        "job_num": j[2],
        "qty": j[3],
        "details_of_job": j[4],
        "due_date": j[5].strftime('%Y-%m-%d') if j[5] else None,
        "department": j[6],
        "person_in_charge": j[7],
        "status": j[8],
        "created_at": j[9].strftime('%Y-%m-%d %H:%M') if j[9] else None
    } for j in jobs]
    
    return jsonify(job_list)


@app.route('/jobs/<int:job_id>', methods=['PUT'])
def update_job(job_id):
    data = request.json
    conn = connect_db()
    cursor = conn.cursor()
=======
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=DictCursor)
>>>>>>> Stashed changes
    
    try:
        query = "SELECT * FROM jobs"
        params = []
        
        if status and status != "all":
            query += " WHERE status = %s"
            params.append(status)
        
        query += f" ORDER BY {sort} {order}"
        
        cursor.execute(query, params)
        jobs = cursor.fetchall()
        
        jobs_list = []
        for job in jobs:
            job_dict = dict(job)
            job_dict['created_at'] = job['created_at'].isoformat() if job['created_at'] else None
            job_dict['due_date'] = job['due_date'].isoformat() if job['due_date'] else None
            jobs_list.append(job_dict)
        
        return jsonify(jobs_list)
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/jobs', methods=['POST'])
def create_job():
    data = request.json
    
    # Validate required fields
    if not all(key in data for key in ['name', 'job_num', 'status']):
        return jsonify({"error": "Missing required fields"}), 400
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            INSERT INTO jobs (
                name, job_num, qty, details_of_job, due_date, 
                department, person_in_charge, status
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id, name, job_num, qty, details_of_job, 
                     due_date, department, person_in_charge, status, created_at
        """, (
            data['name'],
            data['job_num'],
<<<<<<< Updated upstream
            data['qty'],
            data.get('details_of_job', ''),
            data.get('due_date'),
            data['department'],
=======
            data.get('qty', 1),
            data.get('details_of_job', ''),
            data.get('due_date'),
            data.get('department', 'digital Print'),
>>>>>>> Stashed changes
            data.get('person_in_charge', ''),
            data['status']
        ))
        
        new_job = cursor.fetchone()
        conn.commit()
        
        job_dict = {
            "id": new_job[0],
            "name": new_job[1],
<<<<<<< Updated upstream
            "status": new_job[8]
        }), 201
=======
            "job_num": new_job[2],
            "qty": new_job[3],
            "details_of_job": new_job[4],
            "due_date": new_job[5].isoformat() if new_job[5] else None,
            "department": new_job[6],
            "person_in_charge": new_job[7],
            "status": new_job[8],
            "created_at": new_job[9].isoformat()
        }
>>>>>>> Stashed changes
        
        return jsonify(job_dict), 201
    
    except psycopg2.IntegrityError:
        conn.rollback()
        return jsonify({"error": "Job number must be unique"}), 400
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/jobs/<int:job_id>', methods=['PUT'])
def update_job(job_id):
    data = request.json
    
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=DictCursor)
    
    try:
        cursor.execute("""
            UPDATE jobs 
            SET name = %s, job_num = %s, status = %s
            WHERE id = %s
            RETURNING *
        """, (data['name'], data['job_num'], data['status'], job_id))
        
        updated_job = cursor.fetchone()
        if not updated_job:
            return jsonify({"error": "Job not found"}), 404
        
        conn.commit()
        
        job_dict = dict(updated_job)
        job_dict['created_at'] = updated_job['created_at'].isoformat()
        job_dict['due_date'] = updated_job['due_date'].isoformat() if updated_job['due_date'] else None
        
        return jsonify(job_dict)
    
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
    