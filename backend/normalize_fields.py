import sqlite3
from pathlib import Path
import re

# Use the same DB as scraper
DB_PATH = Path(__file__).resolve().parent.parent / "data" / "forms_insights.db"

print("Using DB:", DB_PATH)
conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# 1) Clear old normalized data (safe to rerun)
cur.execute("DELETE FROM form_fields")
cur.execute("DELETE FROM field_name_stats")
cur.execute("DELETE FROM field_value_stats")
conn.commit()
print("Cleared form_fields, field_name_stats, field_value_stats.")

# ---------- CLUSTERING RULES ----------

CLUSTERING_RULES = {
    "first_name": [
        r"fname", r"f_name", r"first_name", r"first name", r"firstname",
        r"given.?name", r"given_name", r"forename", r"name1"
    ],
    "last_name": [
        r"lname", r"l_name", r"last_name", r"last name", r"lastname",
        r"surname", r"family.?name", r"family_name", r"name2"
    ],
    "full_name": [
        r"^name$", r"full.?name", r"fullname", r"customer.?name",
        r"user.?name(?!_)", r"your.?name", r"contact.?name", r"visitor.?name"
    ],
    "email": [
        r"email", r"e.mail", r"e-mail", r"email.?address", r"mail",
        r"contact.?email", r"user.?email", r"your.?email"
    ],
    "phone": [
        r"phone", r"telephone", r"tel", r"mobile", r"cell", r"cellphone",
        r"phone.?number", r"contact.?phone", r"your.?phone"
    ],
    "company": [
        r"company", r"organization", r"organisation", r"org", r"firm",
        r"business.?name", r"business", r"company.?name", r"corporate"
    ],
    "subject": [
        r"subject", r"title", r"topic"
    ],
    "message": [
        r"message", r"comment", r"comments", r"inquiry", r"enquiry",
        r"description", r"msg", r"feedback", r"details", r"content",
        r"question", r"request", r"body"
    ],
    "address": [
        r"address", r"street", r"street.?address", r"location",
        r"mailing.?address", r"billing.?address"
    ],
    "city": [
        r"city", r"town", r"locality"
    ],
    "state": [
        r"state", r"province", r"region", r"county"
    ],
    "zip_code": [
        r"zip", r"postal.?code", r"postcode", r"zipcode", r"zip.?code",
        r"pin.?code", r"pincode"
    ],
    "country": [
        r"country", r"nation"
    ],
    "website": [
        r"website", r"web", r"url", r"homepage", r"site", r"web.?site"
    ],
}

def normalize_field_name(raw_name: str, placeholder: str) -> str:
    """
    Normalize a field using rules; never return 'other'.
    If nothing matches, return a cleaned version of the raw name or placeholder.
    """
    if not raw_name and not placeholder:
        return "unknown_field"

    s = ((raw_name or "") + " " + (placeholder or "")).lower().strip()

    # remove common prefixes/suffixes and junk
    s = re.sub(r"^(your_|your-|contact_|contact-|form_|form-|field_|field-)", "", s)
    s = re.sub(r"(_field|_input|_text|-field|-input|-text)$", "", s)
    s = re.sub(r"[_-]", " ", s)

    for cluster, patterns in CLUSTERING_RULES.items():
        for pat in patterns:
            if re.search(pat, s):
                return cluster

    # no "others": return cleaned raw label
    base = (raw_name or placeholder or "unknown_field").strip()
    base = re.sub(r"\s+", "_", base)
    return base

# 2) Build form_fields from raw_fields
cur.execute("SELECT * FROM raw_fields")
rows = cur.fetchall()
print("Raw fields rows:", len(rows))

# ensure form_fields table exists
cur.execute(
    """
    CREATE TABLE IF NOT EXISTS form_fields (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        website_id INTEGER NOT NULL,
        raw_name TEXT,
        normalized_name TEXT,
        field_type TEXT,
        placeholder TEXT
    )
    """
)
conn.commit()

for r in rows:
    raw_name = r["field_name"]
    placeholder = r["placeholder"]
    norm = normalize_field_name(raw_name, placeholder)

    cur.execute(
        """
        INSERT INTO form_fields
            (website_id, raw_name, normalized_name, field_type, placeholder)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            r["website_id"],
            raw_name,
            norm,
            r["field_type"],
            placeholder,
        ),
    )

conn.commit()
print("Inserted into form_fields with clustering applied.")

# 3) Aggregate into field_name_stats (per distinct field label)
cur.execute(
    """
    CREATE TABLE IF NOT EXISTS field_name_stats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        key TEXT NOT NULL UNIQUE,
        websites INTEGER NOT NULL DEFAULT 0,
        total_fields INTEGER NOT NULL DEFAULT 0
    )
    """
)
cur.execute("DELETE FROM field_name_stats")
conn.commit()

cur.execute("""
    INSERT INTO field_name_stats (key, websites, total_fields)
    SELECT normalized_name AS key,
           COUNT(DISTINCT website_id) AS websites,
           COUNT(*) AS total_fields
    FROM form_fields
    WHERE normalized_name IS NOT NULL
    GROUP BY normalized_name
""")
conn.commit()
print("Populated field_name_stats.")

# 4) Aggregate into field_value_stats (placeholders per field label)
cur.execute(
    """
    CREATE TABLE IF NOT EXISTS field_value_stats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        field_category TEXT NOT NULL,
        field_value TEXT NOT NULL,
        count INTEGER NOT NULL DEFAULT 0
    )
    """
)
cur.execute("DELETE FROM field_value_stats")
conn.commit()

cur.execute("""
    INSERT INTO field_value_stats (field_category, field_value, count)
    SELECT normalized_name AS field_category,
           placeholder AS field_value,
           COUNT(*) AS count
    FROM form_fields
    WHERE normalized_name IS NOT NULL
      AND placeholder IS NOT NULL
    GROUP BY normalized_name, placeholder
""")
conn.commit()
print("Populated field_value_stats.")

conn.close()
print("Done.")
