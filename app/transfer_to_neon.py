import psycopg2
from psycopg2 import sql
import sys

# Database connections
OLD_DB = "postgresql://dbc_jtdb_user:eBH1D0XF5oAMNt1cuU5sXyob9YzivI0m@dpg-cvd9jlhu0jms739lbnug-a.oregon-postgres.render.com/dbc_jtdb"
NEW_DB = "postgresql://neondb_owner:npg_Ut8s9TLJEVRq@ep-cold-grass-abiz6twt-pooler.eu-west-2.aws.neon.tech/Job-TrackingDataBase"

def get_table_columns(conn, table_name):
    """Get column names and types for a table"""
    with conn.cursor() as cur:
        cur.execute(f"""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = '{table_name}'
            ORDER BY ordinal_position
        """)
        return cur.fetchall()

def create_compatible_table(src_conn, dest_conn, table_name):
    """Create a table in destination matching source structure"""
    src_columns = get_table_columns(src_conn, table_name)
    
    with dest_conn.cursor() as cur:
        # Drop table if exists (optional)
        cur.execute(f"DROP TABLE IF EXISTS {table_name} CASCADE")
        
        # Build CREATE TABLE statement
        columns_def = []
        for col in src_columns:
            col_name, col_type = col
            # Map generic types if needed
            if col_type == 'character varying':
                col_type = 'TEXT'
            elif col_type == 'timestamp without time zone':
                col_type = 'TIMESTAMP'
            columns_def.append(f"{col_name} {col_type}")
        
        # Add primary key if 'id' exists
        if any(col[0] == 'id' for col in src_columns):
            columns_def.append("PRIMARY KEY (id)")
        
        create_sql = f"""
            CREATE TABLE {table_name} (
                {', '.join(columns_def)}
            )
        """
        cur.execute(create_sql)
        dest_conn.commit()
    print(f"🔄 Created compatible {table_name} table in Neon")

def transfer_table(src_conn, dest_conn, table_name):
    """Transfer data between databases"""
    print(f"🚀 Transferring {table_name}...")
    
    with src_conn.cursor() as src_cur:
        # Get source data and column names
        src_cur.execute(f"SELECT * FROM {table_name}")
        columns = [desc[0] for desc in src_cur.description]
        data = src_cur.fetchall()
        
        with dest_conn.cursor() as dest_cur:
            # Prepare INSERT with only existing columns
            dest_columns = [col[0] for col in get_table_columns(dest_conn, table_name)]
            common_columns = [col for col in columns if col in dest_columns]
            
            if not common_columns:
                print(f"⚠️ No matching columns found for {table_name}")
                return
            
            insert_query = sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
                sql.Identifier(table_name),
                sql.SQL(', ').join(map(sql.Identifier, common_columns)),
                sql.SQL(', ').join([sql.Placeholder()] * len(common_columns))
            )
            
            # Prepare data with only matching columns
            col_indices = [columns.index(col) for col in common_columns]
            filtered_data = [[row[i] for i in col_indices] for row in data]
            
            # Insert data
            dest_cur.executemany(insert_query, filtered_data)
            dest_conn.commit()
            
    print(f"✅ Transferred {len(data)} rows ({len(common_columns)}/{len(columns)} columns)")

if __name__ == "__main__":
    try:
        # Connect to both databases
        src_conn = psycopg2.connect(OLD_DB)
        dest_conn = psycopg2.connect(NEW_DB)
        
        # Process tables in correct order
        for table in ["users", "jobs"]:
            create_compatible_table(src_conn, dest_conn, table)
            transfer_table(src_conn, dest_conn, table)
            
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        sys.exit(1)
        
    finally:
        src_conn and src_conn.close()
        dest_conn and dest_conn.close()
    
    print("🎉 Migration completed successfully!")
    