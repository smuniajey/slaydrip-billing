import os
import psycopg2

def get_connection():
    database_url = os.environ.get("DATABASE_URL")  # ✅ KEY name

    if not database_url:
        raise RuntimeError("DATABASE_URL not set")

    return psycopg2.connect(database_url)
