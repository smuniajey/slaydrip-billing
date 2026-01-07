import psycopg2
import os

# Set the connection string
DATABASE_URL = "postgresql://neondb_owner:npg_aGzdo2jblwx9@ep-holy-smoke-a4e3gdau-pooler.us-east-1.aws.neon.tech/neondb?sslmode=require"

try:
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    
    print("Creating sale_items table...")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS sale_items (
            id BIGSERIAL PRIMARY KEY,
            invoice_no VARCHAR(50) NOT NULL,
            design_id INTEGER NOT NULL,
            size VARCHAR(10) NOT NULL,
            quantity INTEGER NOT NULL,
            price NUMERIC(12,2) NOT NULL,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    
    cur.execute("CREATE INDEX IF NOT EXISTS idx_sale_items_invoice ON sale_items(invoice_no)")
    
    print("Creating returns table...")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS returns (
            id BIGSERIAL PRIMARY KEY,
            return_ref VARCHAR(50) NOT NULL,
            invoice_no VARCHAR(50) NOT NULL,
            design_id INTEGER NOT NULL,
            size VARCHAR(10) NOT NULL,
            quantity INTEGER NOT NULL CHECK (quantity > 0),
            refund_amount NUMERIC(12,2) NOT NULL,
            return_type VARCHAR(10) NOT NULL CHECK (return_type IN ('RETURN','EXCHANGE')),
            payment_mode VARCHAR(10) NOT NULL CHECK (payment_mode IN ('Cash','UPI','Card')),
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    
    cur.execute("CREATE INDEX IF NOT EXISTS idx_returns_invoice ON returns (invoice_no)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_returns_design_size ON returns (design_id, size)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_returns_ref ON returns (return_ref)")
    
    print("Creating exchange_details table...")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS exchange_details (
            id BIGSERIAL PRIMARY KEY,
            exchange_ref VARCHAR(50) NOT NULL,
            invoice_no VARCHAR(50) NOT NULL,
            design_id INTEGER NOT NULL,
            size VARCHAR(10) NOT NULL,
            quantity INTEGER NOT NULL CHECK (quantity > 0),
            unit_price NUMERIC(12,2) NOT NULL,
            line_total NUMERIC(12,2) NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    
    cur.execute("CREATE INDEX IF NOT EXISTS idx_exchange_ref ON exchange_details (exchange_ref)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_exchange_invoice ON exchange_details (invoice_no)")
    
    conn.commit()
    print("✅ All tables created successfully!")
    
    cur.close()
    conn.close()
    
except Exception as e:
    print(f"❌ Error: {e}")
