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

# Get campaign 21 run details
cur.execute("""
    SELECT id, campaign_id, status, progress, total, results, started_at, finished_at
    FROM campaign_runs 
    WHERE campaign_id = 21 
    ORDER BY id DESC 
    LIMIT 1
""")
run = cur.fetchone()

print("=== Campaign 21 Latest Run ===")
print(f"Run ID: {run['id']}")
print(f"Status: {run['status']}")
print(f"Progress: {run['progress']}/{run['total']}")
print(f"Started: {run['started_at']}")
print(f"Finished: {run['finished_at']}")

if run['results']:
    try:
        results = json.loads(run['results'])
        print(f"\nResults:")
        print(f"  Total: {results.get('total', 0)}")
        print(f"  Success: {results.get('success', 0)}")
        print(f"  Failed: {results.get('failed', 0)}")
        print(f"  Captcha: {results.get('captcha', 0)}")
        print(f"  Scraped: {results.get('scraped', 0)}")
        print(f"  NoForm: {results.get('noform', 0)}")
    except:
        print(f"  Raw: {run['results']}")

# Count actual submissions for campaign 21
cur.execute("""
    SELECT COUNT(*) as count 
    FROM form_submissions 
    WHERE campaign_id = 21
""")
submission_count = cur.fetchone()['count']
print(f"\nActual form submissions in database: {submission_count}")

# Count by status
cur.execute("""
    SELECT status, COUNT(*) as count 
    FROM form_submissions 
    WHERE campaign_id = 21
    GROUP BY status
""")
status_counts = cur.fetchall()
print(f"\nSubmissions by status:")
for row in status_counts:
    print(f"  {row['status']}: {row['count']}")

cur.close()
conn.close()
