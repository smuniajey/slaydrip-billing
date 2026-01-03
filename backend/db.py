import psycopg2
import os

def get_connection():
    return psycopg2.connect(
        os.environ["postgresql://neondb_owner:npg_aGzdo2jblwx9@ep-holy-smoke-a4e3gdau-pooler.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"],
        sslmode="require"
    )
