import sqlite3

db_path = '../data/urls.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("Fixing database schema...")
print("="*60)

cursor.execute("PRAGMA table_info(company_urls)")
existing_columns = [col[1] for col in cursor.fetchall()]
print(f"Existing columns in company_urls: {existing_columns}")

missing_columns = {
    'processed_at': 'TIMESTAMP',
    'error_message': 'TEXT'
}

for col_name, col_type in missing_columns.items():
    if col_name not in existing_columns:
        try:
            cursor.execute(f"ALTER TABLE company_urls ADD COLUMN {col_name} {col_type}")
            print(f"✅ Added column: {col_name}")
        except Exception as e:
            print(f"❌ Error adding {col_name}: {e}")
    else:
        print(f"✅ Column {col_name} already exists")

cursor.execute("PRAGMA table_info(form_fields)")
form_cols = [col[1] for col in cursor.fetchall()]
print(f"\nExisting columns in form_fields: {form_cols}")

if 'is_required' not in form_cols:
    try:
        cursor.execute("ALTER TABLE form_fields ADD COLUMN is_required BOOLEAN DEFAULT 0")
        print(f"✅ Added column: is_required")
    except Exception as e:
        print(f"❌ Error adding is_required: {e}")
else:
    print(f"✅ Column is_required already exists")

conn.commit()
conn.close()

print("="*60)
print("✅ Database schema fixed!")
