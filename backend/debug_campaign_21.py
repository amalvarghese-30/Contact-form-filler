import mysql.connector
import json

conn = mysql.connector.connect(
    host="127.0.0.1",
    port=3306,
    user="root",
    password="",
    database="form_insights"
)

cur = conn.cursor(dictionary=True)

# Get all runs for campaign 21 to see the progression
cur.execute("""
    SELECT id, status, progress, total, results, started_at, finished_at
    FROM campaign_runs 
    WHERE campaign_id = 21 
    ORDER BY id DESC 
    LIMIT 5
""")
runs = cur.fetchall()

print("=== Campaign 21 Run History ===\n")
for run in runs:
    print(f"Run {run['id']}:")
    print(f"  Status: {run['status']}")
    print(f"  Progress: {run['progress']}/{run['total']}")
    if run['results']:
        try:
            results = json.loads(run['results'])
            print(f"  Results: success={results.get('success',0)}, failed={results.get('failed',0)}, captcha={results.get('captcha',0)}, noform={results.get('noform',0)}")
        except:
            pass
    print()

# Check form_submissions table for campaign-related data
# The table might not have campaign_id, so let's check its structure first
cur.execute("SHOW COLUMNS FROM form_submissions")
columns = cur.fetchall()
print("\n=== form_submissions table columns ===")
for col in columns:
    print(f"  {col['Field']}: {col['Type']}")

cur.close()
conn.close()
