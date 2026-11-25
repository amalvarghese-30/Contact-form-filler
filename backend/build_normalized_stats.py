import sqlite3

DB_PATH = "../data/forms_insights.db"

def main():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS normalized_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            normalized_name TEXT NOT NULL,
            raw_name TEXT NOT NULL,
            count INTEGER DEFAULT 1,
            UNIQUE(normalized_name, raw_name)
        )
    """)

    cur.execute("DELETE FROM normalized_stats")

    cur.execute("""
        SELECT normalized_name, field_name, COUNT(*) as cnt
        FROM form_fields
        WHERE normalized_name IS NOT NULL
        GROUP BY normalized_name, field_name
    """)

    for norm, raw, cnt in cur.fetchall():
        cur.execute(
            """
            INSERT INTO normalized_stats (normalized_name, raw_name, count)
            VALUES (?, ?, ?)
            """,
            (norm, raw, cnt),
        )

    conn.commit()
    conn.close()
    print("✅ normalized_stats built")

if __name__ == "__main__":
    main()
