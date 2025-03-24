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
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM jobs;")
    jobs = cursor.fetchall()
    conn.close()
    
    job_list = [{
        "id": j[0],
        "name": j[1],
        "job_num": j[2],
        "qty": j[3],
        "details_of_job": j[4],
        "due_date": j[5],
        "department": j[6],
        "person_in_charge": j[7],
        "status": j[8],
        "created_at": j[9]
    } for j in jobs]
    return jsonify(job_list)

if __name__ == '__main__':
    app.run(debug=True)
