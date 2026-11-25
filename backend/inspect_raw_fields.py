# inspect_raw_fields.py
import sqlite3, pathlib

db = pathlib.Path("..") / "data" / "forms_insights.db"
con = sqlite3.connect(db)
con.row_factory = sqlite3.Row
cur = con.cursor()

cur.execute("PRAGMA table_info(raw_fields)")
cols = cur.fetchall()
print("raw_fields columns:")
for c in cols:
    # c[1] is the column name, c[2] is the type
    print(f"- name={c[1]!r}, type={c[2]!r}")

con.close()
