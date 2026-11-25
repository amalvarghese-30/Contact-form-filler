import mysql.connector
import json

conn = mysql.connector.connect(
    host='127.0.0.1',
    user='root',
    password='',
    database='form_insights'
)

cur = conn.cursor(dictionary=True)

print("=" * 80)
print("WEBSITES WITH CAPTURED POST RESPONSES")
print("=" * 80)
print("\nThese websites successfully returned POST responses that were captured:\n")

# Get submissions with details (meaning POST response was captured)
cur.execute("""
    SELECT 
        fs.id,
        fs.url,
        fs.status,
        fs.filled_fields,
        sd.request_url,
        sd.status_code,
        sd.payload_json,
        sd.response_json,
        fs.created_at
    FROM form_submissions fs
    INNER JOIN form_submissions_details sd ON fs.id = sd.submission_id
    WHERE sd.response_json IS NOT NULL 
       AND sd.response_json != ''
       AND sd.response_json != '{}'
    ORDER BY fs.created_at DESC
    LIMIT 30
""")

results = cur.fetchall()

if results:
    print(f"Found {len(results)} websites with POST responses:\n")
    
    for i, row in enumerate(results, 1):
        print(f"{i}. {row['url']}")
        print(f"   Status: {row['status']} | Fields Filled: {row['filled_fields']} | HTTP Code: {row['status_code']}")
        print(f"   Request URL: {row['request_url']}")
        
        # Try to parse and show response
        try:
            response = json.loads(row['response_json']) if row['response_json'] else {}
            if isinstance(response, dict):
                # Show first few keys
                keys = list(response.keys())[:5]
                if keys:
                    print(f"   Response keys: {', '.join(keys)}")
                else:
                    print(f"   Response: {str(response)[:100]}")
            else:
                print(f"   Response: {str(response)[:100]}")
        except:
            response_str = str(row['response_json'])[:100]
            print(f"   Response: {response_str}")
        
        print(f"   Date: {row['created_at']}")
        print()
else:
    print("No websites found with captured POST responses.")
    print("\nLet me check for ANY submissions with details...\n")
    
    cur.execute("""
        SELECT 
            fs.url,
            fs.status,
            sd.request_url,
            sd.status_code
        FROM form_submissions fs
        INNER JOIN form_submissions_details sd ON fs.id = sd.submission_id
        ORDER BY fs.created_at DESC
        LIMIT 20
    """)
    
    any_details = cur.fetchall()
    if any_details:
        print(f"Found {len(any_details)} submissions with details (but may not have response body):\n")
        for i, row in enumerate(any_details, 1):
            print(f"{i}. {row['url']}")
            print(f"   Status: {row['status']} | Request: {row['request_url']} | HTTP: {row['status_code']}")
            print()

# Also show websites that had successful status
print("\n" + "=" * 80)
print("WEBSITES MARKED AS SUCCESSFUL (may or may not have POST response)")
print("=" * 80)
print()

cur.execute("""
    SELECT url, filled_fields, error, created_at
    FROM form_submissions
    WHERE status IN ('success', 'sent_confirmed', 'sent_unverified')
    ORDER BY created_at DESC
    LIMIT 20
""")

successes = cur.fetchall()
if successes:
    print(f"Found {len(successes)} successful submissions:\n")
    for i, row in enumerate(successes, 1):
        error_msg = f" | Error: {row['error']}" if row['error'] else ""
        print(f"{i}. {row['url']}")
        print(f"   Fields: {row['filled_fields']}{error_msg}")
        print(f"   Date: {row['created_at']}")
        print()

cur.close()
conn.close()

print("\n" + "=" * 80)
print("RECOMMENDATION: Test these websites in a new campaign!")
print("=" * 80)
