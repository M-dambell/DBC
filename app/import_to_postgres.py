import psycopg2
import pandas as pd
from io import StringIO

# Connection strings
OLD_DB = "postgresql://dbc_jtdb_user:eBH1D0XF5oAMNt1cuU5sXyob9YzivI0m@dpg-cvd9jlhu0jms739lbnug-a.oregon-postgres.render.com/dbc_jtdb?sslmode=require"
NEW_DB = "postgresql://neondb_owner:npg_Ut8s9TLJEVRq@ep-cold-grass-abiz6twt-pooler.eu-west-2.aws.neon.tech/Job-TrackingDataBase?sslmode=require"

def transfer_table(table_name):
    # Extract from old DB
    with psycopg2.connect(OLD_DB) as conn:
        df = pd.read_sql(f"SELECT * FROM {table_name}", conn)
    
    # Load to Neon
    with psycopg2.connect(NEW_DB) as conn:
        cursor = conn.cursor()
        buffer = StringIO()
        df.to_csv(buffer, index=False, header=False)
        buffer.seek(0)
        cursor.copy_expert(f"COPY {table_name} FROM STDIN WITH CSV", buffer)
        conn.commit()
    print(f"Transferred {len(df)} rows to {table_name}")

# Run migration
transfer_table("users")
transfer_table("jobs")
