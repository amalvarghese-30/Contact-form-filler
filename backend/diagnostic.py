import sqlite3
import os

db_path = '../data/urls.db'

# Check if file exists
if os.path.exists(db_path):
    print(f"✅ Database file exists: {db_path}")
    print(f"   Size: {os.path.getsize(db_path)} bytes")
else:
    print(f"❌ Database file NOT found: {db_path}")
    exit(1)

# Connect and check tables
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Get all tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()
print(f"\n📊 Tables in database:")
for table in tables:
    print(f"   - {table[0]}")

# Check company_urls table
print(f"\n📋 Checking company_urls table:")
try:
    cursor.execute("SELECT COUNT(*) FROM company_urls")
    count = cursor.fetchone()[0]
    print(f"   Total URLs: {count}")
    
    if count > 0:
        print(f"\n   Sample URLs:")
        cursor.execute("SELECT id, url, status FROM company_urls LIMIT 5")
        for row in cursor.fetchall():
            print(f"      ID={row[0]}, URL={row[1]}, Status={row[2]}")
    else:
        print(f"  ⚠️  Table is EMPTY!")
except Exception as e:
    print(f"   ❌ Error: {e}")

conn.close()
print(f"\n✅ Diagnostic complete!")
