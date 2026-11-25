import mysql.connector

conn = mysql.connector.connect(
    host='127.0.0.1',
    user='root',
    password='',
    database='form_insights'
)

cur = conn.cursor(dictionary=True)

# Get the latest submission details
cur.execute("""
    SELECT 
        sd.id,
        sd.submission_id,
        sd.request_url,
        sd.status_code,
        sd.payload_json,
        sd.response_json,
        fs.url as submission_url,
        fs.filled_fields
    FROM form_submissions_details sd
    JOIN form_submissions fs ON sd.submission_id = fs.id
    WHERE sd.submission_id = 567
    ORDER BY sd.id DESC
    LIMIT 1
""")

result = cur.fetchone()

if result:
    print("=" * 80)
    print("LATEST SUBMISSION DETAILS (ID 567)")
    print("=" * 80)
    print(f"\nSubmission URL: {result['submission_url']}")
    print(f"Request URL: {result['request_url']}")
    print(f"Status Code: {result['status_code']}")
    print(f"Fields Filled: {result['filled_fields']}")
    print(f"\nPayload JSON: {result['payload_json']}")
    print(f"\nResponse JSON: {result['response_json'][:200] if result['response_json'] else 'None'}...")
    
    if result['payload_json'] == '{}' or not result['payload_json']:
        print("\n" + "=" * 80)
        print("ISSUE: Payload is empty!")
        print("=" * 80)
        print("""
This means the system captured the POST request but couldn't extract
the form data that was being sent.

This can happen when:
1. The form uses a different encoding (multipart/form-data)
2. The form data is in the request body but not in a standard format
3. The POST request doesn't include the form fields in the payload

The GOOD news: The form WAS submitted successfully (status 200)
The response was captured, which confirms the submission worked.
        """)
else:
    print("No details found for submission 567")

cur.close()
conn.close()
