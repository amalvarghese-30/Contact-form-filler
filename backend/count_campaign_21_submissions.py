import mysql.connector

conn = mysql.connector.connect(
    host="127.0.0.1",
    port=3306,
    user="root",
    password="",
    database="form_insights"
)

cur = conn.cursor(dictionary=True)

# Count submissions for campaign 21
cur.execute("""
    SELECT status, COUNT(*) as count 
    FROM form_submissions 
    WHERE campaignid = 21
    GROUP BY status
    ORDER BY count DESC
""")
status_counts = cur.fetchall()

print("=== Campaign 21 Form Submissions ===")
total = 0
for row in status_counts:
    print(f"  {row['status']}: {row['count']}")
    total += row['count']
print(f"\nTotal submissions attempted: {total}")

print("\n=== Expected ===")
print("  Total URLs: 385")
print("  Captcha: 54")
print("  No Form: 272")
print("  Should attempt to fill: 385 - 54 - 272 = 59")
print(f"\n=== Gap ===")
print(f"  Expected: 59")
print(f"  Actual: {total}")
print(f"  Missing: {59 - total}")

cur.close()
conn.close()
