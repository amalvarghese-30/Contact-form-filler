import sqlite3

DB_PATH = "../data/urls.db"

all_urls = [
]

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

print("Cleaning database...")
cursor.execute("DELETE FROM form_fields")
cursor.execute("DELETE FROM company_urls")
cursor.execute("DELETE FROM sqlite_sequence")

print(f"Importing {len(all_urls)} URLs...")

for url in all_urls:
    try:
        cursor.execute("INSERT INTO company_urls (url, status) VALUES (?, ?)", (url, "pending"))
    except Exception as e:
        print(f"  Error with {url}: {e}")

conn.commit()
conn.close()

# Verify
conn = sqlite3.connect(DB_PATH)
c = conn.cursor()
c.execute("SELECT COUNT(*) FROM company_urls")
count = c.fetchone()[0]
conn.close()

print(f"✅ Successfully imported {count} URLs!")
