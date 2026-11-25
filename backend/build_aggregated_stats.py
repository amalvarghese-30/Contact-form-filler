import sqlite3
import json

DB_PATH = "../data/forms_insights.db"


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Clear old stats
    cur.execute("DELETE FROM aggregated_stats")

    # Group by field_name + label (label ~ DOM label / placeholder)
    cur.execute("""
        SELECT field_name, placeholder AS label, COUNT(*) AS cnt
        FROM form_fields
        GROUP BY field_name, placeholder
        ORDER BY field_name, cnt DESC
    """)
    rows = cur.fetchall()

    stats = {}
    for r in rows:
        fname = r["field_name"]
        label = r["label"] or ""
        cnt = r["cnt"]

        if fname not in stats:
            stats[fname] = {"total": 0, "values": []}

        stats[fname]["total"] += cnt
        stats[fname]["values"].append({"value": label, "count": cnt})

    # Insert aggregated rows
    for fname, data in stats.items():
        values_sorted = sorted(data["values"], key=lambda x: x["count"], reverse=True)
        most_common = values_sorted[0]["value"] if values_sorted else ""
        total = data["total"]
        cur.execute(
            """
            INSERT INTO aggregated_stats (field_name, most_common_value, count, json_data)
            VALUES (?, ?, ?, ?)
            """,
            (fname, most_common, total, json.dumps(values_sorted))
        )

    conn.commit()
    conn.close()
    print("✅ aggregated_stats rebuilt")


if __name__ == "__main__":
    main()
