import mysql.connector
import time

time.sleep(5)

conn = mysql.connector.connect(
    host='127.0.0.1',
    user='root',
    password='',
    database='form_insights'
)

cur = conn.cursor(dictionary=True)
cur.execute('SELECT status, error FROM campaign_runs WHERE id=88')
r = cur.fetchone()

print(f"Status: {r['status']}")
print(f"Error: {r['error']}")

cur.close()
conn.close()
