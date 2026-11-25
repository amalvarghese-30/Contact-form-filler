import sqlite3

conn = sqlite3.connect('../data/urls.db')
cursor = conn.cursor()

# Update first 10 to completed
cursor.execute("SELECT id FROM company_urls LIMIT 10")
ids = [row[0] for row in cursor.fetchall()]

for i, id in enumerate(ids):
    if i % 3 == 0:
        status = 'completed'
    elif i % 3 == 1:
        status = 'in_progress'
    else:
        status = 'captcha'
    
    cursor.execute("UPDATE company_urls SET status = ? WHERE id = ?", (status, id))

conn.commit()
conn.close()

print("✅ Updated statuses for testing!")
