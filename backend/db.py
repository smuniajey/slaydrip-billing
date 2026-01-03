import os
import psycopg2
from psycopg2.extras import RealDictCursor

def get_connection():
    return psycopg2.connect(
        os.environ["postgresql://neondb_owner:npg_aGzdo2jblwx9@ep-holy-smoke-a4e3gdau-pooler.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"],
        cursor_factory=RealDictCursor,
        sslmode="require"
    )

