import mysql.connector

conn = mysql.connector.connect(
    host='127.0.0.1',
    user='root',
    password='',
    database='form_insights'
)

cur = conn.cursor()

# Check form_submissions structure
print("=== form_submissions structure ===")
cur.execute("DESCRIBE form_submissions")
for row in cur.fetchall():
    print(row)

print("\n=== form_submissions_details structure ===")
cur.execute("DESCRIBE form_submissions_details")
for row in cur.fetchall():
    print(row)

# Check counts
cur.execute("SELECT COUNT(*) FROM form_submissions")
print(f"\nform_submissions: {cur.fetchone()[0]} records")

cur.execute("SELECT COUNT(*) FROM form_submissions_details")
print(f"form_submissions_details: {cur.fetchone()[0]} records")

cur.close()
conn.close()
