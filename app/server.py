from flask import Flask, jsonify, request, send_from_directory
import sqlite3
import os

app = Flask(__name__)

def connect_db():
    return sqlite3.connect("jobs.db")

@app.route('/')
def serve_frontend():
    return send_from_directory(os.path.join(app.root_path, 'app/static'), 'index.html')

@app.route('/jobs', methods=['GET'])
def get_jobs():
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM jobs;")
    jobs = cursor.fetchall()
    conn.close()
    
    job_list = [{"id": j[0], "name": j[1], "job_num": j[2], "qty": j[3], "department": j[4], "status": j[5]} for j in jobs]
    return jsonify(job_list)

if __name__ == '__main__':
    app.run(debug=True)
