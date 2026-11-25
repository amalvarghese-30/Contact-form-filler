import requests
import json

# Test the campaign creation endpoint
url = "http://127.0.0.1:8000/api/campaigns"

# Sample campaign data (matching what the frontend would send)
campaign_data = {
    "name": "testing3",
    "description": "rfe",
    "sender_name": "gaurav",
    "sender_email": "e4vf",
    "subject_line": "wfewf",
    "message_body": "wefwef",
    "max_websites": 25000,
    "targets": [
        "http://wa.me",
        "https://link.zomato.com",
        "https://bharatspinlaundry.com",
        "http://jkmaharaj.com",
        "http://www.landmarkrealities.com"
    ]
}

print("Testing campaign creation...")
print(f"URL: {url}")
print(f"Data: {json.dumps(campaign_data, indent=2)}")
print("\nSending POST request...")

try:
    response = requests.post(url, json=campaign_data, timeout=10)
    print(f"\nStatus Code: {response.status_code}")
    print(f"Response: {response.text[:500]}")
    
    if response.status_code != 200:
        print("\n" + "=" * 80)
        print("ERROR DETECTED!")
        print("=" * 80)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")
        
except Exception as e:
    print(f"\nException occurred: {type(e).__name__}")
    print(f"Error: {str(e)}")
