import mysql.connector
from datetime import datetime, timedelta

conn = mysql.connector.connect(
    host='127.0.0.1',
    user='root',
    password='',
    database='form_insights'
)

cur = conn.cursor(dictionary=True)

# Check recent submissions (last hour)
one_hour_ago = datetime.now() - timedelta(hours=1)

print("=== Recent Form Submissions (last hour) ===")
cur.execute("""
    SELECT id, website_id, url, status, filled_fields, error, created_at
    FROM form_submissions
    WHERE created_at >= %s
    ORDER BY created_at DESC
    LIMIT 20
""", (one_hour_ago,))

submissions = cur.fetchall()
print(f"\nFound {len(submissions)} submissions in the last hour\n")

if submissions:
    for sub in submissions:
        print(f"ID: {sub['id']}")
        print(f"  URL: {sub['url']}")
        print(f"  Status: {sub['status']}")
        print(f"  Filled Fields: {sub['filled_fields']}")
        print(f"  Error: {sub['error']}")
        print(f"  Created: {sub['created_at']}")
        print()
else:
    print("No submissions found in the last hour")

# Check submission details
print("\n=== Form Submission Details (last 10) ===")
cur.execute("""
    SELECT id, submission_id, request_url, status_code, created_at
    FROM form_submissions_details
    ORDER BY created_at DESC
    LIMIT 10
""")

details = cur.fetchall()
print(f"\nFound {len(details)} submission details\n")

if details:
    for det in details:
        print(f"Detail ID: {det['id']}")
        print(f"  Submission ID: {det['submission_id']}")
        print(f"  Request URL: {det['request_url']}")
        print(f"  Status Code: {det['status_code']}")
        print(f"  Created: {det['created_at']}")
        print()
else:
    print("No submission details found")

# Summary statistics
print("\n=== Summary Statistics ===")
cur.execute("""
    SELECT 
        status,
        COUNT(*) as count,
        AVG(filled_fields) as avg_filled
    FROM form_submissions
    WHERE created_at >= %s
    GROUP BY status
""", (one_hour_ago,))

stats = cur.fetchall()
for stat in stats:
    print(f"{stat['status']}: {stat['count']} submissions (avg {stat['avg_filled']:.1f} fields filled)")

cur.close()
conn.close()
