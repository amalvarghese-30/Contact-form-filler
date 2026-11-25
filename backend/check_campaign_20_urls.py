import mysql.connector

conn = mysql.connector.connect(
    host="127.0.0.1",
    port=3306,
    user="root",
    password="",
    database="form_insights"
)

cur = conn.cursor()

# Check how many URLs are in campaign 20
cur.execute("SELECT COUNT(*) FROM campaign_websites WHERE campaign_id = 20")
count = cur.fetchone()[0]

print(f"Campaign 20 has {count} URLs in campaign_websites table")

# Check campaign details
cur.execute("SELECT id, name, max_websites FROM campaigns WHERE id = 20")
campaign = cur.fetchone()
print(f"Campaign details: id={campaign[0]}, name={campaign[1]}, max_websites={campaign[2]}")

cur.close()
conn.close()
