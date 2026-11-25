import mysql.connector

conn = mysql.connector.connect(
    host='127.0.0.1',
    user='root',
    password='',
    database='form_insights'
)

cur = conn.cursor(dictionary=True)

# Get websites with POST responses
cur.execute("""
    SELECT DISTINCT
        fs.url
    FROM form_submissions fs
    INNER JOIN form_submissions_details sd ON fs.id = sd.submission_id
    WHERE sd.response_json IS NOT NULL 
       AND sd.response_json != ''
       AND sd.response_json != '{}'
       AND sd.status_code > 0
    ORDER BY fs.created_at DESC
    LIMIT 50
""")

websites_with_responses = [row['url'] for row in cur.fetchall()]

print("✅ WEBSITES THAT RETURNED POST RESPONSES:")
print("=" * 80)
for i, url in enumerate(websites_with_responses, 1):
    print(f"{i}. {url}")

print(f"\n\nTotal: {len(websites_with_responses)} websites")

# Also get all successful submissions
cur.execute("""
    SELECT DISTINCT url
    FROM form_submissions
    WHERE status IN ('success', 'sent_confirmed', 'sent_unverified')
    ORDER BY created_at DESC
    LIMIT 50
""")

successful_websites = [row['url'] for row in cur.fetchall()]

print("\n\n✅ ALL SUCCESSFUL SUBMISSIONS (with or without POST response):")
print("=" * 80)
for i, url in enumerate(successful_websites, 1):
    print(f"{i}. {url}")

print(f"\n\nTotal: {len(successful_websites)} websites")

cur.close()
conn.close()

# Save to file for easy copying
with open('working_websites_list.txt', 'w') as f:
    f.write("WEBSITES WITH POST RESPONSES:\n")
    f.write("=" * 80 + "\n")
    for url in websites_with_responses:
        f.write(url + "\n")
    
    f.write("\n\nALL SUCCESSFUL SUBMISSIONS:\n")
    f.write("=" * 80 + "\n")
    for url in successful_websites:
        f.write(url + "\n")

print("\n\n✅ List saved to: working_websites_list.txt")
