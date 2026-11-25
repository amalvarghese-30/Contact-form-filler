import mysql.connector
import json

conn = mysql.connector.connect(
    host="127.0.0.1",
    port=3306,
    user="root",
    password="",
    database="form_insights"
)

cur = conn.cursor(dictionary=True)

# Get the latest run for campaign 21
cur.execute("""
    SELECT results 
    FROM campaign_runs 
    WHERE campaign_id = 21 
    ORDER BY id DESC 
    LIMIT 1
""")
run = cur.fetchone()

if run and run['results']:
    results = json.loads(run['results'])
    print("Campaign 21 Results:")
    print(f"  Total processed: {results.get('total', 0)}")
    print(f"  Scraped (found forms): {results.get('scraped', 0)}")
    print(f"  Success (filled): {results.get('success', 0)}")
    print(f"  Failed: {results.get('failed', 0)}")
    print(f"  Captcha: {results.get('captcha', 0)}")
    print(f"  No Form: {results.get('noform', 0)}")
    
    scraped = results.get('scraped', 0)
    captcha = results.get('captcha', 0)
    noform = results.get('noform', 0)
    
    print(f"\n=== Analysis ===")
    print(f"Total URLs: 385")
    print(f"Had captcha: {captcha}")
    print(f"No form found: {noform}")
    print(f"Forms found (scraped): {scraped}")
    print(f"Should have filled: {scraped} forms")
    print(f"Actually filled (success + failed): {results.get('success', 0) + results.get('failed', 0)}")

cur.close()
conn.close()
