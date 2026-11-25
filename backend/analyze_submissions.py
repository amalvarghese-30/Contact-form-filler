import mysql.connector

conn = mysql.connector.connect(
    host='127.0.0.1',
    user='root',
    password='',
    database='form_insights'
)

cur = conn.cursor(dictionary=True)

# Get overall statistics
print("=== Overall Submission Statistics ===\n")
cur.execute("""
    SELECT 
        status,
        COUNT(*) as count
    FROM form_submissions
    GROUP BY status
    ORDER BY count DESC
""")

stats = cur.fetchall()
total = sum(s['count'] for s in stats)
print(f"Total submissions: {total}\n")
for stat in stats:
    pct = (stat['count'] / total * 100) if total > 0 else 0
    print(f"{stat['status']:15} {stat['count']:5} ({pct:5.1f}%)")

# Get recent successful submissions
print("\n\n=== Recent Successful Submissions (last 10) ===\n")
cur.execute("""
    SELECT url, filled_fields, created_at
    FROM form_submissions
    WHERE status = 'success'
    ORDER BY created_at DESC
    LIMIT 10
""")

successes = cur.fetchall()
for sub in successes:
    print(f"{sub['url'][:60]:60} | {sub['filled_fields']} fields | {sub['created_at']}")

# Get recent failed submissions
print("\n\n=== Recent Failed Submissions (last 10) ===\n")
cur.execute("""
    SELECT url, error, created_at
    FROM form_submissions
    WHERE status = 'failed'
    ORDER BY created_at DESC
    LIMIT 10
""")

failures = cur.fetchall()
for sub in failures:
    error_short = (sub['error'] or '')[:50]
    print(f"{sub['url'][:40]:40} | {error_short:50} | {sub['created_at']}")

# Check submission details table
print("\n\n=== Submission Details Count ===\n")
cur.execute("SELECT COUNT(*) as count FROM form_submissions_details")
details_count = cur.fetchone()['count']
print(f"Total submission details records: {details_count}")

if details_count > 0:
    print("\n=== Recent Submission Details (last 5) ===\n")
    cur.execute("""
        SELECT sd.id, sd.submission_id, sd.request_url, sd.status_code, 
               fs.url as form_url, fs.status as form_status
        FROM form_submissions_details sd
        JOIN form_submissions fs ON sd.submission_id = fs.id
        ORDER BY sd.created_at DESC
        LIMIT 5
    """)
    
    details = cur.fetchall()
    for det in details:
        print(f"Detail ID: {det['id']} | Submission ID: {det['submission_id']}")
        print(f"  Form URL: {det['form_url']}")
        print(f"  Request URL: {det['request_url']}")
        print(f"  Status: {det['form_status']} | HTTP Code: {det['status_code']}")
        print()

cur.close()
conn.close()
