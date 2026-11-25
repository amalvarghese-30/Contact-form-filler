import mysql.connector

conn = mysql.connector.connect(
    host='127.0.0.1',
    user='root',
    password='',
    database='form_insights'
)

cur = conn.cursor()
cur.execute("SHOW TABLES LIKE '%submission%'")
tables = [r[0] for r in cur.fetchall()]
print("Submission tables:", tables)

# Check form_submissions table
cur.execute("SELECT COUNT(*) FROM form_submissions")
count = cur.fetchone()[0]
print(f"\nform_submissions table has {count} records")

# Check if form_submissions_details exists
try:
    cur.execute("SELECT COUNT(*) FROM form_submissions_details")
    count_details = cur.fetchone()[0]
    print(f"form_submissions_details table has {count_details} records")
except Exception as e:
    print(f"form_submissions_details table error: {e}")

cur.close()
conn.close()
