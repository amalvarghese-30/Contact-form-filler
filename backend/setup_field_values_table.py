import sqlite3

DB_PATH = "../data/forms_insights.db"

def main():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Table to store ACTUAL VALUES from form fields
    cur.execute("""
        CREATE TABLE IF NOT EXISTS field_values (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            website_id INTEGER NOT NULL,
            field_category TEXT NOT NULL,  -- normalized: first_name, last_name, email, etc
            field_name TEXT NOT NULL,  -- raw: fname, first_name, first, etc
            field_value TEXT,  -- ACTUAL VALUE captured from form (rohan, john, etc)
            FOREIGN KEY(website_id) REFERENCES websites(id)
        )
    """)

    # Table to store STATISTICS per field_category + value
    cur.execute("""
        CREATE TABLE IF NOT EXISTS field_value_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            field_category TEXT NOT NULL,  -- first_name, last_name, email, etc
            field_value TEXT NOT NULL,  -- rohan, john, etc
            count INTEGER DEFAULT 1,  -- how many times this value appeared
            websites_count INTEGER DEFAULT 1,  -- how many websites use this value
            UNIQUE(field_category, field_value)
        )
    """)

    conn.commit()
    conn.close()
    print("✅ Tables created: field_values, field_value_stats")

if __name__ == "__main__":
    main()
