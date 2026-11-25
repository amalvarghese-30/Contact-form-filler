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

# Update campaign 20 to have no limit
cur.execute("UPDATE campaigns SET max_websites = 999999 WHERE id = 20")
conn.commit()

print(f"✅ Updated campaign 20: max_websites set to 999999")
print(f"   Your campaign will now process all 385 URLs!")

cur.close()
conn.close()
