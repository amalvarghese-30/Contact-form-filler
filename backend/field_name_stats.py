import sqlite3

DB_PATH = "../data/forms_insights.db"

def main():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # table: per-normalized key (name/email/phone/company/message/other), with how many websites use it
    cur.execute("""
        CREATE TABLE IF NOT EXISTS field_name_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT NOT NULL,
            websites INTEGER NOT NULL,
            total_fields INTEGER NOT NULL
        )
    """)

    # reset
    cur.execute("DELETE FROM field_name_stats")

    # naive categorisation based only on raw field_name text
    cur.execute("""
        SELECT
            CASE
                WHEN LOWER(field_name) LIKE '%name%' THEN 'name'
                WHEN LOWER(field_name) LIKE '%mail%' OR LOWER(field_name) LIKE '%email%' THEN 'email'
                WHEN LOWER(field_name) LIKE '%phone%' OR LOWER(field_name) LIKE '%mobile%' OR LOWER(field_name) LIKE '%tel%' THEN 'phone'
                WHEN LOWER(field_name) LIKE '%company%' OR LOWER(field_name) LIKE '%firm%' OR LOWER(field_name) LIKE '%org%' THEN 'company'
                WHEN LOWER(field_name) LIKE '%message%' OR LOWER(field_name) LIKE '%comment%' OR LOWER(field_name) LIKE '%subject%' THEN 'message'
                ELSE 'other'
            END AS key,
            website_id,
            field_name
        FROM raw_fields
    """)

    rows = cur.fetchall()

    # aggregate in Python
    from collections import defaultdict
    website_sets = defaultdict(set)
    total_counts = defaultdict(int)

    for key, website_id, field_name in rows:
        website_sets[key].add(website_id)
        total_counts[key] += 1

    for key in sorted(total_counts.keys()):
        cur.execute(
            "INSERT INTO field_name_stats (key, websites, total_fields) VALUES (?, ?, ?)",
            (key, len(website_sets[key]), total_counts[key]),
        )

    conn.commit()
    conn.close()
    print("✅ field_name_stats built")

if __name__ == "__main__":
    main()
