# test_insert_value.py
import sqlite3
DB_PATH = "../data/forms_insights.db"

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

cur.execute(
    "INSERT INTO field_value_stats (field_category, field_value, count) VALUES (?, ?, ?)",
    ("first_name", "Rohan", 5)
)
conn.commit()
conn.close()
print("Inserted test row")
