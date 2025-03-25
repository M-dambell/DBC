# server.py
from flask import Flask, jsonify, request, send_from_directory
import psycopg2
import os

app = Flask(__name__)

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

@app.route('/')
def serve_frontend():
    return send_from_directory(os.path.join(app.root_path, 'static'), 'index.html')

@app.route('/jobs', methods=['GET'])
def get_jobs():
    status = request.args.get('status')
    sort_column = request.args.get('sort')
    sort_order = request.args.get('order', 'asc')
    
    conn = connect_db()
    cursor = conn.cursor()
    
    # Base query
    query = "SELECT * FROM jobs"
    
    # Add WHERE clause if filtering
    if status and status != "all":
        query += f" WHERE status = '{status}'"
    
    # Add ORDER BY if sorting
    valid_columns = ['id', 'name', 'job_num', 'qty', 'details_of_job', 
                    'due_date', 'department', 'person_in_charge', 'status', 'created_at']
    if sort_column in valid_columns:
        query += f" ORDER BY {sort_column} {sort_order}"
    
    cursor.execute(query)
    jobs = cursor.fetchall()
    conn.close()
    
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
        "created_at": j[9].strftime('%Y-%m-%d %H:%M:%S') if j[9] else None
    } for j in jobs]
    
    return jsonify(job_list)


@app.route('/jobs/<int:job_id>', methods=['PUT'])
def update_job(job_id):
    data = request.json
    conn = connect_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            UPDATE jobs 
            SET name = %s, job_num = %s, status = %s
            WHERE id = %s
            RETURNING *;
        """, (data['name'], data['job_num'], data['status'], job_id))
        
        updated_job = cursor.fetchone()
        conn.commit()
        
        return jsonify({
            "id": updated_job[0],
            "name": updated_job[1],
            "job_num": updated_job[2],
            "status": updated_job[8],
            "created_at": updated_job[9].strftime('%Y-%m-%d %H:%M:%S') if updated_job[9] else None
        })
        
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 400
        
    finally:
        conn.close()

if __name__ == '__main__':
    app.run(debug=True)
