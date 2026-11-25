import sqlite3
from pathlib import Path

DB_PATH = "../data/analytics.db"

def create_analytics_db():
    """Create analytics database with proper schema"""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Main analytics table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS website_analysis (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT UNIQUE NOT NULL,
            status TEXT DEFAULT 'pending',  -- pending, analyzing, completed, error
            contact_page_url TEXT,
            has_captcha BOOLEAN DEFAULT 0,
            form_type TEXT,  -- contact, registration, etc
            extracted_fields TEXT,  -- JSON format
            field_patterns JSON,  -- JSON: {name: [{pattern: fname, count: 150}, ...]}
            auto_filled BOOLEAN DEFAULT 0,
            submission_status TEXT,  -- success, failed, error
            error_message TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Field pattern statistics table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS field_statistics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            field_category TEXT NOT NULL,  -- name, email, phone, etc
            pattern TEXT NOT NULL,  -- fname, first_name, etc
            count INTEGER DEFAULT 1,
            websites_count INTEGER DEFAULT 1,  -- how many websites use this pattern
            UNIQUE(field_category, pattern)
        )
    """)

    # Global statistics
    cur.execute("""
        CREATE TABLE IF NOT EXISTS global_stats (
            id INTEGER PRIMARY KEY,
            total_websites_analyzed INTEGER DEFAULT 0,
            completed_analysis INTEGER DEFAULT 0,
            captcha_encountered INTEGER DEFAULT 0,
            successful_submissions INTEGER DEFAULT 0,
            failed_submissions INTEGER DEFAULT 0,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Insert default stats row
    cur.execute("INSERT OR IGNORE INTO global_stats (id) VALUES (1)")

    conn.commit()
    conn.close()
    print(f"✅ Analytics database created at: {DB_PATH}")

if __name__ == "__main__":
    create_analytics_db()
