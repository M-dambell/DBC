import psycopg2
import pandas as pd
from datetime import datetime
from database import create_table
print("fndmk")

# Replace these with your Render PostgreSQL credentials
DB_NAME = "dbc_jtdb"
DB_USER = "dbc_jtdb_user"
DB_PASSWORD = "eBH1D0XF5oAMNt1cuU5sXyob9YzivI0m"
DB_HOST = "dpg-cvd9jlhu0jms739lbnug-a.oregon-postgres.render.com"  # Use the full hostname
DB_PORT = 5432  # Default port for PostgreSQL

# Connect to PostgreSQL database
try:
    print("Connecting to the database...")
    conn = psycopg2.connect(
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST,
        port=DB_PORT,
        sslmode="require",  # Required for Render PostgreSQL
        connect_timeout=60  # Timeout after 60 seconds
    )
    cursor = conn.cursor()
    print("✅ Connected to the Render database successfully!")
except psycopg2.OperationalError as e:
    print(f"❌ Failed to connect to the Render database: {e}")
    exit()

# Ensure the table exists
try:
    print("Creating 'jobs' table if it doesn't exist...")
    create_table();
    conn.commit()
    print("✅ 'jobs' table created or already exists.")
except Exception as e:
    print(f"❌ Failed to create 'jobs' table: {e}")
    conn.close()
    exit()

# Load and clean Excel data
file_path = "Copy of Job Tracker 2025.xlsx"  # Ensure the file is in the same folder
try:
    print(f"Loading Excel file from: {file_path}")
    # Skip the first row (title) and use the second row as headers
    df = pd.read_excel(file_path, sheet_name="Table 1", skiprows=1)
    print("✅ Excel file loaded successfully!")
except Exception as e:
    print(f"❌ Failed to load Excel file: {e}")
    conn.close()
    exit()

# Rename columns to match the database
df.columns = ["name", "job_num", "qty", "details_of_job", "due_date", "department", "person_in_charge", "status", "created_at"]

# Remove rows that contain headers or non-data rows
df = df[~df["name"].str.contains("NAME", na=False)]  # Remove rows where "name" contains "NAME"

# Convert to proper format and handle NaT values
df["due_date"] = pd.to_datetime(df["due_date"], errors="coerce")
df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")

df["due_date"] = df["due_date"].apply(lambda x: None if pd.isna(x) else x)  # Replace NaT with None
df["created_at"] = df["created_at"].apply(lambda x: None if pd.isna(x) else x)

# Clean the 'qty' column: ensure it contains only numeric values
df["qty"] = pd.to_numeric(df["qty"], errors="coerce")  # Convert non-numeric values to NaN
df["qty"] = df["qty"].fillna(0).astype(int)  # Replace NaN with 0 and convert to integer

# Insert data into PostgreSQL
try:
    print("Inserting data into PostgreSQL...")
    for _, row in df.iterrows():
        cursor.execute("""
            INSERT INTO jobs (name, job_num, qty, details_of_job, due_date, department, person_in_charge, status, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (job_num) DO NOTHING
        """, (
            row["name"],
            row["job_num"],
            row["qty"],
            row["details_of_job"],
            row["due_date"] if not pd.isna(row["due_date"]) else None,  # Insert NULL for NaT
            row["department"],
            row["person_in_charge"],
            row["status"],
            row["created_at"]
        ))
    conn.commit()
    print("✅ Data inserted into Render PostgreSQL successfully!")
except Exception as e:
    print(f"❌ Failed to insert data into Render PostgreSQL: {e}")
finally:
    conn.close()
