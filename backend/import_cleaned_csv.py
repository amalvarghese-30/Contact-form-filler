import sqlite3
import pandas as pd
from pathlib import Path

# Paths (adjust only if your folder structure is different)
DB_PATH = "../data/urls.db"
CSV_PATH = "../data/cleaned_companies.csv"  # cleaned 29k URLs file


def detect_url_column(df: pd.DataFrame) -> str:
    """
    Try to guess which column holds URLs, based on its name.
    Looks for: url, website, link, domain.
    """
    for col in df.columns:
        cl = col.lower()
        if "url" in cl or "website" in cl or "link" in cl or "domain" in cl:
            return col
    raise ValueError(f"Could not detect URL column automatically. Columns: {list(df.columns)}")


def load_urls_from_csv(csv_path: Path) -> list:
    """Load and clean URLs from CSV."""
    print(f"📖 Reading CSV: {csv_path}")
    df = pd.read_csv(csv_path)

    print(f"Columns in CSV: {list(df.columns)}")
    url_col = detect_url_column(df)
    print(f"🌐 Detected URL column: {url_col}")

    # Basic cleaning
    urls = (
        df[url_col]
        .astype(str)
        .str.strip()
        .replace("", pd.NA)
        .dropna()
        .drop_duplicates()
        .tolist()
    )

    # Ensure scheme (http/https)
    cleaned_urls = []
    for u in urls:
        if not u:
            continue
        if not (u.startswith("http://") or u.startswith("https://")):
            u = "https://" + u
        cleaned_urls.append(u)

    # Final de-dup
    cleaned_urls = list(dict.fromkeys(cleaned_urls))
    print(f"✅ URLs after cleaning & de-dup: {len(cleaned_urls)}")

    print("Preview (first 10):")
    for i, u in enumerate(cleaned_urls[:10], start=1):
        print(f"  {i}. {u}")

    return cleaned_urls


def import_into_sqlite(db_path: Path, urls: list):
    """Wipe old data and insert new URLs into company_urls."""
    if not urls:
        print("❌ No URLs to import. Aborting.")
        return

    print(f"\n📂 Opening database: {db_path}")
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # Clean existing data
    print("🧹 Cleaning old data (form_fields, company_urls, sqlite_sequence)...")
    try:
        cur.execute("DELETE FROM form_fields")
    except sqlite3.OperationalError:
        # table might not exist in some setups
        pass

    try:
        cur.execute("DELETE FROM company_urls")
    except sqlite3.OperationalError:
        pass

    try:
        cur.execute("DELETE FROM sqlite_sequence")
    except sqlite3.OperationalError:
        # sqlite_sequence exists only if AUTOINCREMENT is used
        pass

    conn.commit()

    # Insert new URLs
    print(f"📝 Inserting {len(urls)} URLs as 'pending'...")
    inserted = 0
    for u in urls:
        try:
            cur.execute(
                "INSERT INTO company_urls (url, status) VALUES (?, 'pending')",
                (u,),
            )
            inserted += 1
        except Exception as e:
            print(f"  ⚠️ Could not insert {u}: {e}")

    conn.commit()

    # Verify
    cur.execute("SELECT COUNT(*) FROM company_urls")
    total = cur.fetchone()[0]
    conn.close()

    print(f"\n✅ Import complete.")
    print(f"   Attempted: {len(urls)}")
    print(f"   Inserted : {inserted}")
    print(f"   Rows now in company_urls: {total}")


def main():
    csv_path = Path(CSV_PATH)
    db_path = Path(DB_PATH)

    if not csv_path.exists():
        print(f"❌ CSV not found at: {csv_path.resolve()}")
        return

    if not db_path.exists():
        print(f"❌ Database not found at: {db_path.resolve()}")
        return

    urls = load_urls_from_csv(csv_path)
    import_into_sqlite(db_path, urls)


if __name__ == "__main__":
    main()
