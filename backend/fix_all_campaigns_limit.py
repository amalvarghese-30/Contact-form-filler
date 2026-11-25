import mysql.connector

# Connect to database
conn = mysql.connector.connect(
    host="127.0.0.1",
    port=3306,
    user="root",
    password="",
    database="form_insights"
)

cur = conn.cursor()

# Update ALL campaigns to have no limit
cur.execute("UPDATE campaigns SET max_websites = 999999")
affected = cur.rowcount
conn.commit()

print(f"✅ Updated {affected} campaigns: max_websites set to 999999")
print(f"   ALL campaigns will now process all their URLs!")

cur.close()
conn.close()
