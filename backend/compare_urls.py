import mysql.connector

conn = mysql.connector.connect(
    host='127.0.0.1',
    user='root',
    password='',
    database='form_insights'
)

cur = conn.cursor()

# Get campaign URL
cur.execute("SELECT website_url FROM campaign_websites WHERE campaign_id = 16")
campaign_url = cur.fetchone()

# Get successful URL
cur.execute("""
    SELECT url FROM form_submissions
    WHERE url LIKE '%divineeldercare%'
      AND status IN ('success', 'sent_confirmed', 'sent_unverified')
    ORDER BY created_at DESC
    LIMIT 1
""")
success_url = cur.fetchone()

cur.close()
conn.close()

print("CAMPAIGN URL:", campaign_url[0] if campaign_url else "None")
print("SUCCESSFUL URL:", success_url[0] if success_url else "None")

if campaign_url and success_url:
    if campaign_url[0] != success_url[0]:
        print("\nPROBLEM: URLs are DIFFERENT!")
        print(f"Change {campaign_url[0]}")
        print(f"To: {success_url[0]}")
    else:
        print("\nURLs match - investigating other issues...")
