import sqlite3
import pandas as pd
from pathlib import Path

# Paths
DB_PATH = "../data/forms_insights.db"        # your insights DB
CSV_PATH = "../data/clean_root_domains.csv"  # your 27k URLs CSV


def main():
    db_path = Path(DB_PATH)
    csv_path = Path(CSV_PATH)

    if not db_path.exists():
        print("❌ DB not found:", db_path.resolve())
        return
    if not csv_path.exists():
        print("❌ CSV not found:", csv_path.resolve())
        return

    print("📖 Reading CSV:", csv_path)
    df = pd.read_csv(csv_path)

    # Detect URL column
    url_col = None
    for col in df.columns:
        cl = col.lower()
        if "url" in cl or "website" in cl or "link" in cl or "domain" in cl:
            url_col = col
            break

    if not url_col:
        print("❌ Could not detect URL column. Columns:", list(df.columns))
        return

    print("🌐 Using URL column:", url_col)

    urls = (
        df[url_col]
        .astype(str)
        .str.strip()
        .replace("", pd.NA)
        .dropna()
        .drop_duplicates()
        .tolist()
    )

    cleaned = []
    for u in urls:
        if not u:
            continue
        if not (u.startswith("http://") or u.startswith("https://")):
            u = "https://" + u
        cleaned.append(u)

    # Final dedupe preserving order
    cleaned = list(dict.fromkeys(cleaned))
    print(f"✅ {len(cleaned)} unique URLs ready to import")
    print("First 5:")
    for i, u in enumerate(cleaned[:5], 1):
        print(f"  {i}. {u}")

    print("\n📂 Opening DB:", db_path)
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # Ensure websites table exists
    cur.execute("""
        CREATE TABLE IF NOT EXISTS websites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT UNIQUE,
            has_captcha BOOLEAN DEFAULT 0,
            form_found BOOLEAN DEFAULT 0,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    print("🧹 Clearing old rows in websites...")
    cur.execute("DELETE FROM websites")

    print("📝 Inserting URLs...")
    inserted = 0
    for u in cleaned:
        try:
            cur.execute(
                "INSERT INTO websites (url, has_captcha, form_found) "
                "VALUES (?, 0, 0)",
                (u,),
            )
            inserted += 1
        except Exception as e:
            print("  ⚠️ Skip", u, "->", e)

    conn.commit()
    cur.execute("SELECT COUNT(*) FROM websites")
    total = cur.fetchone()[0]
    conn.close()

    print("\n✅ Import finished.")
    print("   Attempted:", len(cleaned))
    print("   Inserted :", inserted)
    print("   Rows now in websites:", total)


if __name__ == "__main__":
    main()
