import sqlite3

DB_PATH = "../data/forms_insights.db"

def main():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # raw values seen in forms
    cur.execute("""
        CREATE TABLE IF NOT EXISTS field_values (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            website_id INTEGER NOT NULL,
            field_category TEXT NOT NULL,
            field_name TEXT NOT NULL,
            field_value TEXT NOT NULL
        )
    """)

    # aggregated counts per category + value
    cur.execute("""
        CREATE TABLE IF NOT EXISTS field_value_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            field_category TEXT NOT NULL,
            field_value TEXT NOT NULL,
            count INTEGER DEFAULT 1,
            UNIQUE(field_category, field_value)
        )
    """)

    conn.commit()
    conn.close()
    print("✅ field_values and field_value_stats tables ready")

if __name__ == "__main__":
    main()
