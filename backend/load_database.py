# FILE #11: backend/load_database.py
# Database Population Script - Copy this EXACTLY

#!/usr/bin/env python3
"""
Load company URLs into database
Run: python load_database.py
"""

import json
import os
import sys
from database import URLDatabase

def load_sample_data():
    """Load sample company data into database"""
    print("""
    ╔═════════════════════════════════════════╗
    ║  Contact Form Auto Filler               ║
    ║  Database Population Script             ║
    ╚═════════════════════════════════════════╝
    """)
    
    # Initialize database
    db = URLDatabase()
    print("✅ Database initialized\n")
    
    # Load companies.json
    companies_file = os.path.join(os.path.dirname(__file__), '..', 'data', 'companies.json')
    
    if not os.path.exists(companies_file):
        print(f"❌ File not found: {companies_file}")
        print("Create data/companies.json first")
        return
    
    print(f"📂 Loading from: {companies_file}")
    
    try:
        with open(companies_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        companies = data.get('companies', [])
        print(f"📊 Found {len(companies)} companies in file\n")
        
        if len(companies) == 0:
            print("❌ No companies found in JSON")
            return
        
        # Import to database
        print("📥 Importing to database...")
        added = db.add_urls_batch(companies)
        
        print(f"\n✅ Successfully added {added} URLs to database")
        
        # Show stats
        stats = db.get_database_stats()
        print(f"\n📊 Database Statistics:")
        print(f"   Total URLs: {stats['total_urls']}")
        print(f"   Processed: {stats['processed_urls']}")
        print(f"   Pending: {stats['pending_urls']}")
        print(f"   With Contact Pages: {stats['with_contact_pages']}")
        print(f"   With CAPTCHA: {stats['with_captcha']}")
        print(f"   Completion: {stats['percentage_complete']}%")
        
    except json.JSONDecodeError:
        print(f"❌ Invalid JSON in {companies_file}")
        return
    except Exception as e:
        print(f"❌ Error: {e}")
        return


def load_from_csv(csv_file):
    """Load URLs from CSV file"""
    print(f"\n📂 Loading from CSV: {csv_file}")
    
    try:
        import csv
        db = URLDatabase()
        
        urls = []
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                urls.append({
                    'url': row.get('url'),
                    'company_name': row.get('company_name'),
                    'industry': row.get('industry'),
                    'country': row.get('country')
                })
        
        print(f"📊 Found {len(urls)} URLs in CSV")
        
        added = db.add_urls_batch(urls)
        print(f"✅ Added {added} URLs")
        
        stats = db.get_database_stats()
        print(f"\n📊 Database Total: {stats['total_urls']} URLs")
        
    except Exception as e:
        print(f"❌ Error: {e}")


def load_from_json_file(json_file):
    """Load URLs from JSON file"""
    print(f"\n📂 Loading from JSON: {json_file}")
    
    try:
        db = URLDatabase()
        
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        companies = data.get('companies', data if isinstance(data, list) else [])
        print(f"📊 Found {len(companies)} URLs in JSON")
        
        added = db.add_urls_batch(companies)
        print(f"✅ Added {added} URLs")
        
        stats = db.get_database_stats()
        print(f"\n📊 Database Total: {stats['total_urls']} URLs")
        
    except Exception as e:
        print(f"❌ Error: {e}")


def show_stats():
    """Show current database statistics"""
    print(f"\n📊 Current Database Statistics:")
    print("=" * 50)
    
    db = URLDatabase()
    stats = db.get_database_stats()
    
    print(f"Total URLs: {stats['total_urls']}")
    print(f"Processed: {stats['processed_urls']}")
    print(f"Pending: {stats['pending_urls']}")
    print(f"With Contact Pages: {stats['with_contact_pages']}")
    print(f"With CAPTCHA: {stats['with_captcha']}")
    print(f"Total Fields Discovered: {stats['total_form_fields_discovered']}")
    print(f"Completion: {stats['percentage_complete']}%")
    print(f"\nStatus Breakdown:")
    for status, count in stats['status_breakdown'].items():
        print(f"  {status}: {count}")


def show_field_mapping():
    """Show field mapping analysis"""
    print(f"\n🔍 Field Mapping Analysis:")
    print("=" * 50)
    
    db = URLDatabase()
    mapping = db.get_field_mapping_summary()
    
    if not mapping:
        print("No fields in database yet")
        return
    
    # Sort by frequency
    sorted_mapping = sorted(mapping, key=lambda x: x['frequency'], reverse=True)
    
    print(f"\nTotal Unique Fields: {len(mapping)}\n")
    print("Top 20 Most Common Fields:")
    print("-" * 50)
    
    for i, item in enumerate(sorted_mapping[:20], 1):
        variations = ', '.join(item['field_name_variations'][:3])
        if len(item['field_name_variations']) > 3:
            variations += f", +{len(item['field_name_variations']) - 3} more"
        
        print(f"{i:2}. {item['normalized_name']:20} | Frequency: {item['frequency']:4} | Type: {item['common_type']}")
        print(f"    Variations: {variations}\n")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command == "stats":
            show_stats()
        elif command == "mapping":
            show_field_mapping()
        elif command == "csv" and len(sys.argv) > 2:
            load_from_csv(sys.argv[2])
        elif command == "json" and len(sys.argv) > 2:
            load_from_json_file(sys.argv[2])
        else:
            print(f"""
Usage:
  python load_database.py              # Load sample data
  python load_database.py stats        # Show database stats
  python load_database.py mapping      # Show field mapping
  python load_database.py csv <file>   # Load from CSV
  python load_database.py json <file>  # Load from JSON
            """)
    else:
        load_sample_data()
