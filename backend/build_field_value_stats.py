import sqlite3
import json

DB_PATH = "../data/forms_insights.db"


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Query to get all field values grouped by category
    cur.execute("""
        SELECT field_category, field_value, COUNT(*) as cnt
        FROM field_values
        WHERE field_value IS NOT NULL AND field_value != ''
        GROUP BY field_category, field_value
        ORDER BY field_category, cnt DESC
    """)

    rows = cur.fetchall()

    # Rebuild field_value_stats
    cur.execute("DELETE FROM field_value_stats")

    for row in rows:
        cur.execute(
            """
            INSERT INTO field_value_stats (field_category, field_value, count)
            VALUES (?, ?, ?)
            """,
            (row["field_category"], row["field_value"], row["cnt"])
        )

    conn.commit()

    # Print summary
    cur.execute("""
        SELECT field_category, COUNT(*) as unique_values, SUM(count) as total_count
        FROM field_value_stats
        GROUP BY field_category
        ORDER BY total_count DESC
    """)

    summary = cur.fetchall()
    print("\n✅ Field value statistics rebuilt:\n")
    print("Category          | Unique values | Total occurrences")
    print("-" * 55)
    for row in summary:
        print(f"{row['field_category']:<17} | {row['unique_values']:<13} | {row['total_count']:<13}")

    # Show top 10 values per category
    print("\n\n📊 Top values per category:\n")
    cur.execute("""
        SELECT field_category, field_value, count
        FROM field_value_stats
        ORDER BY field_category, count DESC
    """)

    current_cat = None
    cat_count = 0
    for row in cur.fetchall():
        if row["field_category"] != current_cat:
            current_cat = row["field_category"]
            cat_count = 0
            print(f"\n--- {current_cat} ---")
        
        if cat_count < 10:
            print(f"  {row['field_value']:<40} x {row['count']}")
            cat_count += 1

    conn.close()


if __name__ == "__main__":
    main()
