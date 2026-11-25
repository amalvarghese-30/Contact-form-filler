import mysql.connector

conn = mysql.connector.connect(
    host='127.0.0.1',
    user='root',
    password='',
    database='form_insights'
)

cur = conn.cursor()

print("=" * 80)
print("FIXING CAMPAIGN 16 URL")
print("=" * 80)

# Show current URL
cur.execute("SELECT website_url FROM campaign_websites WHERE campaign_id = 16")
current = cur.fetchone()
print(f"\nCurrent URL: {current[0] if current else 'None'}")

# Update to correct URL
correct_url = "https://divineeldercare.in/contact-us/"
cur.execute("""
    UPDATE campaign_websites 
    SET website_url = %s
    WHERE campaign_id = 16
""", (correct_url,))

conn.commit()

# Verify the change
cur.execute("SELECT website_url FROM campaign_websites WHERE campaign_id = 16")
new = cur.fetchone()
print(f"New URL: {new[0] if new else 'None'}")

print("\n" + "=" * 80)
print("SUCCESS! Campaign URL updated.")
print("=" * 80)
print("\nNow restart your campaign and it should:")
print("1. Find the form on /contact-us/")
print("2. Fill the form fields")
print("3. Submit and capture the POST response")

cur.close()
conn.close()
