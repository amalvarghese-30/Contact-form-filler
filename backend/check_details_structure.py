import mysql.connector

conn = mysql.connector.connect(
    host='127.0.0.1',
    user='root',
    password='',
    database='form_insights'
)

cur = conn.cursor()
cur.execute("DESCRIBE form_submissions_details")
print("form_submissions_details columns:")
for row in cur.fetchall():
    print(f"  {row[0]}: {row[1]} (Null: {row[2]}, Key: {row[3]}, Default: {row[4]})")

cur.close()
conn.close()
