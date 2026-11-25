import re

# Read the file
with open('fastapi_backend.py', 'r', encoding='utf-8') as f:
    content = f.read()

# The code to insert
new_code = '''

class CampaignCreate(BaseModel):
    name: str
    description: Optional[str] = ""
    sender_name: Optional[str] = ""
    sender_email: Optional[str] = ""
    subject_line: Optional[str] = ""
    message_body: Optional[str] = ""
    max_websites: Optional[int] = 50
    targets: List[str] = []


@app.post("/api/campaigns")
def create_campaign(campaign: CampaignCreate):
    """Create a new campaign with target websites"""
    conn = getconn()
    cur = conn.cursor(dictionary=True)
    try:
        # Insert campaign
        cur.execute(
            f"""
            INSERT INTO {CAMPAIGNS_TABLE} 
            (name, description, sender_name, sender_email, subject_line, message_body, max_websites, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'draft')
            """,
            (
                campaign.name,
                campaign.description,
                campaign.sender_name,
                campaign.sender_email,
                campaign.subject_line,
                campaign.message_body,
                campaign.max_websites
            )
        )
        campaign_id = cur.lastrowid
        
        # Insert target websites
        if campaign.targets:
            for url in campaign.targets:
                cur.execute(
                    f"""
                    INSERT INTO {CAMPAIGN_WEBSITES_TABLE} (campaign_id, website_url)
                    VALUES (%s, %s)
                    """,
                    (campaign_id, url.strip())
                )
        
        conn.commit()
        
        return {
            "id": campaign_id,
            "name": campaign.name,
            "status": "draft",
            "targets": len(campaign.targets)
        }
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close()
        conn.close()

'''

# Find the location to insert (after list_campaigns function, before get_campaign)
# Look for the pattern: closing of list_campaigns and start of get_campaign
pattern = r'(def list_campaigns\(\):.*?conn\.close\(\)\n\n)(.*?@app\.get\("/api/campaigns/\{campaign_id\}"\))'

match = re.search(pattern, content, re.DOTALL)

if match:
    # Insert the new code between the two functions
    updated_content = content[:match.end(1)] + new_code + content[match.start(2):]
    
    # Write back
    with open('fastapi_backend.py', 'w', encoding='utf-8') as f:
        f.write(updated_content)
    
    print("✅ Successfully added POST /api/campaigns endpoint!")
    print(f"Inserted at position {match.end(1)}")
else:
    print("❌ Could not find the insertion point")
    print("Looking for list_campaigns function...")
