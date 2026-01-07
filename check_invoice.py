import psycopg2

DATABASE_URL = "postgresql://neondb_owner:npg_aGzdo2jblwx9@ep-holy-smoke-a4e3gdau-pooler.us-east-1.aws.neon.tech/neondb?sslmode=require"

try:
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    
    print("\n=== Checking INV-00008 ===")
    
    # Check if sale exists
    cur.execute("SELECT * FROM sales WHERE invoice_no = 'INV-00008'")
    sale = cur.fetchone()
    if sale:
        print(f"✅ Sale found: {sale}")
    else:
        print("❌ Sale not found")
    
    # Check if items exist
    cur.execute("SELECT * FROM sale_items WHERE invoice_no = 'INV-00008'")
    items = cur.fetchall()
    print(f"\n📦 Sale items count: {len(items)}")
    for item in items:
        print(f"   - {item}")
    
    if len(items) == 0:
        print("\n⚠️  No items found! This invoice was created before we added the sale_items save logic.")
        print("   Solution: Create a new sale to test returns/exchanges.")
    
    cur.close()
    conn.close()
    
except Exception as e:
    print(f"❌ Error: {e}")
