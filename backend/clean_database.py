import sqlite3
import os
from pathlib import Path

DB_PATH = "../data/urls.db"

def clean_database():
    """Clean all data from database"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("Cleaning database...")
    print("="*60)
    
    # Delete all form_fields
    cursor.execute("DELETE FROM form_fields")
    print("✅ Deleted all form_fields")
    
    # Delete all company_urls
    cursor.execute("DELETE FROM company_urls")
    print("✅ Deleted all company_urls")
    
    # Reset autoincrement
    cursor.execute("DELETE FROM sqlite_sequence")
    print("✅ Reset auto-increment")
    
    conn.commit()
    conn.close()
    
    print("="*60)
    print("✅ Database cleaned successfully!")
    print("Ready for new data.\n")

def verify_clean():
    """Verify database is clean"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM company_urls")
    urls_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM form_fields")
    fields_count = cursor.fetchone()[0]
    
    conn.close()
    
    print(f"URLs in database: {urls_count}")
    print(f"Form fields in database: {fields_count}")

if __name__ == "__main__":
    clean_database()
    verify_clean()
