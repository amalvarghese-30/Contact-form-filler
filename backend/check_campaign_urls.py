import mysql.connector
import sys

# Fix encoding for Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

conn = mysql.connector.connect(
    host='127.0.0.1',
    user='root',
    password='',
    database='form_insights'
)

cur = conn.cursor(dictionary=True)

print("=" * 80)
print("CAMPAIGN 16 - WEBSITE URLs")
print("=" * 80)

cur.execute("""
    SELECT website_id, website_url 
    FROM campaign_websites 
    WHERE campaign_id = 16
""")

websites = cur.fetchall()

if websites:
    for w in websites:
        print(f"\nWebsite ID: {w['website_id']}")
        print(f"URL: {w['website_url']}")
else:
    print("No websites found for campaign 16")

print("\n" + "=" * 80)
print("CHECKING IF THIS URL WORKED BEFORE")
print("=" * 80)

# Check if divineeldercare has successful submissions
cur.execute("""
    SELECT url, status, filled_fields, created_at
    FROM form_submissions
    WHERE url LIKE '%divineeldercare%'
      AND status IN ('success', 'sent_confirmed', 'sent_unverified')
    ORDER BY created_at DESC
    LIMIT 5
""")

successes = cur.fetchall()

if successes:
    print("\n[SUCCESS] This domain HAS successful submissions:")
    for s in successes:
        print(f"\n  URL: {s['url']}")
        print(f"  Status: {s['status']}")
        print(f"  Fields Filled: {s['filled_fields']}")
        print(f"  Date: {s['created_at']}")
else:
    print("\n[FAIL] No successful submissions found for divineeldercare.in")

cur.close()
conn.close()

print("\n" + "=" * 80)
print("RECOMMENDATION")
print("=" * 80)
print("If the successful URL is different from the campaign URL,")
print("update your campaign to use the working URL!")
