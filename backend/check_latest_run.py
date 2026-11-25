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
cur.execute('SELECT id, status, progress, total FROM campaign_runs ORDER BY id DESC LIMIT 1')
r = cur.fetchone()

print(f"Latest run:")
print(f"  ID: {r['id']}")
print(f"  Status: {r['status']}")
print(f"  Progress: {r['progress']}/{r['total']}")

cur.close()
conn.close()
